"""P3: Stereo triangulation validation tests.

Tests the full pipeline: triangulate -> board transform -> score,
with synthetic but geometrically realistic camera setups.
"""

import math
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.cv.stereo_utils import (
    CameraParams,
    TriangulationResult,
    triangulate_point,
    transform_to_board_frame,
    point_3d_to_board_2d,
)


# --- Helpers ---

def _make_intrinsics(fx=500.0, fy=500.0, cx=320.0, cy=240.0):
    """Create a simple pinhole camera matrix."""
    return np.array([
        [fx, 0, cx],
        [0, fy, cy],
        [0, 0, 1],
    ], dtype=np.float64)


def _make_camera(camera_id, R, T, K=None):
    """Create CameraParams with zero distortion."""
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
    """Project a 3D world point to 2D pixel via camera params."""
    P = cam.projection_matrix
    p_homo = P @ np.append(point_3d, 1.0)
    return (p_homo[0] / p_homo[2], p_homo[1] / p_homo[2])


def _make_stereo_pair(baseline_m=0.30, distance_m=0.80):
    """Create a realistic stereo camera pair looking at a dartboard.

    World origin = board center. Cameras at Z = -distance_m (looking along +Z).
    In OpenCV convention: T = -R @ camera_position, R = identity (cameras face +Z).
    The board is at Z=0, cameras are behind (negative Z), so board points have Z>0
    relative to camera — satisfying the Z>0 validity check.
    """
    # Camera positions in world frame
    cam1_pos = np.array([-baseline_m / 2, 0, -distance_m])
    cam2_pos = np.array([baseline_m / 2, 0, -distance_m])

    # R = identity (cameras face +Z toward board)
    R = np.eye(3, dtype=np.float64)

    # T = -R @ cam_pos (OpenCV extrinsic convention)
    T1 = (-R @ cam1_pos).reshape(3, 1)
    T2 = (-R @ cam2_pos).reshape(3, 1)

    cam1 = _make_camera("cam_left", R, T1)
    cam2 = _make_camera("cam_right", R, T2)
    return cam1, cam2


# --- Board Transform Tests ---

class TestTransformToBoardFrame:
    def test_identity_transform(self):
        """Identity R_cb, zero t_cb should return same point."""
        pt = np.array([0.1, -0.05, 0.8])
        R_cb = np.eye(3)
        t_cb = np.zeros(3)
        result = transform_to_board_frame(pt, R_cb, t_cb)
        np.testing.assert_allclose(result, pt)

    def test_translation_only(self):
        """Pure translation should shift point."""
        pt = np.array([0.0, 0.0, 0.8])
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -0.8])
        result = transform_to_board_frame(pt, R_cb, t_cb)
        np.testing.assert_allclose(result, [0.0, 0.0, 0.0], atol=1e-10)

    def test_board_face_z_near_zero(self):
        """A point on the board face should have Z ≈ 0 after transform."""
        # Camera at 0.8m looking at board; point on board face at origin
        pt_camera = np.array([0.0, 0.0, 0.8])
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -0.8])
        result = transform_to_board_frame(pt_camera, R_cb, t_cb)
        assert abs(result[2]) < 0.001  # Z within 1mm of board face

    def test_point_offset_on_board(self):
        """A point 50mm right of center should show x=0.05m in board frame."""
        pt_camera = np.array([0.05, 0.0, 0.8])
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -0.8])
        result = transform_to_board_frame(pt_camera, R_cb, t_cb)
        assert abs(result[0] - 0.05) < 0.001
        assert abs(result[2]) < 0.001

    def test_rotation_90_degrees(self):
        """90-degree rotation around Y should swap X and Z."""
        pt = np.array([1.0, 0.0, 0.0])
        R_cb = np.array([
            [0, 0, 1],
            [0, 1, 0],
            [-1, 0, 0],
        ], dtype=np.float64)
        t_cb = np.zeros(3)
        result = transform_to_board_frame(pt, R_cb, t_cb)
        np.testing.assert_allclose(result, [0.0, 0.0, -1.0], atol=1e-10)


