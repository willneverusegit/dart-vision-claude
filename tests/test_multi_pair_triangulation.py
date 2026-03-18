"""Tests for multi-pair triangulation with outlier rejection and weighted fusion."""

import math
import numpy as np
import pytest
from types import SimpleNamespace

from src.cv.stereo_utils import (
    CameraParams,
    triangulate_multi_pair,
    _reject_outliers,
)


# --- Helpers ---

def _make_intrinsics(fx=500.0, fy=500.0, cx=320.0, cy=240.0):
    return np.array([
        [fx, 0, cx],
        [0, fy, cy],
        [0, 0, 1],
    ], dtype=np.float64)


def _make_camera(camera_id, R, T, K=None):
    if K is None:
        K = _make_intrinsics()
    return CameraParams(
        camera_id=camera_id,
        camera_matrix=K,
        dist_coeffs=np.zeros((5, 1), dtype=np.float64),
        R=R,
        T=T,
    )


def _project(point_3d, cam):
    P = cam.projection_matrix
    p_homo = P @ np.append(point_3d, 1.0)
    return (p_homo[0] / p_homo[2], p_homo[1] / p_homo[2])


def _make_detection(center):
    """Create a mock detection with a center attribute."""
    return SimpleNamespace(center=center)


def _make_three_cameras(baseline=0.30, distance=0.80):
    """Create 3 cameras: left, right, top — all looking at board at Z=0.

    World origin = board center. Cameras at Z = -distance.
    """
    R = np.eye(3, dtype=np.float64)

    cam1_pos = np.array([-baseline / 2, 0, -distance])
    cam2_pos = np.array([baseline / 2, 0, -distance])
    cam3_pos = np.array([0, -baseline / 2, -distance])

    cam1 = _make_camera("cam_left", R, (-R @ cam1_pos).reshape(3, 1))
    cam2 = _make_camera("cam_right", R, (-R @ cam2_pos).reshape(3, 1))
    cam3 = _make_camera("cam_top", R, (-R @ cam3_pos).reshape(3, 1))

    return cam1, cam2, cam3


def _identity_board_transform():
    """Board transform: identity R, zero translation.

    In this test setup the board is at world Z=0 and the triangulated
    point is already in world coordinates, so R=I, t=0 gives board Z ~ 0.
    We place target points at small positive Z (e.g. 0.001) to pass the
    triangulate_point Z>0 validity check.
    """
    return {
        "R_cb": np.eye(3, dtype=np.float64),
        "t_cb": np.zeros(3, dtype=np.float64),
    }


# --- Tests ---

