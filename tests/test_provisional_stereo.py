import numpy as np

from src.cv.camera_calibration import estimate_intrinsics
from src.cv.stereo_calibration import (
    BoardPoseEstimate,
    DEFAULT_CHARUCO_BOARD_SPEC,
    provisional_stereo_calibrate,
    stereo_from_board_poses,
)


def _pose(rotation=None, translation=None, reprojection_error_px=0.4):
    rotation = np.eye(3, dtype=np.float64) if rotation is None else rotation
    translation = np.array([0.0, 0.0, 1.0], dtype=np.float64) if translation is None else translation
    return BoardPoseEstimate(
        R=np.array(rotation, dtype=np.float64),
        t=np.array(translation, dtype=np.float64),
        rvec=np.zeros((3, 1), dtype=np.float64),
        tvec=np.array(translation, dtype=np.float64).reshape(3, 1),
        reprojection_error_px=reprojection_error_px,
        corner_count=8,
        board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
    )


def test_estimate_intrinsics_returns_provisional_camera_model():
    intrinsics = estimate_intrinsics(1280, 720)
    assert intrinsics.valid is False
    assert intrinsics.method == "estimated"
    assert intrinsics.image_size == (1280, 720)
    assert intrinsics.camera_matrix[0, 2] == 640.0
    assert intrinsics.camera_matrix[1, 2] == 360.0
    np.testing.assert_array_equal(intrinsics.dist_coeffs, np.zeros((5, 1)))


def test_stereo_from_board_poses_recovers_relative_translation():
    pose_a = _pose(translation=np.array([0.0, 0.0, 1.0], dtype=np.float64))
    pose_b = _pose(translation=np.array([0.25, 0.0, 1.0], dtype=np.float64))

    rotation, translation = stereo_from_board_poses(pose_a, pose_b)

    np.testing.assert_allclose(rotation, np.eye(3), atol=1e-8)
    np.testing.assert_allclose(translation.reshape(3), np.array([0.25, 0.0, 0.0]), atol=1e-8)


def test_provisional_stereo_calibrate_aggregates_pose_pairs(monkeypatch):
    detections_a = [object(), object(), object()]
    detections_b = [object(), object(), object()]
    pose_sequence = [
        _pose(translation=np.array([0.0, 0.0, 1.0], dtype=np.float64), reprojection_error_px=0.3),
        _pose(translation=np.array([0.20, 0.0, 1.0], dtype=np.float64), reprojection_error_px=0.5),
        _pose(translation=np.array([0.0, 0.0, 1.0], dtype=np.float64), reprojection_error_px=0.4),
        _pose(translation=np.array([0.21, 0.0, 1.0], dtype=np.float64), reprojection_error_px=0.6),
        _pose(translation=np.array([0.0, 0.0, 1.0], dtype=np.float64), reprojection_error_px=0.5),
        _pose(translation=np.array([0.19, 0.0, 1.0], dtype=np.float64), reprojection_error_px=0.7),
    ]

    def fake_estimate(_detection, _intrinsics, board_spec=None):
        return pose_sequence.pop(0)

    monkeypatch.setattr("src.cv.stereo_calibration.estimate_charuco_board_pose", fake_estimate)

    intrinsics = estimate_intrinsics(640, 480)
    result = provisional_stereo_calibrate(
        detections_a,
        detections_b,
        intrinsics,
        intrinsics,
        board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
    )

    assert result.ok is True
    assert result.pairs_used == 3
    np.testing.assert_allclose(result.R, np.eye(3), atol=1e-8)
    np.testing.assert_allclose(result.T.reshape(3), np.array([0.20, 0.0, 0.0]), atol=1e-2)
    assert result.pose_consistency_px > 0
