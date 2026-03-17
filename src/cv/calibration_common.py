"""Shared constants and defaults for calibration workflows."""

from __future__ import annotations

import cv2
import numpy as np

BOARD_DIAMETER_MM = 340
BOARD_RADIUS_MM = 170

FRAME_OUTER_MM = 517
FRAME_INNER_MM = 480
MARKER_SPACING_MM = 410
BOARD_CROP_MM = 380

ARUCO_DICT_TYPE = cv2.aruco.DICT_4X4_50
ARUCO_EXPECTED_IDS = [0, 1, 2, 3]
ARUCO_MARKER_SIZE_MM = 75

MM_PER_PX_MIN = 0.3
MM_PER_PX_MAX = 3.0
MANUAL_MIN_POINT_DISTANCE_PX = 50

RING_RADII_MM = {
    "bull_inner": 6.35,
    "bull_outer": 15.9,
    "triple_inner": 99.0,
    "triple_outer": 107.0,
    "double_inner": 162.0,
    "double_outer": 170.0,
}

RING_ORDER = [
    "bull_inner",
    "bull_outer",
    "triple_inner",
    "triple_outer",
    "double_inner",
    "double_outer",
]


def default_calibration_config() -> dict:
    """Return the default board calibration config payload."""
    return {
        "center_px": [200, 200],
        "radii_px": [10, 19, 106, 116, 188, 200],
        "rotation_deg": 0.0,
        "mm_per_px": 1.0,
        "homography": np.eye(3).tolist(),
        "last_update_utc": None,
        "valid": False,
        "method": None,
    }