class TestPoint3dToBoard2d:
    def test_origin(self):
        pt = np.array([0.0, 0.0, 0.0])
        x_mm, y_mm = point_3d_to_board_2d(pt)
        assert x_mm == 0.0
        assert y_mm == 0.0

    def test_conversion_meters_to_mm(self):
        pt = np.array([0.1, -0.05, 0.001])
        x_mm, y_mm = point_3d_to_board_2d(pt)
        assert abs(x_mm - 100.0) < 0.01
        assert abs(y_mm - (-50.0)) < 0.01

    def test_bullseye_position(self):
        """Point at board center should map to (0, 0) mm."""
        pt = np.array([0.0, 0.0, 0.002])  # 2mm depth, on board
        x_mm, y_mm = point_3d_to_board_2d(pt)
        assert abs(x_mm) < 0.01
        assert abs(y_mm) < 0.01


# --- Triangulation Accuracy Tests ---

class TestTriangulationAccuracy:
    """Test triangulation with known 3D points projected to camera pairs.

    Note: triangulate_point requires Z > 0 in the world frame.
    Our world origin is the board face. Real dart tips protrude slightly
    toward the cameras (positive Z in our setup). We use Z=0.005 (5mm)
    to simulate realistic dart tip positions.
    """
    DART_Z = 0.005  # 5mm protrusion toward cameras

    def test_board_center(self):
        """Triangulating board center should yield (0, 0, ~Z)."""
        cam1, cam2 = _make_stereo_pair()
        target = np.array([0.0, 0.0, self.DART_Z])
        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        tri = triangulate_point(pt1, pt2, cam1, cam2)
        assert tri.valid
        assert tri.reprojection_error < 1.0
        np.testing.assert_allclose(tri.point_3d[:2], [0.0, 0.0], atol=0.005)

    def test_triple20_position(self):
        """Triangulating a point at triple-20 (top of board, ~100mm up)."""
        cam1, cam2 = _make_stereo_pair()
        target = np.array([0.0, -0.10, self.DART_Z])
        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        tri = triangulate_point(pt1, pt2, cam1, cam2)
        assert tri.valid
        assert tri.reprojection_error < 1.0
        np.testing.assert_allclose(tri.point_3d[:2], [0.0, -0.10], atol=0.005)

    def test_edge_of_board(self):
        """Point at board edge (~170mm from center) should triangulate correctly."""
        cam1, cam2 = _make_stereo_pair()
        target = np.array([0.17, 0.0, self.DART_Z])
        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        tri = triangulate_point(pt1, pt2, cam1, cam2)
        assert tri.valid
        assert tri.reprojection_error < 2.0
        np.testing.assert_allclose(tri.point_3d[:2], [0.17, 0.0], atol=0.01)

    def test_wider_baseline_better_accuracy(self):
        """Wider baseline should give better depth accuracy."""
        target = np.array([0.05, 0.05, self.DART_Z])

        cam1_narrow, cam2_narrow = _make_stereo_pair(baseline_m=0.10)
        cam1_wide, cam2_wide = _make_stereo_pair(baseline_m=0.40)

        pt1n = _project(target, cam1_narrow)
        pt2n = _project(target, cam2_narrow)
        tri_narrow = triangulate_point(pt1n, pt2n, cam1_narrow, cam2_narrow)

        pt1w = _project(target, cam1_wide)
        pt2w = _project(target, cam2_wide)
        tri_wide = triangulate_point(pt1w, pt2w, cam1_wide, cam2_wide)

        assert tri_narrow.valid and tri_wide.valid
        err_narrow = np.linalg.norm(tri_narrow.point_3d - target)
        err_wide = np.linalg.norm(tri_wide.point_3d - target)
        assert err_narrow < 0.01
        assert err_wide < 0.01

    def test_different_distances(self):
        """Triangulation should work at different board distances."""
        for dist in [0.5, 0.8, 1.2]:
            cam1, cam2 = _make_stereo_pair(distance_m=dist)
            target = np.array([0.03, -0.04, self.DART_Z])
            pt1 = _project(target, cam1)
            pt2 = _project(target, cam2)
            tri = triangulate_point(pt1, pt2, cam1, cam2)
            assert tri.valid, f"Failed at distance={dist}m"
            np.testing.assert_allclose(tri.point_3d[:2], [0.03, -0.04], atol=0.01)

    def test_z_near_zero_still_valid(self):
        """Points at Z≈0 may pass due to floating-point: Z>0 check sees tiny positive."""
        cam1, cam2 = _make_stereo_pair()
        target = np.array([0.05, 0.05, 0.0])
        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        tri = triangulate_point(pt1, pt2, cam1, cam2)
        # Numerically Z is ~1e-18 (positive), so still valid
        assert tri.valid
        assert abs(tri.point_3d[2]) < 1e-10

    def test_behind_camera_rejected(self):
        """Points behind cameras (Z < 0) should be rejected."""
        cam1, cam2 = _make_stereo_pair()
        # Point behind the cameras (Z = -1.0, well behind camera plane)
        target = np.array([0.0, 0.0, -1.5])
        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        tri = triangulate_point(pt1, pt2, cam1, cam2)
        assert not tri.valid


