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
    point_board: np.ndarray,
) -> tuple[float, float]:
    """Convert a 3D point in board frame to board (x_mm, y_mm).

    Expects input already transformed into the board coordinate frame where
    Z=0 is the board face and X, Y are in meters.
    """
    return (float(point_board[0] * 1000), float(point_board[1] * 1000))  # m -> mm


def transform_to_board_frame(
    point_3d: np.ndarray,
    R_cb: np.ndarray,
    t_cb: np.ndarray,
) -> np.ndarray:
    """Transform a 3D point from camera-1 frame to dartboard frame.

    Args:
        point_3d: (X, Y, Z) in camera-1 coordinate frame (meters).
        R_cb: 3x3 rotation matrix from camera frame to board frame.
        t_cb: (3,) translation vector from camera frame to board frame (meters).

    Returns:
        (X, Y, Z) in board coordinate frame.
        Z ≈ 0 is the board face; X/Y are horizontal/vertical offsets in meters.
    """
    return R_cb @ point_3d + t_cb.reshape(3)


def triangulate_multi_pair(
    detections: list[dict],
    camera_params: dict[str, CameraParams],
    board_transforms: dict[str, dict],
    depth_tolerance_m: float = 0.015,
) -> dict | None:
    """Triangulate using all valid camera pairs, with outlier rejection.

    Args:
        detections: List of dicts with keys 'camera_id', 'detection' (DartDetection).
        camera_params: camera_id -> CameraParams mapping.
        board_transforms: camera_id -> {'R_cb': 3x3, 't_cb': (3,)} mapping.
        depth_tolerance_m: Max Z-depth for board-plane plausibility.

    Returns:
        Dict with 'board_x_mm', 'board_y_mm', 'reprojection_error', 'pairs_used', 'source'
        or None if no valid triangulation.
    """
    results = []
    z_rejected_count = 0
    pairs_attempted = 0

    for i in range(len(detections)):
        for j in range(i + 1, len(detections)):
            cam_a = detections[i]["camera_id"]
            cam_b = detections[j]["camera_id"]

            p1 = camera_params.get(cam_a)
            p2 = camera_params.get(cam_b)
            if p1 is None or p2 is None:
                continue

            det1 = detections[i]["detection"]
            det2 = detections[j]["detection"]
            if det1 is None or det2 is None:
                continue

            tri = triangulate_point(det1.center, det2.center, p1, p2)
            if not tri.valid:
                continue

            bt = board_transforms.get(cam_a)
            if bt is None:
                continue

            p_board = transform_to_board_frame(tri.point_3d, bt["R_cb"], bt["t_cb"])

            pairs_attempted += 1
            if abs(p_board[2]) > depth_tolerance_m:
                z_rejected_count += 1
                continue

            board_x_mm, board_y_mm = point_3d_to_board_2d(p_board)
            results.append({
                "board_x_mm": board_x_mm,
                "board_y_mm": board_y_mm,
                "reprojection_error": tri.reprojection_error,
                "pair": (cam_a, cam_b),
                "z_depth": float(p_board[2]),
            })

    if not results:
        return {"failed": True, "z_rejected": z_rejected_count, "pairs_attempted": pairs_attempted}

    if len(results) == 1:
        r = results[0]
        return {
            "board_x_mm": r["board_x_mm"],
            "board_y_mm": r["board_y_mm"],
            "reprojection_error": r["reprojection_error"],
            "z_depth": r["z_depth"],
            "pairs_used": 1,
            "source": "triangulation",
        }

    # Outlier rejection for 3+ results: remove points > 2x median distance from centroid
    if len(results) >= 3:
        results = _reject_outliers(results)

    # Weighted average (weight = 1 / reproj_error)
    epsilon = 1e-6
    total_weight = 0.0
    wx, wy = 0.0, 0.0
    for r in results:
        w = 1.0 / (r["reprojection_error"] + epsilon)
        wx += r["board_x_mm"] * w
        wy += r["board_y_mm"] * w
        total_weight += w

    avg_reproj = sum(r["reprojection_error"] for r in results) / len(results)
    avg_z = sum(r["z_depth"] for r in results) / len(results)

    return {
        "board_x_mm": wx / total_weight,
        "board_y_mm": wy / total_weight,
        "reprojection_error": avg_reproj,
        "z_depth": avg_z,
        "pairs_used": len(results),
        "source": "triangulation",
    }


def _reject_outliers(results: list[dict]) -> list[dict]:
    """Remove outlier triangulation results (>2x median distance from centroid)."""
    import math

    cx = sum(r["board_x_mm"] for r in results) / len(results)
    cy = sum(r["board_y_mm"] for r in results) / len(results)

    distances = [math.hypot(r["board_x_mm"] - cx, r["board_y_mm"] - cy) for r in results]
    sorted_dists = sorted(distances)
    median_dist = sorted_dists[len(sorted_dists) // 2]

    threshold = max(median_dist * 2.0, 1.0)  # at least 1mm to avoid rejecting tight clusters

    filtered = [r for r, d in zip(results, distances) if d <= threshold]
    return filtered if len(filtered) >= 1 else results  # never reject all
