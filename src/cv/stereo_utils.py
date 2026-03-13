"""Stereo triangulation and camera parameter structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import cv2
import numpy as np


@dataclass
class CameraParams:
    """Complete camera model: intrinsics + extrinsics."""
    camera_id: str
    camera_matrix: np.ndarray      # 3x3
    dist_coeffs: np.ndarray        # Nx1
    R: np.ndarray                  # 3x3 rotation (world -> camera)
    T: np.ndarray                  # 3x1 translation (world -> camera)

    @property
    def projection_matrix(self) -> np.ndarray:
        """3x4 projection matrix P = K @ [R | T]."""
        RT = np.hstack([self.R, self.T.reshape(3, 1)])
        return self.camera_matrix @ RT


class TriangulationResult(NamedTuple):
    point_3d: np.ndarray    # (X, Y, Z) in world/board coordinate system
    reprojection_error: float
    valid: bool


def triangulate_point(
    pt1: tuple[float, float],
    pt2: tuple[float, float],
    cam1: CameraParams,
    cam2: CameraParams,
    max_reproj_error: float = 5.0,
) -> TriangulationResult:
    """Triangulate a 3D point from two 2D observations.

    Args:
        pt1: (x, y) pixel coordinate in camera 1.
        pt2: (x, y) pixel coordinate in camera 2.
        cam1: Camera parameters for camera 1.
        cam2: Camera parameters for camera 2.
        max_reproj_error: Maximum reprojection error (px) to consider valid.

    Returns:
        TriangulationResult with 3D point and quality metrics.
    """
    # Undistort points first
    pt1_undist = cv2.undistortPoints(
        np.array([[pt1]], dtype=np.float64),
        cam1.camera_matrix, cam1.dist_coeffs,
        P=cam1.camera_matrix,
    ).reshape(2)

    pt2_undist = cv2.undistortPoints(
        np.array([[pt2]], dtype=np.float64),
        cam2.camera_matrix, cam2.dist_coeffs,
        P=cam2.camera_matrix,
    ).reshape(2)

    P1 = cam1.projection_matrix
    P2 = cam2.projection_matrix

    # Triangulate
    pts_4d = cv2.triangulatePoints(
        P1, P2,
        pt1_undist.reshape(2, 1),
        pt2_undist.reshape(2, 1),
    )

    # Convert from homogeneous
    w = pts_4d[3, 0]
    if abs(w) < 1e-10:
        return TriangulationResult(np.zeros(3), float("inf"), False)
    point_3d = (pts_4d[:3, 0] / w).astype(np.float64)

    # Reprojection error check
    reproj_1 = _reproject(point_3d, cam1)
    reproj_2 = _reproject(point_3d, cam2)
    err_1 = np.linalg.norm(reproj_1 - np.array(pt1))
    err_2 = np.linalg.norm(reproj_2 - np.array(pt2))
    avg_error = float((err_1 + err_2) / 2.0)

    valid = avg_error <= max_reproj_error and point_3d[2] > 0  # Z > 0 = in front of cameras

    return TriangulationResult(point_3d, avg_error, valid)


def _reproject(point_3d: np.ndarray, cam: CameraParams) -> np.ndarray:
    """Reproject a 3D point to 2D pixel coordinates."""
    rvec, _ = cv2.Rodrigues(cam.R)
    pts_2d, _ = cv2.projectPoints(
        point_3d.reshape(1, 1, 3),
        rvec, cam.T,
        cam.camera_matrix, cam.dist_coeffs,
    )
    return pts_2d.reshape(2)


def point_3d_to_board_2d(
    point_3d: np.ndarray,
    board_normal: np.ndarray | None = None,
) -> tuple[float, float]:
    """Project a 3D point onto the board plane to get (x_mm, y_mm).

    Assumes the board lies in the Z=0 plane (if board_normal is None).
    """
    if board_normal is None:
        # Simple case: board at Z=0, X/Y are the board coordinates in meters
        return (float(point_3d[0] * 1000), float(point_3d[1] * 1000))  # m -> mm
    # General case with board normal: project onto plane
    # (extend later if board is not at Z=0)
    return (float(point_3d[0] * 1000), float(point_3d[1] * 1000))
