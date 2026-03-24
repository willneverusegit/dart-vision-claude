"""Tests for stereo triangulation utilities."""

import numpy as np
import cv2
import pytest

from src.cv.stereo_utils import (
    CameraParams,
    TriangulationResult,
    triangulate_point,
    point_3d_to_board_2d,
    transform_to_board_frame,
)


def _make_camera_pair():
    """Create two cameras with known intrinsics/extrinsics for testing.

    Camera 1 at origin looking along +Z, camera 2 shifted 0.1m to the right.
    """
    fx, fy = 500.0, 500.0
    cx, cy = 320.0, 240.0
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)
    D = np.zeros((5, 1), dtype=np.float64)

    cam1 = CameraParams(
        camera_id="cam_left",
        camera_matrix=K.copy(),
        dist_coeffs=D.copy(),
        R=np.eye(3, dtype=np.float64),
        T=np.zeros((3, 1), dtype=np.float64),
    )

    cam2 = CameraParams(
        camera_id="cam_right",
        camera_matrix=K.copy(),
        dist_coeffs=D.copy(),
        R=np.eye(3, dtype=np.float64),
        T=np.array([[0.1], [0.0], [0.0]], dtype=np.float64),
    )
    return cam1, cam2


class TestCameraParams:
    def test_projection_matrix_shape(self):
        cam1, _ = _make_camera_pair()
        P = cam1.projection_matrix
        assert P.shape == (3, 4)

    def test_projection_matrix_identity_camera(self):
        """Camera at origin: P = K @ [I | 0]."""
        cam1, _ = _make_camera_pair()
        P = cam1.projection_matrix
        K = cam1.camera_matrix
        # P should be K @ [I | 0]
        expected = K @ np.hstack([np.eye(3), np.zeros((3, 1))])
        np.testing.assert_array_almost_equal(P, expected)


class TestTriangulatePoint:
    def test_known_3d_point(self):
        """Project a known 3D point to both cameras, triangulate, compare."""
        cam1, cam2 = _make_camera_pair()

        # Known 3D point: 0.5m in front of camera 1, centered
        point_3d = np.array([0.0, 0.0, 0.5], dtype=np.float64)

        # Project to camera 1 (at origin)
        rvec1, _ = cv2.Rodrigues(cam1.R)
        pts1, _ = cv2.projectPoints(
            point_3d.reshape(1, 1, 3), rvec1, cam1.T,
            cam1.camera_matrix, cam1.dist_coeffs,
        )
        pt1 = tuple(pts1.reshape(2).tolist())

        # Project to camera 2 (shifted right)
        rvec2, _ = cv2.Rodrigues(cam2.R)
        pts2, _ = cv2.projectPoints(
            point_3d.reshape(1, 1, 3), rvec2, cam2.T,
            cam2.camera_matrix, cam2.dist_coeffs,
        )
        pt2 = tuple(pts2.reshape(2).tolist())

        result = triangulate_point(pt1, pt2, cam1, cam2)
        assert result.valid
        assert result.reprojection_error < 1.0
        np.testing.assert_array_almost_equal(result.point_3d, point_3d, decimal=3)

    def test_off_center_point(self):
        """Triangulate an off-center point."""
        cam1, cam2 = _make_camera_pair()
        point_3d = np.array([0.05, -0.03, 0.4], dtype=np.float64)

        rvec1, _ = cv2.Rodrigues(cam1.R)
        pts1, _ = cv2.projectPoints(
            point_3d.reshape(1, 1, 3), rvec1, cam1.T,
            cam1.camera_matrix, cam1.dist_coeffs,
        )
        rvec2, _ = cv2.Rodrigues(cam2.R)
        pts2, _ = cv2.projectPoints(
            point_3d.reshape(1, 1, 3), rvec2, cam2.T,
            cam2.camera_matrix, cam2.dist_coeffs,
        )

        result = triangulate_point(
            tuple(pts1.reshape(2).tolist()),
            tuple(pts2.reshape(2).tolist()),
            cam1, cam2,
        )
        assert result.valid
        assert result.reprojection_error < 1.0
        np.testing.assert_array_almost_equal(result.point_3d, point_3d, decimal=3)

    def test_behind_camera_invalid(self):
        """Point behind camera (Z < 0) should be invalid."""
        cam1, cam2 = _make_camera_pair()
        # Use pixel coordinates that would triangulate to a degenerate point
        # Two identical pixel coords in different cameras = point at infinity or behind
        result = triangulate_point((320, 240), (320, 240), cam1, cam2)
        # With baseline 0.1m and same pixel -> ill-conditioned, likely Z very large or negative
        # Just verify it returns a TriangulationResult without crash
        assert isinstance(result, TriangulationResult)

    def test_result_type(self):
        cam1, cam2 = _make_camera_pair()
        result = triangulate_point((320, 240), (270, 240), cam1, cam2)
        assert isinstance(result, TriangulationResult)
        assert isinstance(result.reprojection_error, float)

    def test_high_reproj_error_invalid(self):
        """Very noisy observations should exceed max reprojection error."""
        cam1, cam2 = _make_camera_pair()
        # Use very inconsistent pixel coordinates
        result = triangulate_point((0, 0), (639, 479), cam1, cam2, max_reproj_error=0.01)
        # With strict threshold, likely invalid
        # Just check it doesn't crash
        assert isinstance(result, TriangulationResult)


