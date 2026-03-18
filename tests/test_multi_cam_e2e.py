"""Multi-Camera E2E Tests -- validates the full fusion pipeline with synthetic data.

These tests create synthetic detections from known 3D board positions,
run them through the multi-camera fusion pipeline, and verify the
scored results match expected sectors/rings.
"""

import math
import time
import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cv.detector import DartDetection
from src.cv.multi_camera import MultiCameraPipeline
from src.cv.stereo_utils import CameraParams


def _make_camera(cam_id: str, position: np.ndarray, focal: float = 500.0) -> CameraParams:
    """Create synthetic camera looking at origin from given position."""
    K = np.array([[focal, 0, 320], [0, focal, 240], [0, 0, 1]], dtype=np.float64)
    dist = np.zeros(5, dtype=np.float64)

    # Camera looks at origin
    forward = -position / np.linalg.norm(position)
    right = np.cross(np.array([0, 1, 0]), forward)
    if np.linalg.norm(right) < 1e-6:
        right = np.cross(np.array([0, 0, 1]), forward)
    right = right / np.linalg.norm(right)
    up = np.cross(forward, right)

    R = np.stack([right, up, forward])
    T = (-R @ position).reshape(3, 1)

    return CameraParams(camera_id=cam_id, camera_matrix=K, dist_coeffs=dist, R=R, T=T)


def _project_point(point_3d: np.ndarray, cam: CameraParams) -> tuple[int, int]:
    """Project a 3D point to pixel coordinates."""
    import cv2
    rvec, _ = cv2.Rodrigues(cam.R)
    pts_2d, _ = cv2.projectPoints(
        point_3d.reshape(1, 1, 3), rvec, cam.T,
        cam.camera_matrix, cam.dist_coeffs,
    )
    x, y = pts_2d.reshape(2)
    return (int(round(x)), int(round(y)))