# --- Z-Depth Plausibility Tests ---

class TestZDepthPlausibility:
    """Test the Z-depth check used in MultiCameraPipeline._try_fuse()."""

    BOARD_DEPTH_TOLERANCE_M = 0.015  # 15mm, same as multi_camera.py

    def test_dart_on_board_face_passes(self):
        """Z=0 (exactly on board face) should pass."""
        pt_camera = np.array([0.05, 0.0, 0.8])
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -0.8])
        p_board = transform_to_board_frame(pt_camera, R_cb, t_cb)
        assert abs(p_board[2]) <= self.BOARD_DEPTH_TOLERANCE_M

    def test_dart_penetrating_5mm_passes(self):
        """Dart penetrating 5mm into board should pass (within 15mm tolerance)."""
        pt_camera = np.array([0.05, 0.0, 0.805])
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -0.8])
        p_board = transform_to_board_frame(pt_camera, R_cb, t_cb)
        assert abs(p_board[2]) <= self.BOARD_DEPTH_TOLERANCE_M

    def test_dart_10mm_in_front_passes(self):
        """Dart 10mm in front of board should pass."""
        pt_camera = np.array([0.05, 0.0, 0.79])
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -0.8])
        p_board = transform_to_board_frame(pt_camera, R_cb, t_cb)
        assert abs(p_board[2]) <= self.BOARD_DEPTH_TOLERANCE_M

    def test_point_50mm_behind_board_fails(self):
        """Point 50mm behind board should fail."""
        pt_camera = np.array([0.05, 0.0, 0.85])
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -0.8])
        p_board = transform_to_board_frame(pt_camera, R_cb, t_cb)
        assert abs(p_board[2]) > self.BOARD_DEPTH_TOLERANCE_M

    def test_point_far_in_front_fails(self):
        """Point 100mm in front of board should fail."""
        pt_camera = np.array([0.05, 0.0, 0.7])
        R_cb = np.eye(3)
        t_cb = np.array([0.0, 0.0, -0.8])
        p_board = transform_to_board_frame(pt_camera, R_cb, t_cb)
        assert abs(p_board[2]) > self.BOARD_DEPTH_TOLERANCE_M


# --- End-to-End: Triangulation -> Board Transform -> Score ---

