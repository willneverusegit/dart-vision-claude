"""CalibrationManager: manual 4-point, ArUco marker, and frame-based calibration."""

import cv2
import numpy as np
import yaml
import os
import tempfile
import argparse
import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BOARD_DIAMETER_MM = 340  # Standard dartboard playing area diameter
BOARD_RADIUS_MM = 170   # Double-outer ring radius

# Known surround frame dimensions (black frame around board)
FRAME_OUTER_MM = 517  # Outer edge of black frame
FRAME_INNER_MM = 480  # Inner edge of black frame (not used for calibration)

# CRITICAL: Physical center-to-center distance between adjacent ArUco markers.
# This is the actual measured distance, NOT the frame inner edge.
MARKER_SPACING_MM = 410  # Measured ArUco marker center-to-center distance

# ROI crop: board diameter + margin so the double ring is fully visible
BOARD_CROP_MM = 380   # 340mm board + 20mm margin each side

# ArUco configuration for the project markers
ARUCO_DICT_TYPE = cv2.aruco.DICT_4X4_50
ARUCO_EXPECTED_IDS = [0, 1, 2, 3]
ARUCO_MARKER_SIZE_MM = 75  # Edge length of printed markers

# Standard dartboard ring radii in mm (from center)
RING_RADII_MM = {
    "bull_inner": 6.35,     # Double bull (inner ring)
    "bull_outer": 15.9,     # Single bull (outer ring)
    "triple_inner": 99.0,   # Triple ring inner edge
    "triple_outer": 107.0,  # Triple ring outer edge
    "double_inner": 162.0,  # Double ring inner edge
    "double_outer": 170.0,  # Double ring outer edge (= board radius)
}


