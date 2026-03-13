"""Tests for stereo calibration with synthetic data."""

import numpy as np
import cv2
import pytest

from src.cv.stereo_calibration import (
    stereo_calibrate, detect_charuco_corners, StereoResult,
    STEREO_CHARUCO_DICT, STEREO_SQUARES_X, STEREO_SQUARES_Y,
    STEREO_SQUARE_LENGTH, STEREO_MARKER_LENGTH,
)


class TestStereoCalibration:
    def test_frame_count_mismatch(self):
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        result = stereo_calibrate([np.zeros((10, 10, 3), dtype=np.uint8)], [], K, D, K, D)
        assert not result.ok
        assert "mismatch" in result.error_message.lower()

    def test_too_few_frames(self):
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        frames = [np.zeros((100, 100, 3), dtype=np.uint8)] * 3
        result = stereo_calibrate(frames, frames, K, D, K, D)
        assert not result.ok

    def test_result_type(self):
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        result = stereo_calibrate([], [], K, D, K, D)
        assert isinstance(result, StereoResult)

    def test_detect_charuco_corners_empty_frame(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cc, ci = detect_charuco_corners(frame)
        assert cc is None and ci is None

    def test_stereo_result_fields(self):
        """StereoResult has the expected fields."""
        r = StereoResult(ok=False, R=None, T=None,
                         reprojection_error=0.0, error_message="test")
        assert r.ok is False
        assert r.R is None
        assert r.T is None
        assert r.reprojection_error == 0.0
        assert r.error_message == "test"

    def test_stereo_result_success_fields(self):
        """StereoResult can hold numpy arrays for R and T."""
        R = np.eye(3, dtype=np.float64)
        T = np.array([[0.1], [0.0], [0.0]], dtype=np.float64)
        r = StereoResult(ok=True, R=R, T=T,
                         reprojection_error=0.5, error_message=None)
        assert r.ok is True
        np.testing.assert_array_equal(r.R, R)
        np.testing.assert_array_equal(r.T, T)
        assert r.error_message is None

    def test_too_few_frames_exact_boundary(self):
        """Exactly 4 frames should still be rejected (need >= 5)."""
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        frames = [np.zeros((100, 100, 3), dtype=np.uint8)] * 4
        result = stereo_calibrate(frames, frames, K, D, K, D)
        assert not result.ok
        assert "5" in result.error_message

    def test_five_blank_frames_no_crash(self):
        """5 blank frames: no corners detected, should fail gracefully."""
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        frames = [np.zeros((200, 200, 3), dtype=np.uint8)] * 5
        result = stereo_calibrate(frames, frames, K, D, K, D)
        assert not result.ok
        assert "usable" in result.error_message.lower()

    def test_detect_charuco_corners_grayscale_input(self):
        """Grayscale input should not crash."""
        frame = np.zeros((100, 100), dtype=np.uint8)
        cc, ci = detect_charuco_corners(frame)
        assert cc is None and ci is None

    def test_constants_defined(self):
        """Module constants are accessible and sane."""
        assert STEREO_CHARUCO_DICT == cv2.aruco.DICT_6X6_250
        assert STEREO_SQUARES_X == 7
        assert STEREO_SQUARES_Y == 5
        assert STEREO_SQUARE_LENGTH > 0
        assert STEREO_MARKER_LENGTH > 0
        assert STEREO_MARKER_LENGTH < STEREO_SQUARE_LENGTH
