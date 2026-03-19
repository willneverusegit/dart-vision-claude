"""Tests for stereo calibration with synthetic data."""

import numpy as np
import cv2
import pytest

from src.cv.stereo_calibration import (
    DEFAULT_CHARUCO_BOARD_SPEC,
    LARGE_MARKER_CHARUCO_BOARD_SPEC,
    PORTRAIT_CHARUCO_BOARD_SPEC,
    StereoResult,
    detect_charuco_board,
    detect_charuco_corners,
    resolve_charuco_board_candidates,
    resolve_charuco_board_spec,
    stereo_calibrate,
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

    def test_charuco_large_marker_preset_defined(self):
        assert LARGE_MARKER_CHARUCO_BOARD_SPEC.squares_x == 7
        assert LARGE_MARKER_CHARUCO_BOARD_SPEC.squares_y == 5
        assert LARGE_MARKER_CHARUCO_BOARD_SPEC.square_length_m == pytest.approx(0.04)
        assert LARGE_MARKER_CHARUCO_BOARD_SPEC.marker_length_m == pytest.approx(0.028)
        assert LARGE_MARKER_CHARUCO_BOARD_SPEC.preset_name == "7x5_40x28"

    def test_resolve_charuco_board_from_preset(self):
        spec = resolve_charuco_board_spec(preset="40x28")
        assert spec == LARGE_MARKER_CHARUCO_BOARD_SPEC

    def test_resolve_charuco_board_from_config(self):
        spec = resolve_charuco_board_spec(
            config={"charuco_preset": "40x28"}
        )
        assert spec == LARGE_MARKER_CHARUCO_BOARD_SPEC

    def test_resolve_charuco_board_with_mm_override(self):
        spec = resolve_charuco_board_spec(
            config=DEFAULT_CHARUCO_BOARD_SPEC.to_config_fragment(),
            marker_length_mm=28,
        )
        assert spec == LARGE_MARKER_CHARUCO_BOARD_SPEC

    def test_resolve_charuco_board_rejects_invalid_geometry(self):
        with pytest.raises(ValueError):
            resolve_charuco_board_spec(square_length_mm=40, marker_length_mm=40)

    def test_auto_candidates_include_landscape_and_portrait(self):
        specs = resolve_charuco_board_candidates(preset="auto")
        assert {spec.preset_name for spec in specs} == {
            "7x5_40x20",
            "7x5_40x28",
            "5x7_40x20",
            "5x7_40x28",
        }

    def test_detect_charuco_board_auto_prefers_5x7_when_7x5_has_no_corners(self, monkeypatch):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)

        class DummyDetector:
            def detectMarkers(self, _gray):
                corners = [np.zeros((1, 4, 2), dtype=np.float32)]
                ids = np.array([[0], [1], [2], [3]], dtype=np.int32)
                return corners, ids, None

        def fake_build_detector(_dictionary):
            return DummyDetector()

        def fake_interpolate(_corners, _ids, _gray, board):
            size = board.getChessboardSize()
            if tuple(size) == (5, 7):
                return 18, np.zeros((18, 1, 2), dtype=np.float32), np.arange(18, dtype=np.int32).reshape(-1, 1)
            return 0, None, None

        monkeypatch.setattr("src.cv.stereo_calibration._build_aruco_detector", fake_build_detector)
        monkeypatch.setattr("src.cv.stereo_calibration.cv2.aruco.interpolateCornersCharuco", fake_interpolate)

        result = detect_charuco_board(frame, preset="auto")
        assert result.interpolation_ok is True
        assert result.board_spec == PORTRAIT_CHARUCO_BOARD_SPEC
        assert result.charuco_corners_found == 18

    def test_detect_charuco_board_auto_keeps_7x5_when_it_is_best(self, monkeypatch):
        frame = np.zeros((120, 160, 3), dtype=np.uint8)

        class DummyDetector:
            def detectMarkers(self, _gray):
                corners = [np.zeros((1, 4, 2), dtype=np.float32)]
                ids = np.array([[0], [1], [2], [3]], dtype=np.int32)
                return corners, ids, None

        def fake_build_detector(_dictionary):
            return DummyDetector()

        def fake_interpolate(_corners, _ids, _gray, board):
            size = board.getChessboardSize()
            if tuple(size) == (7, 5):
                return 16, np.zeros((16, 1, 2), dtype=np.float32), np.arange(16, dtype=np.int32).reshape(-1, 1)
            return 0, None, None

        monkeypatch.setattr("src.cv.stereo_calibration._build_aruco_detector", fake_build_detector)
        monkeypatch.setattr("src.cv.stereo_calibration.cv2.aruco.interpolateCornersCharuco", fake_interpolate)

        result = detect_charuco_board(frame, preset="auto")
        assert result.interpolation_ok is True
        assert result.board_spec == DEFAULT_CHARUCO_BOARD_SPEC
        assert result.charuco_corners_found == 16