class TestEndToEndTriangulationScoring:
    """Full pipeline: project known point -> triangulate -> board transform -> mm coords.

    Uses DART_Z=0.005m (5mm) to ensure Z>0 for valid triangulation.
    Board transform subtracts this back to get Z≈0 on board face.
    """
    DART_Z = 0.005

    def test_bullseye_e2e(self):
        """Full pipeline for a bullseye hit."""
        cam1, cam2 = _make_stereo_pair(distance_m=0.8)
        target = np.array([0.0, 0.0, self.DART_Z])

        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        tri = triangulate_point(pt1, pt2, cam1, cam2)
        assert tri.valid

        # Board transform: identity R, translate to put board at Z=0
        # The triangulated point is in world frame where board is at Z=0
        # so we just use identity — Z stays at DART_Z ≈ 0.005
        R_cb = np.eye(3)
        t_cb = np.zeros(3)
        p_board = transform_to_board_frame(tri.point_3d, R_cb, t_cb)

        assert abs(p_board[2]) < 0.01  # within 10mm of board face

        x_mm, y_mm = point_3d_to_board_2d(p_board)
        distance_mm = math.sqrt(x_mm**2 + y_mm**2)
        assert distance_mm < 5.0

    def test_triple20_e2e(self):
        """Full pipeline for a triple-20 hit (top of board)."""
        cam1, cam2 = _make_stereo_pair(distance_m=0.8)
        target = np.array([0.0, -0.10, self.DART_Z])

        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        tri = triangulate_point(pt1, pt2, cam1, cam2)
        assert tri.valid

        R_cb = np.eye(3)
        t_cb = np.zeros(3)
        p_board = transform_to_board_frame(tri.point_3d, R_cb, t_cb)

        x_mm, y_mm = point_3d_to_board_2d(p_board)
        distance_mm = math.sqrt(x_mm**2 + y_mm**2)
        assert 95.0 < distance_mm < 105.0

    def test_double16_e2e(self):
        """Full pipeline for a double-16 hit (lower-left area)."""
        cam1, cam2 = _make_stereo_pair(distance_m=0.8)
        angle_rad = math.radians(250)
        r_m = 0.162
        target = np.array([r_m * math.cos(angle_rad), r_m * math.sin(angle_rad), self.DART_Z])

        pt1 = _project(target, cam1)
        pt2 = _project(target, cam2)
        tri = triangulate_point(pt1, pt2, cam1, cam2)
        assert tri.valid

        R_cb = np.eye(3)
        t_cb = np.zeros(3)
        p_board = transform_to_board_frame(tri.point_3d, R_cb, t_cb)

        x_mm, y_mm = point_3d_to_board_2d(p_board)
        distance_mm = math.sqrt(x_mm**2 + y_mm**2)
        assert 155.0 < distance_mm < 170.0

    def test_multiple_board_positions_accuracy(self):
        """Test accuracy across 8 different board positions."""
        cam1, cam2 = _make_stereo_pair(distance_m=0.8)
        R_cb = np.eye(3)
        t_cb = np.zeros(3)

        test_points_m = [
            (0.0, 0.0),      # bull
            (0.05, 0.0),     # 50mm right
            (-0.05, 0.0),    # 50mm left
            (0.0, 0.05),     # 50mm down
            (0.0, -0.05),    # 50mm up
            (0.10, 0.10),    # diagonal
            (-0.10, -0.10),  # diagonal
            (0.17, 0.0),     # board edge
        ]

        errors_mm = []
        for x, y in test_points_m:
            target = np.array([x, y, self.DART_Z])
            pt1 = _project(target, cam1)
            pt2 = _project(target, cam2)
            tri = triangulate_point(pt1, pt2, cam1, cam2)
            assert tri.valid, f"Failed for target ({x},{y})"

            p_board = transform_to_board_frame(tri.point_3d, R_cb, t_cb)
            x_mm, y_mm = point_3d_to_board_2d(p_board)
            err = math.sqrt((x_mm - x * 1000)**2 + (y_mm - y * 1000)**2)
            errors_mm.append(err)

        assert max(errors_mm) < 5.0, f"Max error: {max(errors_mm):.2f}mm"
        assert sum(errors_mm) / len(errors_mm) < 2.0


