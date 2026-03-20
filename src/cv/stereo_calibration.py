"""Stereo calibration: compute extrinsic parameters between two cameras."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import cv2
import numpy as np

from src.cv.geometry import CameraIntrinsics

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
    preset_name="7x5_40x20",
)

LARGE_MARKER_CHARUCO_BOARD_SPEC = CharucoBoardSpec(
    squares_x=STEREO_SQUARES_X,
    squares_y=STEREO_SQUARES_Y,
    square_length_m=STEREO_SQUARE_LENGTH,
    marker_length_m=0.028,
    preset_name="7x5_40x28",
)

PORTRAIT_CHARUCO_BOARD_SPEC = CharucoBoardSpec(
    squares_x=5,
    squares_y=7,
    square_length_m=STEREO_SQUARE_LENGTH,
    marker_length_m=STEREO_MARKER_LENGTH,
    preset_name="5x7_40x20",
)

PORTRAIT_LARGE_MARKER_CHARUCO_BOARD_SPEC = CharucoBoardSpec(
    squares_x=5,
    squares_y=7,
    square_length_m=STEREO_SQUARE_LENGTH,
    marker_length_m=0.028,
    preset_name="5x7_40x28",
)

_CHARUCO_BOARD_PRESETS = {
    "default": DEFAULT_CHARUCO_BOARD_SPEC,
    "40x20": DEFAULT_CHARUCO_BOARD_SPEC,
    "40x28": LARGE_MARKER_CHARUCO_BOARD_SPEC,
    "large_markers_40x28": LARGE_MARKER_CHARUCO_BOARD_SPEC,
    "7x5_40x20": DEFAULT_CHARUCO_BOARD_SPEC,
    "7x5_40x28": LARGE_MARKER_CHARUCO_BOARD_SPEC,
    "5x7_40x20": PORTRAIT_CHARUCO_BOARD_SPEC,
    "5x7_40x28": PORTRAIT_LARGE_MARKER_CHARUCO_BOARD_SPEC,
}

_CONCRETE_CHARUCO_BOARD_PRESETS = (
    DEFAULT_CHARUCO_BOARD_SPEC,
    LARGE_MARKER_CHARUCO_BOARD_SPEC,
    PORTRAIT_CHARUCO_BOARD_SPEC,
    PORTRAIT_LARGE_MARKER_CHARUCO_BOARD_SPEC,
)


@dataclass(frozen=True)
class CharucoDetectionResult:
    """Best-effort ChArUco detection result for one frame."""

    board_spec: CharucoBoardSpec | None
    charuco_corners: np.ndarray | None
    charuco_ids: np.ndarray | None
    marker_corners: tuple[np.ndarray, ...]
    marker_ids: np.ndarray | None
    markers_found: int
    charuco_corners_found: int
    interpolation_ok: bool
    warning: str | None = None


@dataclass(frozen=True)
class BoardPoseEstimate:
    """PnP pose of the ChArUco board in one camera."""

    R: np.ndarray
    t: np.ndarray
    rvec: np.ndarray
    tvec: np.ndarray
    reprojection_error_px: float
    corner_count: int
    board_spec: CharucoBoardSpec


def _canonical_preset_name(spec: CharucoBoardSpec) -> str:
    for preset in _CONCRETE_CHARUCO_BOARD_PRESETS:
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


def resolve_charuco_board_candidates(
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
) -> list[CharucoBoardSpec]:
    """Resolve one or more candidate ChArUco boards.

    ``preset="auto"`` evaluates all known concrete layouts. Concrete presets and
    legacy aliases still resolve to a single board spec.
    """
    config = config or {}
    preset_name = preset if preset is not None else config.get("charuco_preset")

    if board_spec is not None:
        return [
            resolve_charuco_board_spec(
                board_spec=board_spec,
                squares_x=squares_x,
                squares_y=squares_y,
                square_length_m=square_length_m,
                marker_length_m=marker_length_m,
                square_length_mm=square_length_mm,
                marker_length_mm=marker_length_mm,
            )
        ]

    if str(preset_name).strip().lower() != "auto":
        return [
            resolve_charuco_board_spec(
                config=config,
                preset=preset,
                squares_x=squares_x,
                squares_y=squares_y,
                square_length_m=square_length_m,
                marker_length_m=marker_length_m,
                square_length_mm=square_length_mm,
                marker_length_mm=marker_length_mm,
            )
        ]

    if square_length_mm is not None:
        square_length_m = float(square_length_mm) / 1000.0
    if marker_length_mm is not None:
        marker_length_m = float(marker_length_mm) / 1000.0

    candidates: list[CharucoBoardSpec] = []
    for base in _CONCRETE_CHARUCO_BOARD_PRESETS:
        resolved = CharucoBoardSpec(
            squares_x=int(base.squares_x if squares_x is None else squares_x),
            squares_y=int(base.squares_y if squares_y is None else squares_y),
            square_length_m=float(
                base.square_length_m if square_length_m is None else square_length_m
            ),
            marker_length_m=float(
                base.marker_length_m if marker_length_m is None else marker_length_m
            ),
            dictionary_id=base.dictionary_id,
            preset_name=base.preset_name,
        )
        candidates.append(
            CharucoBoardSpec(
                squares_x=resolved.squares_x,
                squares_y=resolved.squares_y,
                square_length_m=resolved.square_length_m,
                marker_length_m=resolved.marker_length_m,
                dictionary_id=resolved.dictionary_id,
                preset_name=_canonical_preset_name(resolved),
            )
        )

    deduped: list[CharucoBoardSpec] = []
    seen: set[tuple[int, int, float, float, int]] = set()
    for candidate in candidates:
        key = (
            candidate.squares_x,
            candidate.squares_y,
            round(candidate.square_length_m, 6),
            round(candidate.marker_length_m, 6),
            candidate.dictionary_id,
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _build_aruco_detector(dictionary) -> cv2.aruco.ArucoDetector:
    params = cv2.aruco.DetectorParameters()
    if hasattr(params, "cornerRefinementMethod"):
        params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    return cv2.aruco.ArucoDetector(dictionary, params)


def detect_charuco_board(
    frame: np.ndarray,
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
    board_specs: list[CharucoBoardSpec] | tuple[CharucoBoardSpec, ...] | None = None,
    min_markers: int = 4,
    min_corners: int = 4,
) -> CharucoDetectionResult:
    """Detect the best matching ChArUco board in a single frame."""

    candidates = list(board_specs or resolve_charuco_board_candidates(
        config=config,
        preset=preset,
        squares_x=squares_x,
        squares_y=squares_y,
        square_length_m=square_length_m,
        marker_length_m=marker_length_m,
        square_length_mm=square_length_mm,
        marker_length_mm=marker_length_mm,
        board_spec=board_spec,
    ))
    if not candidates:
        return CharucoDetectionResult(
            board_spec=None,
            charuco_corners=None,
            charuco_ids=None,
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=0,
            interpolation_ok=False,
            warning="Keine ChArUco-Layouts konfiguriert.",
        )

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    dictionary = candidates[0].create_dictionary()
    detector = _build_aruco_detector(dictionary)
    marker_corners, marker_ids, _ = detector.detectMarkers(gray)
    markers_found = 0 if marker_ids is None else int(len(marker_ids))
    if marker_ids is None or markers_found < min_markers:
        warning = (
            f"Nur {markers_found} Rohmarker erkannt."
            if markers_found
            else "Kein ChArUco-Board sichtbar."
        )
        return CharucoDetectionResult(
            board_spec=candidates[0] if len(candidates) == 1 else None,
            charuco_corners=None,
            charuco_ids=None,
            marker_corners=tuple(marker_corners or ()),
            marker_ids=marker_ids,
            markers_found=markers_found,
            charuco_corners_found=0,
            interpolation_ok=False,
            warning=warning,
        )

    best_spec: CharucoBoardSpec | None = candidates[0] if len(candidates) == 1 else None
    best_corners: np.ndarray | None = None
    best_ids: np.ndarray | None = None
    best_corner_count = -1

    for candidate in candidates:
        board = candidate.create_board(dictionary)
        ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
            marker_corners, marker_ids, gray, board,
        )
        corner_count = int(ret) if ret else 0
        if corner_count > best_corner_count:
            best_corner_count = corner_count
            best_spec = candidate
            best_corners = charuco_corners if corner_count > 0 else None
            best_ids = charuco_ids if corner_count > 0 else None

    warning = None
    interpolation_ok = best_corner_count >= min_corners
    if best_corner_count <= 0:
        warning = "Rohmarker erkannt, aber kein passendes ChArUco-Layout interpoliert."
        if len(candidates) != 1:
            best_spec = None
    elif not interpolation_ok:
        warning = f"Nur {best_corner_count} ChArUco-Ecken erkannt."

    return CharucoDetectionResult(
        board_spec=best_spec,
        charuco_corners=best_corners,
        charuco_ids=best_ids,
        marker_corners=tuple(marker_corners or ()),
        marker_ids=marker_ids,
        markers_found=markers_found,
        charuco_corners_found=max(best_corner_count, 0),
        interpolation_ok=interpolation_ok,
        warning=warning,
    )


def validate_stereo_prerequisites(
    cam_a_id: str,
    cam_b_id: str,
    config_path: str = "config/calibration_config.yaml",
) -> dict:
    """Check that both cameras have valid intrinsics before stereo calibration.

    Returns:
        dict with 'ready' (bool), 'errors' (list[str]), 'warnings' (list[str])
    """
    from src.cv.camera_calibration import CameraCalibrationManager

    errors: list[str] = []
    warnings: list[str] = []

    for cam_id in [cam_a_id, cam_b_id]:
        mgr = CameraCalibrationManager(config_path=config_path, camera_id=cam_id)
        result = mgr.validate_intrinsics()
        if not result["valid"]:
            errors.append(f"Kamera '{cam_id}': " + "; ".join(result["errors"]))
        warnings.extend(f"Kamera '{cam_id}': {w}" for w in result.get("warnings", []))

    return {
        "ready": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


class StereoResult(NamedTuple):
    ok: bool
    R: np.ndarray | None           # 3x3 rotation matrix
    T: np.ndarray | None           # 3x1 translation vector
    reprojection_error: float
    error_message: str | None


class ProvisionalStereoResult(NamedTuple):
    ok: bool
    R: np.ndarray | None
    T: np.ndarray | None
    reprojection_error: float
    pose_consistency_px: float
    pairs_used: int
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
    if board_spec is None:
        board_spec = resolve_charuco_board_spec(board_spec=board_spec)
    result = detect_charuco_board(frame, board_spec=board_spec)
    return result.charuco_corners, result.charuco_ids


def estimate_charuco_board_pose(
    detection: CharucoDetectionResult,
    intrinsics: CameraIntrinsics,
    *,
    board_spec: CharucoBoardSpec | None = None,
) -> BoardPoseEstimate | None:
    """Estimate a board pose from a successful ChArUco detection."""
    if intrinsics is None:
        return None
    resolved_board_spec = board_spec or detection.board_spec
    if (
        resolved_board_spec is None
        or not detection.interpolation_ok
        or detection.charuco_corners is None
        or detection.charuco_ids is None
    ):
        return None

    ids = detection.charuco_ids.reshape(-1)
    if len(ids) < 4:
        return None

    board = resolved_board_spec.create_board()
    object_points = board.getChessboardCorners()[ids].reshape(-1, 3).astype(np.float64)
    image_points = detection.charuco_corners.reshape(-1, 2).astype(np.float64)

    try:
        success, rvec, tvec = cv2.solvePnP(
            object_points,
            image_points,
            intrinsics.camera_matrix,
            intrinsics.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
    except cv2.error:
        return None
    if not success:
        return None

    R, _ = cv2.Rodrigues(rvec)
    proj, _ = cv2.projectPoints(
        object_points,
        rvec,
        tvec,
        intrinsics.camera_matrix,
        intrinsics.dist_coeffs,
    )
    reprojection_error_px = float(
        np.mean(np.linalg.norm(proj.reshape(-1, 2) - image_points, axis=1))
    )
    return BoardPoseEstimate(
        R=R.astype(np.float64),
        t=tvec.reshape(3).astype(np.float64),
        rvec=rvec.reshape(3, 1).astype(np.float64),
        tvec=tvec.reshape(3, 1).astype(np.float64),
        reprojection_error_px=reprojection_error_px,
        corner_count=int(len(ids)),
        board_spec=resolved_board_spec,
    )


def stereo_from_board_poses(
    pose_a: BoardPoseEstimate,
    pose_b: BoardPoseEstimate,
) -> tuple[np.ndarray, np.ndarray]:
    """Convert two board poses into camera-a -> camera-b extrinsics."""
    R = pose_b.R @ pose_a.R.T
    T = pose_b.t.reshape(3, 1) - R @ pose_a.t.reshape(3, 1)
    return R.astype(np.float64), T.astype(np.float64)


def _average_stereo_extrinsics(
    relative_rotations: list[np.ndarray],
    relative_translations: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    rotation_sum = np.zeros((3, 3), dtype=np.float64)
    for rotation in relative_rotations:
        rotation_sum += rotation
    U, _s, Vt = np.linalg.svd(rotation_sum)
    averaged_rotation = U @ Vt
    if np.linalg.det(averaged_rotation) < 0:
        U[:, -1] *= -1
        averaged_rotation = U @ Vt
    averaged_translation = np.mean(
        np.stack([t.reshape(3, 1) for t in relative_translations], axis=0),
        axis=0,
    )
    return averaged_rotation.astype(np.float64), averaged_translation.astype(np.float64)


def provisional_stereo_calibrate(
    detections_cam1: list[CharucoDetectionResult],
    detections_cam2: list[CharucoDetectionResult],
    intrinsics_1: CameraIntrinsics,
    intrinsics_2: CameraIntrinsics,
    *,
    board_spec: CharucoBoardSpec | None = None,
) -> ProvisionalStereoResult:
    """Estimate stereo extrinsics from paired board poses when intrinsics are provisional."""
    if len(detections_cam1) != len(detections_cam2):
        return ProvisionalStereoResult(
            False,
            None,
            None,
            0.0,
            0.0,
            0,
            f"Frame count mismatch: {len(detections_cam1)} vs {len(detections_cam2)}",
        )

    relative_rotations: list[np.ndarray] = []
    relative_translations: list[np.ndarray] = []
    pose_errors: list[float] = []

    for detection_a, detection_b in zip(detections_cam1, detections_cam2):
        pose_a = estimate_charuco_board_pose(
            detection_a,
            intrinsics_1,
            board_spec=board_spec,
        )
        pose_b = estimate_charuco_board_pose(
            detection_b,
            intrinsics_2,
            board_spec=board_spec,
        )
        if pose_a is None or pose_b is None:
            continue
        relative_rotation, relative_translation = stereo_from_board_poses(pose_a, pose_b)
        relative_rotations.append(relative_rotation)
        relative_translations.append(relative_translation)
        pose_errors.append(
            float((pose_a.reprojection_error_px + pose_b.reprojection_error_px) / 2.0)
        )

    if len(relative_rotations) < 3:
        return ProvisionalStereoResult(
            False,
            None,
            None,
            0.0,
            0.0,
            len(relative_rotations),
            f"Only {len(relative_rotations)} usable pose pairs (need 3+)",
        )

    averaged_rotation, averaged_translation = _average_stereo_extrinsics(
        relative_rotations,
        relative_translations,
    )
    pose_consistency_px = float(np.mean(pose_errors)) if pose_errors else 0.0
    return ProvisionalStereoResult(
        True,
        averaged_rotation,
        averaged_translation,
        pose_consistency_px,
        pose_consistency_px,
        len(relative_rotations),
        None,
    )


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