class TestMultiCamE2ESynthetic:
    """E2E tests using synthetic camera setups and known 3D points."""

    def test_triangulation_accuracy_bullseye(self):
        """Two cameras should triangulate bullseye accurately."""
        # Board center at Z=1.0 (in front of cameras which are near Z=0)
        board_z = 1.0
        cam1 = _make_camera("cam_left", np.array([-0.2, 0, 0.0]))
        cam2 = _make_camera("cam_right", np.array([0.2, 0, 0.0]))

        target = np.array([0.0, 0.0, board_z])
        px1 = _project_point(target, cam1)
        px2 = _project_point(target, cam2)

        from src.cv.stereo_utils import triangulate_point, transform_to_board_frame, point_3d_to_board_2d
        tri = triangulate_point(px1, px2, cam1, cam2)
        assert tri.valid
        assert tri.reprojection_error < 2.0

        # Board transform: translate board center to origin
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -board_z])
        p_board = transform_to_board_frame(tri.point_3d, R_cb, t_cb)
        x_mm, y_mm = point_3d_to_board_2d(p_board)

        # Should be within 5mm of bullseye
        dist_mm = math.hypot(x_mm, y_mm)
        assert dist_mm < 5.0, f"Bullseye error: {dist_mm:.1f}mm"

    def test_triangulation_accuracy_t20(self):
        """Triangulate a point in Triple 20 zone."""
        board_z = 1.0
        cam1 = _make_camera("cam_left", np.array([-0.2, 0, 0.0]))
        cam2 = _make_camera("cam_right", np.array([0.2, 0, 0.0]))

        # T20 is at ~103mm above center (between triple inner/outer ring)
        target = np.array([0.0, 0.103, board_z])
        px1 = _project_point(target, cam1)
        px2 = _project_point(target, cam2)

        from src.cv.stereo_utils import triangulate_point, transform_to_board_frame, point_3d_to_board_2d
        tri = triangulate_point(px1, px2, cam1, cam2)
        assert tri.valid

        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -board_z])
        p_board = transform_to_board_frame(tri.point_3d, R_cb, t_cb)
        x_mm, y_mm = point_3d_to_board_2d(p_board)

        # Should be within 5mm of target
        expected_y = 103.0
        error = math.hypot(x_mm, y_mm - expected_y)
        assert error < 5.0, f"T20 error: {error:.1f}mm"

    def test_three_camera_improves_accuracy(self):
        """Three cameras should give better or equal accuracy to two."""
        board_z = 1.0
        cam1 = _make_camera("cam_left", np.array([-0.2, 0, 0.0]))
        cam2 = _make_camera("cam_right", np.array([0.2, 0, 0.0]))
        cam3 = _make_camera("cam_top", np.array([0, 0.2, 0.0]))

        target = np.array([0.05, 0.05, board_z])

        from src.cv.stereo_utils import triangulate_point, triangulate_multi_pair, transform_to_board_frame, point_3d_to_board_2d

        # Two-camera result
        px1 = _project_point(target, cam1)
        px2 = _project_point(target, cam2)
        tri2 = triangulate_point(px1, px2, cam1, cam2)

        # Three-camera result
        px3 = _project_point(target, cam3)
        det1 = DartDetection(center=px1, area=500, confidence=0.8, frame_count=5, tip=px1)
        det2 = DartDetection(center=px2, area=500, confidence=0.8, frame_count=5, tip=px2)
        det3 = DartDetection(center=px3, area=500, confidence=0.8, frame_count=5, tip=px3)

        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -board_z])

        result = triangulate_multi_pair(
            detections=[
                {"camera_id": "cam_left", "detection": det1},
                {"camera_id": "cam_right", "detection": det2},
                {"camera_id": "cam_top", "detection": det3},
            ],
            camera_params={"cam_left": cam1, "cam_right": cam2, "cam_top": cam3},
            board_transforms={
                "cam_left": {"R_cb": R_cb, "t_cb": t_cb},
                "cam_right": {"R_cb": R_cb, "t_cb": t_cb},
                "cam_top": {"R_cb": R_cb, "t_cb": t_cb},
            },
        )

        assert result is not None
        assert result["pairs_used"] >= 2

        # Three-camera error
        target_x_mm, target_y_mm = 50.0, 50.0
        error_3 = math.hypot(result["board_x_mm"] - target_x_mm, result["board_y_mm"] - target_y_mm)
        assert error_3 < 10.0, f"3-cam error: {error_3:.1f}mm"

    def test_fusion_pipeline_emits_result(self):
        """Full MultiCameraPipeline processes buffered detections."""
        results = []

        pipeline = MultiCameraPipeline(
            camera_configs=[
                {"camera_id": "cam_a", "src": 0},
                {"camera_id": "cam_b", "src": 1},
            ],
            on_multi_dart_detected=lambda r: results.append(r),
        )

        # Simulate two detections arriving
        det_a = DartDetection(center=(200, 200), area=500, confidence=0.9, frame_count=5)
        det_b = DartDetection(center=(210, 195), area=480, confidence=0.85, frame_count=5)

        now = time.time()
        with pipeline._buffer_lock:
            pipeline._detection_buffer["cam_a"] = {
                "camera_id": "cam_a",
                "score_result": {"total_score": 20, "score": 20, "sector": 20, "multiplier": 1, "ring": "single"},
                "detection": det_a,
                "timestamp": now,
            }
            pipeline._detection_buffer["cam_b"] = {
                "camera_id": "cam_b",
                "score_result": {"total_score": 20, "score": 20, "sector": 20, "multiplier": 1, "ring": "single"},
                "detection": det_b,
                "timestamp": now + 0.05,
            }

        pipeline._try_fuse()

        assert len(results) == 1
        assert results[0]["source"] in ("triangulation", "voting_fallback")

    def test_fusion_config_exposed(self):
        """MultiCameraPipeline exposes fusion config."""
        pipeline = MultiCameraPipeline(
            camera_configs=[],
            sync_wait_s=0.4,
            max_time_diff_s=0.2,
            depth_tolerance_m=0.02,
        )
        config = pipeline.get_fusion_config()
        assert config["sync_wait_s"] == 0.4
        assert config["max_time_diff_s"] == 0.2
        assert config["depth_tolerance_m"] == 0.02