class CalibrationManager:
    """Manages board calibration: manual 4-point, ArUco, and frame-based."""

    def __init__(self, config_path: str = "config/calibration_config.yaml") -> None:
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load config from YAML or return defaults."""
        default: dict = {
            "center_px": [200, 200],
            "radii_px": [10, 19, 106, 116, 188, 200],
            "rotation_deg": 0.0,
            "mm_per_px": 1.0,
            "homography": np.eye(3).tolist(),
            "last_update_utc": None,
            "valid": False,
            "method": None,
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f)
                if loaded:
                    default.update(loaded)
            except Exception as e:
                logger.error("Config load error: %s", e)
        return default

    def manual_calibration(self, board_points: list[list[float]],
                           roi_size: tuple[int, int] = (400, 400)) -> dict:
        """
        Perform manual 4-point calibration.

        Args:
            board_points: 4 corner points [[x1,y1], ...] in clockwise order
            roi_size: Target ROI dimensions

        Returns:
            {"ok": True, "homography": list, "mm_per_px": float}
        """
        try:
            if len(board_points) != 4:
                return {"ok": False, "error": f"Expected 4 points, got {len(board_points)}"}
            src = np.float32(board_points)
            dst = np.float32([[0, 0], [roi_size[0], 0],
                              [roi_size[0], roi_size[1]], [0, roi_size[1]]])
            homography = cv2.getPerspectiveTransform(src, dst)
            det = np.linalg.det(homography)
            if abs(det) < 1e-6:
                return {"ok": False, "error": "Degenerate homography (det ~ 0)"}
            board_width_px = float(np.linalg.norm(src[1] - src[0]))
            if board_width_px < 1:
                return {"ok": False, "error": "Board width too small (< 1px)"}
            # Clicked points span the frame inner edge (480mm)
            mm_per_px = FRAME_INNER_MM / board_width_px
            center_x = float((src[0][0] + src[2][0]) / 2)
            center_y = float((src[0][1] + src[2][1]) / 2)
            # ROI (400px) maps the clicked area which spans FRAME_INNER_MM (480mm)
            roi_w = roi_size[0]
            roi_mm_per_px_local = FRAME_INNER_MM / roi_w
            radii_px = []
            for key in ["bull_inner", "bull_outer", "triple_inner",
                         "triple_outer", "double_inner", "double_outer"]:
                r_mm = RING_RADII_MM[key]
                r_px = r_mm / roi_mm_per_px_local
                radii_px.append(round(r_px, 1))
            self._config.update({
                "center_px": [center_x, center_y],
                "mm_per_px": mm_per_px,
                "radii_px": radii_px,
                "homography": homography.tolist(),
                "last_update_utc": datetime.now(timezone.utc).isoformat(),
                "valid": True,
                "method": "manual",
            })
            self._atomic_save()
            logger.info("Manual calibration complete (mm/px=%.3f)", mm_per_px)
            return {"ok": True, "homography": homography.tolist(), "mm_per_px": mm_per_px}
        except Exception as e:
            logger.error("Manual calibration failed: %s", e)
            return {"ok": False, "error": str(e)}

    def aruco_calibration(self, frame: np.ndarray,
                          expected_ids: list[int] | None = None,
                          marker_spacing_mm: float = MARKER_SPACING_MM,
                          roi_size: tuple[int, int] = (400, 400)) -> dict:
        """
        Detect ArUco markers (4x4_50 dict) and derive calibration.

        Markers are placed at the inner corners of the black surround frame.
        The known marker center-to-center distance (410mm) gives precise mm/px scaling.

        Args:
            frame: Single camera frame.
            expected_ids: Marker IDs to look for (default: [0,1,2,3]).
            marker_spacing_mm: Physical distance between marker centers (mm).
            roi_size: Target ROI size for warped output.

        Returns:
            {"ok": True, "homography": list, "mm_per_px": float, "corners_px": list}
        """
        if expected_ids is None:
            expected_ids = ARUCO_EXPECTED_IDS

        try:
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame

            # Use the correct dictionary: 4x4_50
            dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)

            # Configure detector for better detection
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

            # Try with CLAHE enhancement if normal detection fails
            corners, ids, rejected = detector.detectMarkers(gray)
            if ids is None or len(ids) < 4:
                # Retry with CLAHE contrast enhancement
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(gray)
                corners, ids, rejected = detector.detectMarkers(enhanced)

            if ids is None or len(ids) < 4:
                found = 0 if ids is None else len(ids)
                rejected_count = 0 if rejected is None else len(rejected)
                return {"ok": False,
                        "error": f"Found {found} markers (4x4_50 dict), "
                                 f"{rejected_count} rejected candidates. "
                                 f"Expected IDs: {expected_ids}"}

            flat_ids = ids.flatten().tolist()
            logger.info("Detected ArUco markers: %s", flat_ids)

            # Select the expected markers
            selected_indices = []
            for eid in expected_ids:
                if eid not in flat_ids:
                    return {"ok": False,
                            "error": f"Marker ID {eid} not found. Detected: {flat_ids}"}
                selected_indices.append(flat_ids.index(eid))

            # Get center of each selected marker
            centers = []
            for idx in selected_indices:
                marker_corners = corners[idx][0]
                cx = float(marker_corners[:, 0].mean())
                cy = float(marker_corners[:, 1].mean())
                centers.append([cx, cy])

            # Sort into TL, TR, BR, BL order
            centers_arr = np.float32(centers)
            s = centers_arr.sum(axis=1)
            d = np.diff(centers_arr, axis=1).flatten()
            tl_idx = int(np.argmin(s))
            br_idx = int(np.argmax(s))
            tr_idx = int(np.argmin(d))
            bl_idx = int(np.argmax(d))
            ordered = [centers[tl_idx], centers[tr_idx],
                       centers[br_idx], centers[bl_idx]]

            src_markers = np.float32(ordered)
            roi_w, roi_h = roi_size

            # Step 1: Compute homography from marker corners to a
            # "frame space" (410mm mapped to 410px for 1:1 mm-to-px)
            frame_px = marker_spacing_mm  # 410 (marker center-to-center)
            frame_dst = np.float32([
                [0, 0], [frame_px, 0],
                [frame_px, frame_px], [0, frame_px],
            ])
            H_frame = cv2.getPerspectiveTransform(src_markers, frame_dst)

            # Step 2: Define a tighter crop centered on the board
            # BOARD_CROP_MM (380mm) = board diameter + small margin
            crop_mm = BOARD_CROP_MM
            margin = (frame_px - crop_mm) / 2  # (410-380)/2 = 15
            crop_in_frame = np.float32([
                [margin, margin],
                [frame_px - margin, margin],
                [frame_px - margin, frame_px - margin],
                [margin, frame_px - margin],
            ])

            # Step 3: Map crop corners back to camera image coordinates
            H_frame_inv = np.linalg.inv(H_frame)
            crop_in_image = cv2.perspectiveTransform(
                crop_in_frame.reshape(1, -1, 2), H_frame_inv
            ).reshape(4, 2)

            # Step 4: Final homography — camera crop region → 400×400 ROI
            dst = np.float32([
                [0, 0], [roi_w, 0],
                [roi_w, roi_h], [0, roi_h],
            ])
            homography = cv2.getPerspectiveTransform(
                np.float32(crop_in_image), dst
            )

            det = np.linalg.det(homography)
            if abs(det) < 1e-6:
                return {"ok": False, "error": "Degenerate homography"}

            # Compute mm/px from ArUco marker edge length (75mm).
            # Each marker has 4 corners — average the edge lengths of all
            # detected markers for a robust per-pixel scale.
            edge_lengths_px = []
            for idx in selected_indices:
                mc = corners[idx][0]  # 4 corners of this marker
                for i in range(4):
                    edge = float(np.linalg.norm(mc[(i + 1) % 4] - mc[i]))
                    edge_lengths_px.append(edge)
            avg_edge_px = float(np.mean(edge_lengths_px)) if edge_lengths_px else 1.0
            mm_per_px = ARUCO_MARKER_SIZE_MM / avg_edge_px

            # Board center in original image
            center_x = float(np.mean(src_markers[:, 0]))
            center_y = float(np.mean(src_markers[:, 1]))

            # Compute radii in pixels for the cropped ROI
            # The ROI now spans BOARD_CROP_MM (380mm), not the full frame
            roi_mm_per_px = crop_mm / roi_w  # 380/400 = 0.95 mm/px
            radii_px = []
            for key in ["bull_inner", "bull_outer", "triple_inner",
                         "triple_outer", "double_inner", "double_outer"]:
                r_mm = RING_RADII_MM[key]
                r_px = r_mm / roi_mm_per_px
                radii_px.append(round(r_px, 1))

            self._config.update({
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
            })
            self._atomic_save()
            logger.info("ArUco calibration complete (mm/px=%.3f, markers=%s)",
                        mm_per_px, flat_ids)
            return {
                "ok": True,
                "homography": homography.tolist(),
                "mm_per_px": mm_per_px,
                "corners_px": ordered,
                "radii_px": radii_px,
                "detected_ids": flat_ids,
            }

        except Exception as e:
            logger.error("ArUco calibration failed: %s", e)
            return {"ok": False, "error": str(e)}

    def verify_rings(self, frame: np.ndarray) -> dict:
        """
        Verify calibrated ring radii against expected mathematical values.

        Note: HoughCircles-based ring detection was removed — it is too
        error-prone due to wire spider shadows and reflections. Ring
        positions are now derived purely from the calibrated homography
        and known dartboard dimensions (polar coordinate math).

        Returns:
            {"ok": bool, "radii_px": list, "expected_radii_px": list,
             "roi_mm_per_px": float}
        """
        h, w = frame.shape[:2] if len(frame.shape) >= 2 else (400, 400)
        crop_mm = self._config.get("board_crop_mm", BOARD_CROP_MM)
        roi_mm_per_px = crop_mm / w

        expected_radii = []
        ring_names = ["bull_inner", "bull_outer", "triple_inner",
                      "triple_outer", "double_inner", "double_outer"]
        for name in ring_names:
            r_mm = RING_RADII_MM[name]
            expected_radii.append(round(r_mm / roi_mm_per_px, 1))

        stored_radii = self._config.get("radii_px", [])

        return {
            "ok": True,
            "radii_px": stored_radii,
            "expected_radii_px": expected_radii,
            "roi_mm_per_px": roi_mm_per_px,
        }

    def find_optical_center(self, roi_frame: np.ndarray,
                            search_radius_mm: float = 10.0) -> tuple[float, float]:
        """
        Find the true optical center (bullseye) in the warped ROI frame.

        Even with a perfect homography the board may sag mechanically,
        shifting the bullseye a few mm from the geometric center.  This
        method searches a small region around the geometric center for
        the red/green bullseye using color thresholding in HSV.

        Args:
            roi_frame: The perspective-warped ROI image (BGR or grayscale).
            search_radius_mm: Search radius in mm (default ±10mm).

        Returns:
            (cx, cy) — refined center coordinates in ROI pixel space.
            Falls back to the geometric center if detection fails.
        """
        h, w = roi_frame.shape[:2]
        geo_cx, geo_cy = w / 2.0, h / 2.0

        # Convert search radius from mm to pixels
        crop_mm = self._config.get("board_crop_mm", BOARD_CROP_MM)
        roi_mm_per_px = crop_mm / w
        search_r_px = int(search_radius_mm / roi_mm_per_px)

        # Need a color image for HSV thresholding
        if len(roi_frame.shape) == 2:
            logger.debug("Grayscale ROI — cannot detect bullseye color, "
                         "using geometric center")
            return (geo_cx, geo_cy)

        # Crop a small search region around geometric center
        x1 = max(0, int(geo_cx) - search_r_px)
        y1 = max(0, int(geo_cy) - search_r_px)
        x2 = min(w, int(geo_cx) + search_r_px)
        y2 = min(h, int(geo_cy) + search_r_px)
        patch = roi_frame[y1:y2, x1:x2]

        if patch.size == 0:
            return (geo_cx, geo_cy)

        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)

        # Detect red bullseye (red wraps around H=0/180 in OpenCV HSV)
        mask_red1 = cv2.inRange(hsv, np.array([0, 70, 50]),
                                np.array([10, 255, 255]))
        mask_red2 = cv2.inRange(hsv, np.array([170, 70, 50]),
                                np.array([180, 255, 255]))
        # Also detect green (outer bull on many boards)
        mask_green = cv2.inRange(hsv, np.array([35, 70, 50]),
                                 np.array([85, 255, 255]))
        mask = mask_red1 | mask_red2 | mask_green

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Find the centroid of the largest blob
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            logger.debug("No bullseye blob found, using geometric center")
            return (geo_cx, geo_cy)

        largest = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest)
        if M["m00"] < 1:
            return (geo_cx, geo_cy)

        # Centroid in patch coordinates → ROI coordinates
        local_cx = M["m10"] / M["m00"]
        local_cy = M["m01"] / M["m00"]
        refined_cx = x1 + local_cx
        refined_cy = y1 + local_cy

        dx = refined_cx - geo_cx
        dy = refined_cy - geo_cy
        offset_mm = math.hypot(dx, dy) * roi_mm_per_px
        logger.info("Optical center offset: (%.1fpx, %.1fpx) = %.1fmm from geometric",
                    dx, dy, offset_mm)

        # Sanity check: reject if offset is too large (> search radius)
        if offset_mm > search_radius_mm:
            logger.warning("Optical center offset (%.1fmm) exceeds search radius "
                           "(%.1fmm), falling back to geometric center",
                           offset_mm, search_radius_mm)
            return (geo_cx, geo_cy)

        return (refined_cx, refined_cy)

    def charuco_calibration(self, frames: list[np.ndarray],
                            squares_x: int = 7, squares_y: int = 5,
                            square_length: float = 0.04,
                            marker_length: float = 0.02) -> dict:
        """ChArUco-based calibration from multiple frames."""
        try:
            if len(frames) < 3:
                return {"ok": False, "error": f"Need at least 3 frames, got {len(frames)}"}
            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
            board = cv2.aruco.CharucoBoard(
                (squares_x, squares_y), square_length, marker_length, dictionary)
            detector = cv2.aruco.ArucoDetector(dictionary)
            all_charuco_corners: list = []
            all_charuco_ids: list = []
            image_size = None
            for i, frame in enumerate(frames):
                if len(frame.shape) == 3:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                else:
                    gray = frame
                if image_size is None:
                    image_size = gray.shape[::-1]
                corners, ids, _ = detector.detectMarkers(gray)
                if ids is None or len(ids) < 4:
                    logger.warning("Frame %d: only %d markers, skipping",
                                   i, 0 if ids is None else len(ids))
                    continue
                ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                    corners, ids, gray, board)
                if ret >= 4:
                    all_charuco_corners.append(charuco_corners)
                    all_charuco_ids.append(charuco_ids)
            if len(all_charuco_corners) < 3:
                return {"ok": False,
                        "error": f"Only {len(all_charuco_corners)} usable frames (need 3+)"}
            ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.aruco.calibrateCameraCharuco(
                all_charuco_corners, all_charuco_ids, board, image_size, None, None)
            if not ret:
                return {"ok": False, "error": "Camera calibration failed"}
            h, w = frames[0].shape[:2]
            homography = np.eye(3)
            mm_per_px = float(square_length * 1000 / (w / squares_x))
            self._config.update({
                "center_px": [w / 2.0, h / 2.0],
                "mm_per_px": mm_per_px,
                "homography": homography.tolist(),
                "camera_matrix": camera_matrix.tolist(),
                "dist_coeffs": dist_coeffs.tolist(),
                "last_update_utc": datetime.now(timezone.utc).isoformat(),
                "valid": True,
                "method": "charuco",
                "reprojection_error": float(ret),
            })
            self._atomic_save()
            logger.info("ChArUco calibration complete (RMS=%.4f)", ret)
            return {"ok": True, "homography": homography.tolist(),
                    "mm_per_px": mm_per_px, "reprojection_error": float(ret)}
        except Exception as e:
            logger.error("ChArUco calibration failed: %s", e)
            return {"ok": False, "error": str(e)}

    def get_homography(self) -> np.ndarray | None:
        """Get current homography matrix, or None if not calibrated."""
        if self._config.get("valid", False):
            return np.array(self._config["homography"], dtype=np.float64)
        return None

    def get_config(self) -> dict:
        """Get current calibration config."""
        return dict(self._config)

    def is_valid(self) -> bool:
        """Check if calibration is valid."""
        return self._config.get("valid", False)

    def get_center(self) -> tuple[float, float]:
        """Get board center in original image pixel coordinates."""
        c = self._config.get("center_px", [200, 200])
        return (float(c[0]), float(c[1]))

    def get_optical_center(self) -> tuple[float, float] | None:
        """Get refined optical center in ROI pixel coordinates, if available."""
        c = self._config.get("optical_center_roi_px")
        if c and len(c) == 2:
            return (float(c[0]), float(c[1]))
        return None

    def get_mm_per_px(self) -> float:
        """Get scale factor (mm per pixel)."""
        return float(self._config.get("mm_per_px", 1.0))

    def get_radii_px(self) -> list[float]:
        """Get ring radii in pixels (for ROI-warped image)."""
        return self._config.get("radii_px", [10, 19, 106, 116, 188, 200])

    def _atomic_save(self) -> None:
        """Atomic config write: temp file -> os.replace()."""
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        os.makedirs(config_dir, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(suffix=".yaml", dir=config_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                yaml.dump(self._config, f, default_flow_style=False)
            os.replace(temp_path, self.config_path)
            logger.info("Config saved to %s", self.config_path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise


def _run_manual_cli(source: int) -> None:
    """Interactive CLI: click 4 board corners in an OpenCV window."""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error("Cannot open camera source: %d", source)
        return
    ret, frame = cap.read()
    cap.release()
    if not ret:
        logger.error("Failed to capture frame")
        return
    points: list[list[float]] = []
    display = frame.copy()
    window_name = "Calibration: Click 4 corners (TL, TR, BR, BL), then Enter"

    def on_mouse(event: int, x: int, y: int, flags: int, param: object) -> None:
        nonlocal display
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append([float(x), float(y)])
            cv2.circle(display, (x, y), 5, (0, 255, 0), -1)
            if len(points) > 1:
                cv2.line(display, (int(points[-2][0]), int(points[-2][1])),
                         (x, y), (0, 255, 0), 2)
            if len(points) == 4:
                cv2.line(display, (int(points[3][0]), int(points[3][1])),
                         (int(points[0][0]), int(points[0][1])), (0, 255, 0), 2)
            cv2.imshow(window_name, display)
            logger.info("Point %d: [%.1f, %.1f]", len(points), x, y)

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse)
    cv2.imshow(window_name, display)
    logger.info("Click 4 board corners (TL -> TR -> BR -> BL), then press Enter.")
    while True:
        key = cv2.waitKey(100) & 0xFF
        if key == 13 and len(points) == 4:
            break
        if key == 27:
            logger.info("Calibration cancelled")
            cv2.destroyAllWindows()
            return
        if key == ord("r"):
            points.clear()
            display = frame.copy()
            cv2.imshow(window_name, display)
            logger.info("Points reset")
    cv2.destroyAllWindows()
    manager = CalibrationManager()
    result = manager.manual_calibration(points)
    if result["ok"]:
        logger.info("Calibration saved! mm/px = %.3f", result["mm_per_px"])
    else:
        logger.error("Calibration failed: %s", result["error"])


def _run_charuco_cli(source: int) -> None:
    """Capture multiple frames with ChArUco board for calibration."""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error("Cannot open camera source: %d", source)
        return
    frames: list[np.ndarray] = []
    logger.info("Show ChArUco board. SPACE=capture, ENTER=done (need 3+).")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        display = frame.copy()
        cv2.putText(display, f"Captured: {len(frames)} (SPACE=capture, ENTER=done)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imshow("ChArUco Calibration", display)
        key = cv2.waitKey(30) & 0xFF
        if key == ord(" "):
            frames.append(frame.copy())
            logger.info("Frame %d captured", len(frames))
        elif key == 13 and len(frames) >= 3:
            break
        elif key == 27:
            logger.info("Calibration cancelled")
            cap.release()
            cv2.destroyAllWindows()
            return
    cap.release()
    cv2.destroyAllWindows()
    manager = CalibrationManager()
    result = manager.charuco_calibration(frames)
    if result["ok"]:
        logger.info("ChArUco calibration saved! RMS=%.4f, mm/px=%.3f",
                    result["reprojection_error"], result["mm_per_px"])
    else:
        logger.error("ChArUco calibration failed: %s", result["error"])


def main() -> None:
    """CLI entry point for calibration."""
    from src.utils.logger import setup_logging
    setup_logging()
    parser = argparse.ArgumentParser(description="Dart Board Calibration")
    parser.add_argument("--mode", choices=["manual", "charuco"], default="manual",
                        help="Calibration method")
    parser.add_argument("--source", type=int, default=0, help="Camera source index")
    args = parser.parse_args()
    if args.mode == "manual":
        _run_manual_cli(args.source)
    else:
        _run_charuco_cli(args.source)


if __name__ == "__main__":
    main()