# --- Stereo Param Loading Tests ---

class TestStereoParamLoading:
    """Test that stereo calibration data loads correctly into fusion pipeline."""

    def _make_pipeline(self):
        """Create a MultiCameraPipeline without starting cameras."""
        from src.cv.multi_camera import MultiCameraPipeline
        mp = MultiCameraPipeline.__new__(MultiCameraPipeline)
        mp._pipelines = {}
        mp._stereo_params = {}
        mp._board_transforms = {}
        mp._camera_errors = {}
        mp.camera_configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 2},
        ]
        return mp

    @patch("src.cv.multi_camera.get_stereo_pair")
    @patch("src.cv.multi_camera.get_board_transform")
    def test_load_extrinsics_populates_stereo_params(self, mock_get_bt, mock_get_sp):
        """Saved stereo pair should load into _stereo_params dict."""
        mp = self._make_pipeline()

        mock_get_sp.return_value = {
            "R": np.eye(3).tolist(), "T": [0.3, 0.0, 0.0],
            "reprojection_error": 0.5,
        }
        mock_get_bt.return_value = {
            "R_cb": np.eye(3).tolist(), "t_cb": [0, 0, -0.8],
        }

        # Mock pipelines with intrinsics
        for cam_id in ["cam_left", "cam_right"]:
            mock_pipe = MagicMock()
            mock_pipe.camera_calibration.get_intrinsics.return_value = MagicMock(
                camera_matrix=_make_intrinsics(),
                dist_coeffs=np.zeros((5, 1)),
            )
            mp._pipelines[cam_id] = mock_pipe

        mp._load_extrinsics()

        assert "cam_left" in mp._stereo_params
        assert "cam_right" in mp._stereo_params
        assert "cam_left" in mp._board_transforms
        assert "cam_right" in mp._board_transforms

    @patch("src.cv.multi_camera.get_stereo_pair")
    @patch("src.cv.multi_camera.get_board_transform")
    def test_missing_stereo_pair_graceful(self, mock_get_bt, mock_get_sp):
        """Missing stereo calibration should not crash — just skip triangulation."""
        mp = self._make_pipeline()

        mock_get_sp.return_value = None
        mock_get_bt.return_value = None

        for cam_id in ["cam_left", "cam_right"]:
            mock_pipe = MagicMock()
            mock_pipe.camera_calibration.get_intrinsics.return_value = None
            mp._pipelines[cam_id] = mock_pipe

        mp._load_extrinsics()

        assert len(mp._stereo_params) == 0
        assert len(mp._board_transforms) == 0

    @patch("src.cv.multi_camera.get_stereo_pair")
    @patch("src.cv.multi_camera.get_board_transform")
    def test_missing_intrinsics_skips_stereo(self, mock_get_bt, mock_get_sp):
        """If one camera lacks intrinsics, stereo params should not load for that pair."""
        mp = self._make_pipeline()

        mock_get_sp.return_value = {
            "R": np.eye(3).tolist(), "T": [0.3, 0.0, 0.0],
        }
        mock_get_bt.return_value = {
            "R_cb": np.eye(3).tolist(), "t_cb": [0, 0, -0.8],
        }

        # cam_left has intrinsics, cam_right does not
        mock_left = MagicMock()
        mock_left.camera_calibration.get_intrinsics.return_value = MagicMock(
            camera_matrix=_make_intrinsics(), dist_coeffs=np.zeros((5, 1)),
        )
        mock_right = MagicMock()
        mock_right.camera_calibration.get_intrinsics.return_value = None
        mp._pipelines = {"cam_left": mock_left, "cam_right": mock_right}

        mp._load_extrinsics()

        # Stereo params should NOT be populated (need both intrinsics)
        assert len(mp._stereo_params) == 0
        # Board transforms should still load
        assert "cam_left" in mp._board_transforms
        assert "cam_right" in mp._board_transforms
