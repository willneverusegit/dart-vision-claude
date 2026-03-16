"""Stereo calibration: compute extrinsic parameters between two cameras."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CharucoBoardSpec:
    """Physical ChArUco board geometry used for calibration and overlays."""

    squares_x: int
    squares_y: int
    square_length_m: float
    marker_length_m: float
    dictionary_id: int = STEREO_CHARUCO_DICT
    preset_name: str = "custom"

    def __post_init__(self) -> None:
        if self.squares_x < 2 or self.squares_y < 2:
            raise ValueError("ChArUco board must have at least 2x2 squares")
        if self.square_length_m <= 0 or self.marker_length_m <= 0:
            raise ValueError("ChArUco square and marker length must be positive")
        if self.marker_length_m >= self.square_length_m:
            raise ValueError("ChArUco marker length must be smaller than square length")

    def create_dictionary(self):
        return cv2.aruco.getPredefinedDictionary(self.dictionary_id)

    def create_board(self, dictionary=None):
        dictionary = dictionary or self.create_dictionary()
        return cv2.aruco.CharucoBoard(
            (self.squares_x, self.squares_y),
            self.square_length_m,
            self.marker_length_m,
            dictionary,
        )

    def to_config_fragment(self) -> dict:
        return {
            "charuco_preset": self.preset_name,
            "charuco_squares_x": int(self.squares_x),
            "charuco_squares_y": int(self.squares_y),
            "charuco_square_length_m": float(self.square_length_m),
            "charuco_marker_length_m": float(self.marker_length_m),
        }

    def to_api_payload(self) -> dict:
        return {
            "preset": self.preset_name,
            "squares_x": int(self.squares_x),
            "squares_y": int(self.squares_y),
            "square_length_mm": float(self.square_length_m * 1000.0),
            "marker_length_mm": float(self.marker_length_m * 1000.0),
            "dictionary": "DICT_6X6_250",
        }


DEFAULT_CHARUCO_BOARD_SPEC = CharucoBoardSpec(
    squares_x=STEREO_SQUARES_X,
    squares_y=STEREO_SQUARES_Y,
    square_length_m=STEREO_SQUARE_LENGTH,
    marker_length_m=STEREO_MARKER_LENGTH,
    preset_name="40x20",
)

LARGE_MARKER_CHARUCO_BOARD_SPEC = CharucoBoardSpec(
    squares_x=STEREO_SQUARES_X,
    squares_y=STEREO_SQUARES_Y,
    square_length_m=STEREO_SQUARE_LENGTH,
    marker_length_m=0.028,
    preset_name="40x28",
)

_CHARUCO_BOARD_PRESETS = {
    "default": DEFAULT_CHARUCO_BOARD_SPEC,
    "40x20": DEFAULT_CHARUCO_BOARD_SPEC,
    "40x28": LARGE_MARKER_CHARUCO_BOARD_SPEC,
    "large_markers_40x28": LARGE_MARKER_CHARUCO_BOARD_SPEC,
}


def _canonical_preset_name(spec: CharucoBoardSpec) -> str:
    for preset in (DEFAULT_CHARUCO_BOARD_SPEC, LARGE_MARKER_CHARUCO_BOARD_SPEC):
        if (
            spec.squares_x == preset.squares_x
            and spec.squares_y == preset.squares_y
            and np.isclose(spec.square_length_m, preset.square_length_m)
            and np.isclose(spec.marker_length_m, preset.marker_length_m)
            and spec.dictionary_id == preset.dictionary_id
        ):
            return preset.preset_name
    return "custom"


def resolve_charuco_board_spec(
    *,
    config: dict | None = None,
    preset: str | None = None,
    squares_x: int | None = None,
    squares_y: int | None = None,
    square_length_m: float | None = None,
    marker_length_m: float | None = None,
    square_length_mm: float | None = None,
    marker_length_mm: float | None = None,
    board_spec: CharucoBoardSpec | None = None,
) -> CharucoBoardSpec:
    """Resolve a ChArUco board spec from preset/config/explicit overrides."""
    if board_spec is not None:
        base = board_spec
    else:
        config = config or {}
        preset_name = preset or config.get("charuco_preset")
        if preset_name is not None:
            key = str(preset_name).strip().lower()
            if key not in _CHARUCO_BOARD_PRESETS:
                known = ", ".join(sorted(_CHARUCO_BOARD_PRESETS))
                raise ValueError(f"Unknown ChArUco preset '{preset_name}'. Known presets: {known}")
            base = _CHARUCO_BOARD_PRESETS[key]
        else:
            base = DEFAULT_CHARUCO_BOARD_SPEC

        squares_x = config.get("charuco_squares_x", squares_x)
        squares_y = config.get("charuco_squares_y", squares_y)
        square_length_m = config.get("charuco_square_length_m", square_length_m)
        marker_length_m = config.get("charuco_marker_length_m", marker_length_m)

    if square_length_mm is not None:
        square_length_m = float(square_length_mm) / 1000.0
    if marker_length_mm is not None:
        marker_length_m = float(marker_length_mm) / 1000.0

    resolved = CharucoBoardSpec(
        squares_x=int(base.squares_x if squares_x is None else squares_x),
        squares_y=int(base.squares_y if squares_y is None else squares_y),
        square_length_m=float(base.square_length_m if square_length_m is None else square_length_m),
        marker_length_m=float(base.marker_length_m if marker_length_m is None else marker_length_m),
        dictionary_id=base.dictionary_id,
    )
    return CharucoBoardSpec(
        squares_x=resolved.squares_x,
        squares_y=resolved.squares_y,
        square_length_m=resolved.square_length_m,
        marker_length_m=resolved.marker_length_m,
        dictionary_id=resolved.dictionary_id,
        preset_name=_canonical_preset_name(resolved),
    )


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
    board_spec: CharucoBoardSpec | None = None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Detect ChArUco corners in a single frame.

    Returns (charuco_corners, charuco_ids) or (None, None) if detection fails.
    """
    board_spec = resolve_charuco_board_spec(board_spec=board_spec)
    if dictionary is None:
        dictionary = board_spec.create_dictionary()
    if board is None:
        board = board_spec.create_board(dictionary)

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
    board_spec: CharucoBoardSpec | None = None,
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

    board_spec = resolve_charuco_board_spec(board_spec=board_spec)
    dictionary = board_spec.create_dictionary()
    board = board_spec.create_board(dictionary)

    obj_points_all: list[np.ndarray] = []
    img_points_1_all: list[np.ndarray] = []
    img_points_2_all: list[np.ndarray] = []

    for i, (f1, f2) in enumerate(zip(frames_cam1, frames_cam2)):
        if image_size is None:
            h, w = f1.shape[:2]
            image_size = (w, h)

        cc1, ci1 = detect_charuco_corners(f1, dictionary, board, board_spec=board_spec)
        cc2, ci2 = detect_charuco_corners(f2, dictionary, board, board_spec=board_spec)

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
