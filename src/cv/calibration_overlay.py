# src/cv/calibration_overlay.py
"""Overlay rendering for calibration result previews."""

from __future__ import annotations

import cv2
import numpy as np

_RING_COLORS = [
    (0, 0, 255),
    (0, 200, 0),
    (0, 255, 255),
    (0, 255, 255),
    (0, 165, 255),
    (0, 165, 255),
]


def draw_aruco_result_overlay(
    frame: np.ndarray,
    corners_px: list[list[float]],
    center_px: list[float],
    radii_px: list[float],
) -> np.ndarray:
    """Draw ArUco marker corners, board center, and scoring rings.
    Returns a new image (does not mutate *frame*).
    """
    out = frame.copy()
    cx, cy = int(center_px[0]), int(center_px[1])
    for i, r in enumerate(radii_px):
        color = _RING_COLORS[i] if i < len(_RING_COLORS) else (200, 200, 200)
        cv2.circle(out, (cx, cy), int(r), color, 1, cv2.LINE_AA)
    for corner in corners_px:
        x, y = int(corner[0]), int(corner[1])
        cv2.rectangle(out, (x - 8, y - 8), (x + 8, y + 8), (0, 255, 136), 2)
    cv2.circle(out, (cx, cy), 5, (0, 0, 255), -1, cv2.LINE_AA)
    return out


def draw_undistorted_preview(
    frame: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> np.ndarray:
    """Return the undistorted frame as lens calibration result."""
    return cv2.undistort(frame, camera_matrix, dist_coeffs)


def draw_pose_result_overlay(
    frame: np.ndarray,
    corners_px: list[list[float]],
    center_px: list[float],
    radii_px: list[float],
    rvec: np.ndarray,
    tvec: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> np.ndarray:
    """Draw marker corners, scoring rings, and 3D axes for board pose."""
    out = draw_aruco_result_overlay(frame, corners_px, center_px, radii_px)
    cv2.drawFrameAxes(out, camera_matrix, dist_coeffs, rvec, tvec, 0.1)
    return out


def draw_stereo_epipolar_overlay(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    num_lines: int = 8,
) -> np.ndarray:
    """Draw side-by-side stereo frames with horizontal epipolar lines."""
    h = max(frame_a.shape[0], frame_b.shape[0])
    w_a, w_b = frame_a.shape[1], frame_b.shape[1]
    out = np.zeros((h, w_a + w_b, 3), dtype=np.uint8)
    out[:frame_a.shape[0], :w_a] = frame_a
    out[:frame_b.shape[0], w_a:w_a + w_b] = frame_b
    for i in range(1, num_lines + 1):
        y = int(h * i / (num_lines + 1))
        cv2.line(out, (0, y), (w_a + w_b, y), (0, 255, 255), 1, cv2.LINE_AA)
    cv2.line(out, (w_a, 0), (w_a, h), (255, 255, 255), 1)
    return out


def encode_result_image(frame: np.ndarray, quality: int = 75) -> str:
    """Encode a BGR frame as base64 data-URI JPEG string."""
    import base64
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"
