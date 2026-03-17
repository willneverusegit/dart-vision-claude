"""Pure board calibration workflow helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import math

import cv2
import numpy as np

from src.cv.calibration_common import (
    ARUCO_DICT_TYPE,
    ARUCO_EXPECTED_IDS,
    ARUCO_MARKER_SIZE_MM,
    BOARD_CROP_MM,
    FRAME_INNER_MM,
    MANUAL_MIN_POINT_DISTANCE_PX,
    MARKER_SPACING_MM,
    MM_PER_PX_MAX,
    MM_PER_PX_MIN,
    RING_ORDER,
    RING_RADII_MM,
)

logger = logging.getLogger(__name__)


def _build_radii_px(crop_mm: float, roi_width_px: int) -> list[float]:
    roi_mm_per_px = crop_mm / roi_width_px
    return [round(RING_RADII_MM[name] / roi_mm_per_px, 1) for name in RING_ORDER]


def manual_calibration_result(
    board_points: list[list[float]],
    roi_size: tuple[int, int] = (400, 400),
) -> dict:
    """Validate manual points and derive a board homography payload."""
    if len(board_points) != 4:
        return {"ok": False, "error": f"Expected 4 points, got {len(board_points)}"}

    src = np.float32(board_points)
    for i in range(4):
        for j in range(i + 1, 4):
            dist = float(np.linalg.norm(src[i] - src[j]))
            if dist < MANUAL_MIN_POINT_DISTANCE_PX:
                return {
                    "ok": False,
                    "error": (
                        f"Punkte {i} und {j} sind nur {dist:.0f}px voneinander entfernt "
                        f"(Minimum: {MANUAL_MIN_POINT_DISTANCE_PX}px). "
                        "Bitte groessere Abstaende zwischen den Ecken waehlen."
                    ),
                }

    dst = np.float32([[0, 0], [roi_size[0], 0], [roi_size[0], roi_size[1]], [0, roi_size[1]]])
    homography = cv2.getPerspectiveTransform(src, dst)
    if abs(np.linalg.det(homography)) < 1e-6:
        return {"ok": False, "error": "Degenerate homography (det ~ 0)"}

    board_width_px = float(np.linalg.norm(src[1] - src[0]))
    if board_width_px < 1:
        return {"ok": False, "error": "Board width too small (< 1px)"}

    mm_per_px = FRAME_INNER_MM / board_width_px
    if not (MM_PER_PX_MIN <= mm_per_px <= MM_PER_PX_MAX):
        return {
            "ok": False,
            "error": (
                f"Unrealistisches mm/px-Verhaeltnis ({mm_per_px:.3f}). "
                f"Erwartet: {MM_PER_PX_MIN}-{MM_PER_PX_MAX} mm/px. "
                "Kamera moeglicherweise zu nah oder zu weit vom Board entfernt."
            ),
        }

    center_x = float((src[0][0] + src[2][0]) / 2)
    center_y = float((src[0][1] + src[2][1]) / 2)
    radii_px = _build_radii_px(FRAME_INNER_MM, roi_size[0])

    return {
        "ok": True,
        "homography": homography.tolist(),
        "mm_per_px": mm_per_px,
        "config_updates": {
            "center_px": [center_x, center_y],
            "mm_per_px": mm_per_px,
            "radii_px": radii_px,
            "homography": homography.tolist(),
            "last_update_utc": datetime.now(timezone.utc).isoformat(),
            "valid": True,
            "method": "manual",
        },
    }


def aruco_calibration_result(
    frame: np.ndarray,
    *,
    expected_ids: list[int] | None = None,
    marker_spacing_mm: float = MARKER_SPACING_MM,
    roi_size: tuple[int, int] = (400, 400),
) -> dict:
    """Run the ArUco board calibration workflow and return config updates."""
    if expected_ids is None:
        expected_ids = ARUCO_EXPECTED_IDS

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)

    params = cv2.aruco.DetectorParameters()
    params.adaptiveThreshWinSizeMin = 3
    params.adaptiveThreshWinSizeMax = 23
    params.adaptiveThreshWinSizeStep = 10
    params.adaptiveThreshConstant = 7
    params.minMarkerPerimeterRate = 0.02
    params.maxMarkerPerimeterRate = 4.0
    params.polygonalApproxAccuracyRate = 0.03
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX

    detector = cv2.aruco.ArucoDetector(dictionary, params)

    corners, ids, rejected = detector.detectMarkers(gray)
    detection_method = "raw"

    if ids is None or len(ids) < 4:
        enhanced = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray)
        corners, ids, rejected = detector.detectMarkers(enhanced)
        detection_method = "clahe_3.0"

    if ids is None or len(ids) < 4:
        enhanced = cv2.createCLAHE(clipLimit=6.0, tileGridSize=(4, 4)).apply(gray)
        corners, ids, rejected = detector.detectMarkers(enhanced)
        detection_method = "clahe_6.0"

    if ids is None or len(ids) < 4:
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        enhanced = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8)).apply(blurred)
        corners, ids, rejected = detector.detectMarkers(enhanced)
        detection_method = "blur_clahe"

    if ids is None or len(ids) < 4:
        found = 0 if ids is None else len(ids)
        rejected_count = 0 if rejected is None else len(rejected)
        return {
            "ok": False,
            "error": (
                f"Found {found} markers (4x4_50 dict), "
                f"{rejected_count} rejected candidates. "
                f"Expected IDs: {expected_ids}"
            ),
        }

    flat_ids = ids.flatten().tolist()
    logger.info("Detected ArUco markers: %s", flat_ids)

    selected_indices = []
    for expected_id in expected_ids:
        if expected_id not in flat_ids:
            return {"ok": False, "error": f"Marker ID {expected_id} not found. Detected: {flat_ids}"}
        selected_indices.append(flat_ids.index(expected_id))

    centers = []
    for index in selected_indices:
        marker_corners = corners[index][0]
        centers.append([float(marker_corners[:, 0].mean()), float(marker_corners[:, 1].mean())])

    centers_arr = np.float32(centers)
    sums = centers_arr.sum(axis=1)
    diffs = np.diff(centers_arr, axis=1).flatten()
    ordered = [
        centers[int(np.argmin(sums))],
        centers[int(np.argmin(diffs))],
        centers[int(np.argmax(sums))],
        centers[int(np.argmax(diffs))],
    ]

    src_markers = np.float32(ordered)
    roi_w, roi_h = roi_size
    frame_px = marker_spacing_mm
    frame_dst = np.float32([[0, 0], [frame_px, 0], [frame_px, frame_px], [0, frame_px]])
    h_frame = cv2.getPerspectiveTransform(src_markers, frame_dst)

    crop_mm = BOARD_CROP_MM
    margin = (frame_px - crop_mm) / 2
    crop_in_frame = np.float32(
        [
            [margin, margin],
            [frame_px - margin, margin],
            [frame_px - margin, frame_px - margin],
            [margin, frame_px - margin],
        ]
    )

    h_frame_inv = np.linalg.inv(h_frame)
    crop_in_image = cv2.perspectiveTransform(crop_in_frame.reshape(1, -1, 2), h_frame_inv).reshape(4, 2)
    dst = np.float32([[0, 0], [roi_w, 0], [roi_w, roi_h], [0, roi_h]])
    homography = cv2.getPerspectiveTransform(np.float32(crop_in_image), dst)
    if abs(np.linalg.det(homography)) < 1e-6:
        return {"ok": False, "error": "Degenerate homography"}

    edge_lengths_px = []
    for index in selected_indices:
        marker_corners = corners[index][0]
        for corner_index in range(4):
            edge_lengths_px.append(
                float(np.linalg.norm(marker_corners[(corner_index + 1) % 4] - marker_corners[corner_index]))
            )
    avg_edge_px = float(np.mean(edge_lengths_px)) if edge_lengths_px else 1.0
    mm_per_px = ARUCO_MARKER_SIZE_MM / avg_edge_px
    if not (MM_PER_PX_MIN <= mm_per_px <= MM_PER_PX_MAX):
        return {
            "ok": False,
            "error": (
                f"Unrealistisches mm/px-Verhaeltnis ({mm_per_px:.3f}). "
                f"Erwartet: {MM_PER_PX_MIN}-{MM_PER_PX_MAX} mm/px. "
                "Kamera moeglicherweise zu nah oder zu weit vom Board entfernt."
            ),
        }

    center_x = float(np.mean(src_markers[:, 0]))
    center_y = float(np.mean(src_markers[:, 1]))
    radii_px = _build_radii_px(crop_mm, roi_w)

    return {
        "ok": True,
        "homography": homography.tolist(),
        "mm_per_px": mm_per_px,
        "corners_px": ordered,
        "radii_px": radii_px,
        "detected_ids": flat_ids,
        "detection_method": detection_method,
        "config_updates": {
            "center_px": [center_x, center_y],
            "mm_per_px": mm_per_px,
            "homography": homography.tolist(),
            "radii_px": radii_px,
            "marker_spacing_mm": marker_spacing_mm,
            "board_crop_mm": crop_mm,
            "marker_corners_px": ordered,
            "last_update_utc": datetime.now(timezone.utc).isoformat(),
            "valid": True,
            "method": "aruco",
        },
    }


def verify_rings_result(config: dict, frame: np.ndarray) -> dict:
    """Compare stored ring radii against expected radii for the warped ROI."""
    _height, width = frame.shape[:2] if len(frame.shape) >= 2 else (400, 400)
    crop_mm = config.get("board_crop_mm", BOARD_CROP_MM)
    roi_mm_per_px = crop_mm / width
    expected_radii = [round(RING_RADII_MM[name] / roi_mm_per_px, 1) for name in RING_ORDER]
    stored_radii = config.get("radii_px", [])

    if stored_radii and len(stored_radii) == len(expected_radii):
        deviations_px = [round(abs(stored - expected), 1) for stored, expected in zip(stored_radii, expected_radii)]
        max_dev_px = max(deviations_px)
        max_dev_mm = round(max_dev_px * roi_mm_per_px, 1)
        quality = max(0, round(100 - max_dev_px * 20))
    else:
        deviations_px = []
        max_dev_mm = 0.0
        quality = 0

    return {
        "ok": True,
        "radii_px": stored_radii,
        "expected_radii_px": expected_radii,
        "roi_mm_per_px": roi_mm_per_px,
        "deviations_px": deviations_px,
        "max_deviation_mm": max_dev_mm,
        "quality": quality,
    }


def find_optical_center(config: dict, roi_frame: np.ndarray, search_radius_mm: float = 10.0) -> tuple[float, float]:
    """Find the likely bullseye center in an ROI frame."""
    height, width = roi_frame.shape[:2]
    geo_cx, geo_cy = width / 2.0, height / 2.0
    crop_mm = config.get("board_crop_mm", BOARD_CROP_MM)
    roi_mm_per_px = crop_mm / width
    search_r_px = int(search_radius_mm / roi_mm_per_px)

    if len(roi_frame.shape) == 2:
        logger.debug("Grayscale ROI - cannot detect bullseye color, using geometric center")
        return (geo_cx, geo_cy)

    x1 = max(0, int(geo_cx) - search_r_px)
    y1 = max(0, int(geo_cy) - search_r_px)
    x2 = min(width, int(geo_cx) + search_r_px)
    y2 = min(height, int(geo_cy) + search_r_px)
    patch = roi_frame[y1:y2, x1:x2]
    if patch.size == 0:
        return (geo_cx, geo_cy)

    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    mask_red1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
    mask_red2 = cv2.inRange(hsv, np.array([170, 70, 50]), np.array([180, 255, 255]))
    mask_green = cv2.inRange(hsv, np.array([35, 70, 50]), np.array([85, 255, 255]))
    mask = mask_red1 | mask_red2 | mask_green

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        gray_patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
        blurred_patch = cv2.GaussianBlur(gray_patch, (11, 11), 0)
        _min_val, _max_val, _min_loc, max_loc = cv2.minMaxLoc(blurred_patch)
        px, py = max_loc
        patch_h, patch_w = patch.shape[:2]
        if abs(px - patch_w / 2) < patch_w * 0.3 and abs(py - patch_h / 2) < patch_h * 0.3:
            refined_cx = x1 + px
            refined_cy = y1 + py
            logger.info("Optical center via intensity fallback: (%.1f, %.1f)", refined_cx, refined_cy)
            return (refined_cx, refined_cy)
        logger.debug("No bullseye blob found, using geometric center")
        return (geo_cx, geo_cy)

    largest = max(contours, key=cv2.contourArea)
    moments = cv2.moments(largest)
    if moments["m00"] < 1:
        return (geo_cx, geo_cy)

    refined_cx = x1 + moments["m10"] / moments["m00"]
    refined_cy = y1 + moments["m01"] / moments["m00"]
    dx = refined_cx - geo_cx
    dy = refined_cy - geo_cy
    offset_mm = math.hypot(dx, dy) * roi_mm_per_px
    logger.info(
        "Optical center offset: (%.1fpx, %.1fpx) = %.1fmm from geometric",
        dx,
        dy,
        offset_mm,
    )

    if offset_mm > search_radius_mm:
        logger.warning(
            "Optical center offset (%.1fmm) exceeds search radius (%.1fmm), falling back to geometric center",
            offset_mm,
            search_radius_mm,
        )
        return (geo_cx, geo_cy)

    return (refined_cx, refined_cy)