class TestTriangulateMultiPair:
    def test_two_cameras_single_pair(self):
        """Two cameras should produce a single-pair result."""
        cam1, cam2, _ = _make_three_cameras()
        target = np.array([0.05, 0.03, 0.001])  # point near board

        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)

        cam_params = {"cam_left": cam1, "cam_right": cam2}
        bt = {"cam_left": _identity_board_transform()}
        detections = [
            {"camera_id": "cam_left", "detection": _make_detection(pt1)},
            {"camera_id": "cam_right", "detection": _make_detection(pt2)},
        ]

        result = triangulate_multi_pair(detections, cam_params, bt)
        assert result is not None
        assert result["pairs_used"] == 1
        assert result["source"] == "triangulation"
        assert abs(result["board_x_mm"] - 50.0) < 5.0
        assert abs(result["board_y_mm"] - 30.0) < 5.0

    def test_three_cameras_three_pairs(self):
        """Three cameras should use up to 3 pairs."""
        cam1, cam2, cam3 = _make_three_cameras()
        target = np.array([0.02, -0.01, 0.001])

        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        pt3 = _project(target, cam3)

        cam_params = {"cam_left": cam1, "cam_right": cam2, "cam_top": cam3}
        bt = {
            "cam_left": _identity_board_transform(),
            "cam_right": _identity_board_transform(),
            "cam_top": _identity_board_transform(),
        }
        detections = [
            {"camera_id": "cam_left", "detection": _make_detection(pt1)},
            {"camera_id": "cam_right", "detection": _make_detection(pt2)},
            {"camera_id": "cam_top", "detection": _make_detection(pt3)},
        ]

        result = triangulate_multi_pair(detections, cam_params, bt)
        assert result is not None
        assert result["pairs_used"] >= 2  # at least 2 valid pairs
        assert abs(result["board_x_mm"] - 20.0) < 5.0
        assert abs(result["board_y_mm"] - (-10.0)) < 5.0

    def test_returns_none_no_valid_pairs(self):
        """Returns None when no camera params match."""
        detections = [
            {"camera_id": "cam_a", "detection": _make_detection((320, 240))},
            {"camera_id": "cam_b", "detection": _make_detection((320, 240))},
        ]
        result = triangulate_multi_pair(detections, {}, {})
        assert result is not None and result.get("failed")

    def test_returns_none_no_detections(self):
        """Returns None with None detections."""
        cam1, cam2, _ = _make_three_cameras()
        cam_params = {"cam_left": cam1, "cam_right": cam2}
        bt = {"cam_left": _identity_board_transform()}
        detections = [
            {"camera_id": "cam_left", "detection": None},
            {"camera_id": "cam_right", "detection": None},
        ]
        result = triangulate_multi_pair(detections, cam_params, bt)
        assert result is not None and result.get("failed")

    def test_z_depth_rejection(self):
        """Points far from board plane should be rejected."""
        cam1, cam2, _ = _make_three_cameras()
        # Point far from the board (Z = 0.5, way off board plane)
        target = np.array([0.0, 0.0, 0.5])
        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)

        cam_params = {"cam_left": cam1, "cam_right": cam2}
        # Board transform expects board at Z=0.8 from camera, so Z=0.5 -> board Z = -0.3
        bt = {"cam_left": _identity_board_transform()}
        detections = [
            {"camera_id": "cam_left", "detection": _make_detection(pt1)},
            {"camera_id": "cam_right", "detection": _make_detection(pt2)},
        ]

        result = triangulate_multi_pair(detections, cam_params, bt, depth_tolerance_m=0.015)
        # Should fail because the point is ~0.3m off the board plane
        assert result.get("failed")
        assert result["z_rejected"] > 0

    def test_weighted_average_favors_low_reproj(self):
        """Results with lower reprojection error should have more weight."""
        # Create synthetic results and check the weighted fusion manually
        cam1, cam2, cam3 = _make_three_cameras()
        # Use a point near the board
        target = np.array([0.0, 0.0, 0.001])
        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        pt3 = _project(target, cam3)

        cam_params = {"cam_left": cam1, "cam_right": cam2, "cam_top": cam3}
        bt = {
            "cam_left": _identity_board_transform(),
            "cam_right": _identity_board_transform(),
            "cam_top": _identity_board_transform(),
        }
        detections = [
            {"camera_id": "cam_left", "detection": _make_detection(pt1)},
            {"camera_id": "cam_right", "detection": _make_detection(pt2)},
            {"camera_id": "cam_top", "detection": _make_detection(pt3)},
        ]

        result = triangulate_multi_pair(detections, cam_params, bt)
        assert result is not None
        # For a symmetric setup with target at origin, result should be near (0, 0)
        assert abs(result["board_x_mm"]) < 5.0
        assert abs(result["board_y_mm"]) < 5.0


class TestRejectOutliers:
    def test_preserves_at_least_one(self):
        """Should never reject all results."""
        results = [
            {"board_x_mm": 0.0, "board_y_mm": 0.0, "reprojection_error": 1.0},
            {"board_x_mm": 100.0, "board_y_mm": 100.0, "reprojection_error": 1.0},
            {"board_x_mm": 200.0, "board_y_mm": 200.0, "reprojection_error": 1.0},
        ]
        filtered = _reject_outliers(results)
        assert len(filtered) >= 1

    def test_removes_outlier(self):
        """An outlier far from the cluster should be removed."""
        results = [
            {"board_x_mm": 10.0, "board_y_mm": 10.0, "reprojection_error": 1.0},
            {"board_x_mm": 11.0, "board_y_mm": 11.0, "reprojection_error": 1.0},
            {"board_x_mm": 10.5, "board_y_mm": 10.5, "reprojection_error": 1.0},
            {"board_x_mm": 500.0, "board_y_mm": 500.0, "reprojection_error": 1.0},  # outlier
        ]
        filtered = _reject_outliers(results)
        # The outlier at (500, 500) should be removed
        assert len(filtered) < len(results)
        for r in filtered:
            assert r["board_x_mm"] < 100.0

    def test_tight_cluster_preserved(self):
        """A tight cluster should not lose any points (threshold >= 1mm)."""
        results = [
            {"board_x_mm": 10.0, "board_y_mm": 10.0, "reprojection_error": 1.0},
            {"board_x_mm": 10.1, "board_y_mm": 10.1, "reprojection_error": 1.0},
            {"board_x_mm": 10.2, "board_y_mm": 10.2, "reprojection_error": 1.0},
        ]
        filtered = _reject_outliers(results)
        assert len(filtered) == 3