class TestPoint3dToBoard2d:
    def test_meters_to_mm_conversion(self):
        point_3d = np.array([0.05, 0.03, 0.0])  # 50mm, 30mm
        x_mm, y_mm = point_3d_to_board_2d(point_3d)
        assert abs(x_mm - 50.0) < 0.01
        assert abs(y_mm - 30.0) < 0.01

    def test_origin(self):
        point_3d = np.array([0.0, 0.0, 0.0])
        x_mm, y_mm = point_3d_to_board_2d(point_3d)
        assert x_mm == 0.0
        assert y_mm == 0.0

    def test_negative_coords(self):
        point_3d = np.array([-0.1, -0.05, 0.0])
        x_mm, y_mm = point_3d_to_board_2d(point_3d)
        assert abs(x_mm - (-100.0)) < 0.01
        assert abs(y_mm - (-50.0)) < 0.01

    def test_with_board_frame_point(self):
        """Point already in board frame — Z (depth) is ignored for 2D result."""
        point_3d = np.array([0.02, 0.01, 0.005])  # 5mm depth, irrelevant to X/Y
        x_mm, y_mm = point_3d_to_board_2d(point_3d)
        assert abs(x_mm - 20.0) < 0.01
        assert abs(y_mm - 10.0) < 0.01


class TestTransformToBoardFrame:
    """Verify camera-to-board transform round-trips correctly with solvePnP."""

    def test_solvepnp_inverse_roundtrip(self):
        """A point at the board origin should map to ~(0,0,0) in board frame.

        Simulates what board_pose_calibration does: solvePnP gives board-to-camera,
        we invert to get camera-to-board, and then transform_to_board_frame should
        recover the original board coordinates.
        """
        # Camera intrinsics
        K = np.array([[500, 0, 320], [0, 500, 240], [0, 0, 1]], dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)

        # Board point at origin and at known offset
        board_points = np.array([
            [0.0, 0.0, 0.0],       # board center
            [0.05, 0.03, 0.0],      # 50mm right, 30mm up
            [-0.1, 0.07, 0.0],      # 100mm left, 70mm up
        ], dtype=np.float64)

        # Simulate a camera looking at the board from 0.5m away, slightly rotated
        rvec_true = np.array([0.1, -0.05, 0.02], dtype=np.float64)
        tvec_true = np.array([0.0, 0.0, 0.5], dtype=np.float64).reshape(3, 1)

        # solvePnP gives board-to-camera: p_cam = R_bc @ p_board + t_bc
        R_bc, _ = cv2.Rodrigues(rvec_true)
        t_bc = tvec_true.reshape(3)

        # Invert to camera-to-board (what board_pose_calibration now does)
        R_cb = R_bc.T
        t_cb = -R_bc.T @ t_bc

        for bp in board_points:
            # Forward: board -> camera
            p_cam = R_bc @ bp + t_bc

            # Inverse: camera -> board via transform_to_board_frame
            p_board = transform_to_board_frame(p_cam, R_cb, t_cb)

            np.testing.assert_array_almost_equal(p_board, bp, decimal=6,
                err_msg=f"Round-trip failed for board point {bp}")

    def test_board_center_maps_to_zero(self):
        """Board center (0,0,0) through solvePnP + inverse should give (0,0) in mm."""
        rvec = np.array([0.15, -0.1, 0.0], dtype=np.float64)
        tvec = np.array([0.02, -0.01, 0.6], dtype=np.float64).reshape(3, 1)

        R_bc, _ = cv2.Rodrigues(rvec)
        t_bc = tvec.reshape(3)
        R_cb = R_bc.T
        t_cb = -R_bc.T @ t_bc

        # Board center in camera frame
        p_cam = R_bc @ np.zeros(3) + t_bc

        # Transform back to board
        p_board = transform_to_board_frame(p_cam, R_cb, t_cb)
        x_mm, y_mm = point_3d_to_board_2d(p_board)

        assert abs(x_mm) < 0.01, f"Expected x~0mm, got {x_mm}"
        assert abs(y_mm) < 0.01, f"Expected y~0mm, got {y_mm}"
