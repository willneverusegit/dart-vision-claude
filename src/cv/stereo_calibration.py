"""Stereo calibration: compute extrinsic parameters between two cameras."""

from __future__ import annotations

import logging
from typing import NamedTuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ChArUco board parameters for stereo calibration
# (distinct from board ArUco markers which use DICT_4X4_50)
STEREO_CHARUCO_DICT = cv2.aruco.DICT_6X6_250
STEREO_SQUARES_X = 7
STEREO_SQUARES_Y = 5
STEREO_SQUARE_LENGTH = 0.04   # meters
STEREO_MARKER_LENGTH = 0.02   # meters


class StereoResult(NamedTuple):
    ok: bool
    R: np.ndarray | None           # 3x3 rotation matrix
    T: np.ndarray | None           # 3x1 translation vector
    reprojection_error: float
    error_message: str | None


def detect_charuco_corners(
    frame: np.ndarray,
    dictionary=None,
    board=None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Detect ChArUco corners in a single frame.

    Returns (charuco_corners, charuco_ids) or (None, None) if detection fails.
    """
    if dictionary is None:
        dictionary = cv2.aruco.getPredefinedDictionary(STEREO_CHARUCO_DICT)
    if board is None:
        board = cv2.aruco.CharucoBoard(
            (STEREO_SQUARES_X, STEREO_SQUARES_Y),
            STEREO_SQUARE_LENGTH, STEREO_MARKER_LENGTH, dictionary,
        )

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    detector = cv2.aruco.ArucoDetector(dictionary)
    corners, ids, _ = detector.detectMarkers(gray)

    if ids is None or len(ids) < 4:
        return None, None

    ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
        corners, ids, gray, board,
    )
    if ret < 4:
        return None, None

    return charuco_corners, charuco_ids


def stereo_calibrate(
    frames_cam1: list[np.ndarray],
    frames_cam2: list[np.ndarray],
    camera_matrix_1: np.ndarray,
    dist_coeffs_1: np.ndarray,
    camera_matrix_2: np.ndarray,
    dist_coeffs_2: np.ndarray,
    image_size: tuple[int, int] | None = None,
) -> StereoResult:
    """Compute extrinsic parameters between two cameras from synchronous ChArUco frames.

    Args:
        frames_cam1: List of frames from camera 1 (must be same length as frames_cam2).
        frames_cam2: List of frames from camera 2.
        camera_matrix_1: 3x3 intrinsic matrix of camera 1.
        dist_coeffs_1: Distortion coefficients of camera 1.
        camera_matrix_2: 3x3 intrinsic matrix of camera 2.
        dist_coeffs_2: Distortion coefficients of camera 2.
        image_size: (width, height) of the frames. Auto-detected if None.

    Returns:
        StereoResult with R, T, reprojection_error, or error message.
    """
    if len(frames_cam1) != len(frames_cam2):
        return StereoResult(False, None, None, 0.0,
                            f"Frame count mismatch: {len(frames_cam1)} vs {len(frames_cam2)}")
    if len(frames_cam1) < 5:
        return StereoResult(False, None, None, 0.0,
                            f"Need at least 5 frame pairs, got {len(frames_cam1)}")

    dictionary = cv2.aruco.getPredefinedDictionary(STEREO_CHARUCO_DICT)
    board = cv2.aruco.CharucoBoard(
        (STEREO_SQUARES_X, STEREO_SQUARES_Y),
        STEREO_SQUARE_LENGTH, STEREO_MARKER_LENGTH, dictionary,
    )

    obj_points_all: list[np.ndarray] = []
    img_points_1_all: list[np.ndarray] = []
    img_points_2_all: list[np.ndarray] = []

    for i, (f1, f2) in enumerate(zip(frames_cam1, frames_cam2)):
        if image_size is None:
            h, w = f1.shape[:2]
            image_size = (w, h)

        cc1, ci1 = detect_charuco_corners(f1, dictionary, board)
        cc2, ci2 = detect_charuco_corners(f2, dictionary, board)

        if cc1 is None or cc2 is None:
            logger.debug("Frame pair %d: detection failed in one camera, skipping", i)
            continue

        # Find common corner IDs
        ids1_flat = ci1.flatten()
        ids2_flat = ci2.flatten()
        common_ids = np.intersect1d(ids1_flat, ids2_flat)

        if len(common_ids) < 6:
            logger.debug("Frame pair %d: only %d common corners, skipping", i, len(common_ids))
            continue

        # Extract matching corners in consistent order
        mask1 = np.isin(ids1_flat, common_ids)
        mask2 = np.isin(ids2_flat, common_ids)

        pts1 = cc1[mask1].reshape(-1, 2)
        pts2 = cc2[mask2].reshape(-1, 2)

        # Sort by ID to ensure correspondence
        sorted_idx1 = np.argsort(ids1_flat[mask1])
        sorted_idx2 = np.argsort(ids2_flat[mask2])
        pts1 = pts1[sorted_idx1]
        pts2 = pts2[sorted_idx2]

        # Get object points for the common corner IDs
        obj_pts = board.getChessboardCorners()[common_ids].reshape(-1, 3).astype(np.float32)

        obj_points_all.append(obj_pts)
        img_points_1_all.append(pts1.astype(np.float32))
        img_points_2_all.append(pts2.astype(np.float32))

    if len(obj_points_all) < 3:
        return StereoResult(False, None, None, 0.0,
                            f"Only {len(obj_points_all)} usable frame pairs (need 3+)")

    try:
        flags = cv2.CALIB_FIX_INTRINSIC  # Intrinsics already calibrated per camera
        rms, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
            obj_points_all,
            img_points_1_all,
            img_points_2_all,
            camera_matrix_1, dist_coeffs_1,
            camera_matrix_2, dist_coeffs_2,
            image_size,
            flags=flags,
        )
    except cv2.error as e:
        return StereoResult(False, None, None, 0.0, f"stereoCalibrate failed: {e}")

    if not np.isfinite(rms):
        return StereoResult(False, None, None, 0.0, "Non-finite reprojection error")

    logger.info("Stereo calibration complete (RMS=%.4f)", rms)
    return StereoResult(True, R, T, float(rms), None)
