# tests/test_calibration_overlay.py
import numpy as np
import pytest


def test_draw_aruco_result_overlay_returns_image():
    from src.cv.calibration_overlay import draw_aruco_result_overlay
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    corners_px = [[100, 100], [540, 100], [540, 380], [100, 380]]
    center_px = [320, 240]
    radii_px = [10, 20, 80, 100, 160, 170]
    result = draw_aruco_result_overlay(frame, corners_px, center_px, radii_px)
    assert result.shape == (480, 640, 3)
    assert result.dtype == np.uint8
    assert result.sum() > 0


def test_draw_aruco_result_overlay_does_not_mutate_input():
    from src.cv.calibration_overlay import draw_aruco_result_overlay
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    original = frame.copy()
    draw_aruco_result_overlay(
        frame,
        [[100, 100], [540, 100], [540, 380], [100, 380]],
        [320, 240],
        [10, 20, 80, 100, 160, 170],
    )
    np.testing.assert_array_equal(frame, original)


def test_encode_result_image_returns_data_uri():
    from src.cv.calibration_overlay import encode_result_image
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    uri = encode_result_image(frame)
    assert uri.startswith("data:image/jpeg;base64,")
    assert len(uri) < 200_000


def test_draw_undistorted_preview():
    from src.cv.calibration_overlay import draw_undistorted_preview
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cam_mtx = np.eye(3, dtype=np.float64)
    cam_mtx[0, 0] = 500
    cam_mtx[1, 1] = 500
    cam_mtx[0, 2] = 320
    cam_mtx[1, 2] = 240
    dist = np.zeros(5, dtype=np.float64)
    result = draw_undistorted_preview(frame, cam_mtx, dist)
    assert result.shape == frame.shape


def test_draw_pose_result_overlay():
    from src.cv.calibration_overlay import draw_pose_result_overlay
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    corners_px = [[100, 100], [540, 100], [540, 380], [100, 380]]
    center_px = [320, 240]
    radii_px = [10, 20, 80, 100, 160, 170]
    cam_mtx = np.eye(3, dtype=np.float64)
    cam_mtx[0, 0] = 500
    cam_mtx[1, 1] = 500
    cam_mtx[0, 2] = 320
    cam_mtx[1, 2] = 240
    dist = np.zeros(5, dtype=np.float64)
    rvec = np.zeros((3, 1), dtype=np.float64)
    tvec = np.array([[0], [0], [1]], dtype=np.float64)
    result = draw_pose_result_overlay(frame, corners_px, center_px, radii_px, rvec, tvec, cam_mtx, dist)
    assert result.shape == (480, 640, 3)
    assert result.sum() > 0
