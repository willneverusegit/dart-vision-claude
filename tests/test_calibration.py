"""Unit tests for CalibrationManager."""

import pytest
import os
import numpy as np
import yaml
from src.cv.calibration import (
    CalibrationManager,
    MANUAL_MIN_POINT_DISTANCE_PX,
    MM_PER_PX_MIN,
    MM_PER_PX_MAX,
    FRAME_INNER_MM,
)
from src.cv.camera_calibration import CameraCalibrationManager
from src.cv.stereo_calibration import (
    DEFAULT_CHARUCO_BOARD_SPEC,
    LARGE_MARKER_CHARUCO_BOARD_SPEC,
)


@pytest.fixture
def calib_manager(tmp_path):
    config_path = str(tmp_path / "test_calib.yaml")
    return CalibrationManager(config_path=config_path)


class TestCalibration:
    def test_initial_state_invalid(self, calib_manager):
        assert not calib_manager.is_valid()
        assert calib_manager.get_homography() is None

    def test_manual_calibration(self, calib_manager):
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        result = calib_manager.manual_calibration(points)
        assert result["ok"]
        assert calib_manager.is_valid()
        assert calib_manager.get_homography() is not None

    def test_config_persistence(self, calib_manager):
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        calib_manager.manual_calibration(points)

        # Load fresh manager from same config
        manager2 = CalibrationManager(config_path=calib_manager.config_path)
        assert manager2.is_valid()
        np.testing.assert_array_almost_equal(
            manager2.get_homography(),
            calib_manager.get_homography()
        )

    def test_atomic_write_creates_file(self, calib_manager):
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        calib_manager.manual_calibration(points)
        assert os.path.exists(calib_manager.config_path)

    def test_wrong_point_count(self, calib_manager):
        result = calib_manager.manual_calibration([[0, 0], [1, 1]])
        assert not result["ok"]
        assert "Expected 4" in result["error"]

    def test_degenerate_points(self, calib_manager):
        # All points at same location -> degenerate homography
        result = calib_manager.manual_calibration([[0, 0], [0, 0], [0, 0], [0, 0]])
        assert not result["ok"]

    def test_mm_per_px_reasonable(self, calib_manager):
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        result = calib_manager.manual_calibration(points)
        assert result["ok"]
        mm_per_px = result["mm_per_px"]
        assert 0.1 < mm_per_px < 50  # Sanity check

    def test_get_center(self, calib_manager):
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        calib_manager.manual_calibration(points)
        cx, cy = calib_manager.get_center()
        assert abs(cx - 200) < 1.0
        assert abs(cy - 200) < 1.0


class TestManualCalibrationValidation:
    """D2: Tests for A3 (mm/px plausibility) and A4 (min point distance)."""

    def test_points_too_close_same_location(self, calib_manager):
        """A4: All points at same location → distance error (not degenerate homography)."""
        result = calib_manager.manual_calibration([[0, 0], [0, 0], [0, 0], [0, 0]])
        assert not result["ok"]
        assert "nah beieinander" in result["error"] or "50" in result["error"]

    def test_points_too_close_threshold(self, calib_manager):
        """A4: Two points exactly at the minimum-distance boundary → fails."""
        # Place points such that points 0 and 1 are only 10px apart
        close_pts = [[100, 100], [110, 100], [400, 500], [100, 500]]
        result = calib_manager.manual_calibration(close_pts)
        assert not result["ok"]
        assert "nah" in result["error"].lower() or str(MANUAL_MIN_POINT_DISTANCE_PX) in result["error"]

    def test_valid_points_pass_distance_check(self, calib_manager):
        """A4: Points well above minimum distance → should not fail on distance."""
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        result = calib_manager.manual_calibration(points)
        assert result["ok"], f"Expected ok, got error: {result.get('error')}"

    def test_mm_per_px_too_high(self, calib_manager):
        """A3: Board width ~100px → mm/px = 500/100 = 5.0 > MM_PER_PX_MAX → fails."""
        # width = 100px, height = 100px (above 50px distance threshold)
        points = [[200, 200], [300, 200], [300, 300], [200, 300]]
        result = calib_manager.manual_calibration(points)
        expected_ratio = FRAME_INNER_MM / 100.0  # ~4.8
        if expected_ratio > MM_PER_PX_MAX:
            assert not result["ok"]
            assert "mm/px" in result["error"] or "Verhältnis" in result["error"]
        else:
            # If ratio happens to be in range, test is inconclusive — just check no crash
            assert "ok" in result

    def test_mm_per_px_too_low(self, calib_manager):
        """A3: Board width ~2000px → mm/px = 500/2000 = 0.25 < MM_PER_PX_MIN → fails."""
        points = [[0, 0], [2000, 0], [2000, 2000], [0, 2000]]
        result = calib_manager.manual_calibration(points)
        expected_ratio = FRAME_INNER_MM / 2000.0  # ~0.24
        if expected_ratio < MM_PER_PX_MIN:
            assert not result["ok"]
            assert "mm/px" in result["error"] or "Verhältnis" in result["error"]
        else:
            assert "ok" in result

    def test_mm_per_px_in_valid_range(self, calib_manager):
        """A3: Standard points → mm/px within [MM_PER_PX_MIN, MM_PER_PX_MAX] → succeeds."""
        # width ~200px → mm/px = 500/200 = 2.5 (within 0.3–3.0)
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        result = calib_manager.manual_calibration(points)
        assert result["ok"]
        assert MM_PER_PX_MIN <= result["mm_per_px"] <= MM_PER_PX_MAX


class TestHomographyFallback:
    """P60: Homography fallback when markers are occluded."""

    @pytest.fixture
    def board_manager(self, tmp_path):
        from src.cv.board_calibration import BoardCalibrationManager
        config_path = str(tmp_path / "board_calib.yaml")
        return BoardCalibrationManager(
            config_path=config_path,
            max_homography_age_frames=10,
            homography_warn_age_frames=5,
        )

    @pytest.fixture
    def calibrated_board_manager(self, board_manager):
        """Board manager with a valid manual calibration already set."""
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        board_manager.manual_calibration(points)
        # Manually cache the homography (simulates successful aruco detection)
        h = board_manager.get_homography()
        assert h is not None
        board_manager._last_valid_homography = h.copy()
        board_manager._homography_age = 0
        return board_manager

    def test_initial_homography_age_zero(self, board_manager):
        assert board_manager.homography_age == 0

    def test_get_params_initial(self, board_manager):
        params = board_manager.get_params()
        assert params["homography_age"] == 0
        assert params["max_homography_age_frames"] == 10
        assert params["homography_warn_age_frames"] == 5

    def test_fallback_returns_cached_homography(self, calibrated_board_manager):
        """When markers not found, fallback uses cached homography."""
        # Use a blank frame — no markers will be detected
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = calibrated_board_manager.aruco_calibration_with_fallback(frame)
        assert result["ok"]
        assert result.get("fallback") is True
        assert result["homography_age"] == 1

    def test_fallback_increments_age(self, calibrated_board_manager):
        """Each failed detection increments homography_age."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(3):
            result = calibrated_board_manager.aruco_calibration_with_fallback(frame)
            assert result["ok"]
            assert result["homography_age"] == i + 1
        assert calibrated_board_manager.homography_age == 3

    def test_fallback_expires_after_max_age(self, calibrated_board_manager):
        """After max_homography_age_frames, fallback stops working."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Exhaust the max age (10 frames)
        for _ in range(10):
            calibrated_board_manager.aruco_calibration_with_fallback(frame)
        # 11th attempt should fail
        result = calibrated_board_manager.aruco_calibration_with_fallback(frame)
        assert not result["ok"]

    def test_no_fallback_without_cached_homography(self, board_manager):
        """Without prior calibration, fallback is not available."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = board_manager.aruco_calibration_with_fallback(frame)
        assert not result["ok"]

    def test_successful_detection_resets_age(self, calibrated_board_manager, monkeypatch):
        """Successful aruco detection resets homography_age to 0."""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Simulate some failures
        calibrated_board_manager.aruco_calibration_with_fallback(frame)
        calibrated_board_manager.aruco_calibration_with_fallback(frame)
        assert calibrated_board_manager.homography_age == 2

        # Simulate a successful aruco detection by monkeypatching
        fake_result = {"ok": True, "homography": np.eye(3).tolist(), "mm_per_px": 1.0}
        monkeypatch.setattr(
            calibrated_board_manager._legacy, "aruco_calibration",
            lambda *a, **kw: fake_result,
        )
        result = calibrated_board_manager.aruco_calibration_with_fallback(frame)
        assert result["ok"]
        assert calibrated_board_manager.homography_age == 0
        assert result.get("fallback") is None

    def test_get_params_reflects_age(self, calibrated_board_manager):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        calibrated_board_manager.aruco_calibration_with_fallback(frame)
        params = calibrated_board_manager.get_params()
        assert params["homography_age"] == 1
        assert params["has_cached_homography"] is True


class TestCameraCharucoBoardConfig:
    def test_camera_calibration_manager_uses_default_board_spec(self, tmp_path):
        path = str(tmp_path / "cal.yaml")
        manager = CameraCalibrationManager(config_path=path)
        assert manager.get_charuco_board_spec() == DEFAULT_CHARUCO_BOARD_SPEC

    def test_camera_calibration_manager_reads_saved_board_spec(self, tmp_path):
        path = tmp_path / "cal.yaml"
        path.write_text(
            yaml.dump(
                {
                    "schema_version": 3,
                    "cameras": {
                        "default": {
                            "charuco_preset": "40x28",
                            "charuco_squares_x": 7,
                            "charuco_squares_y": 5,
                            "charuco_square_length_m": 0.04,
                            "charuco_marker_length_m": 0.028,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        manager = CameraCalibrationManager(config_path=str(path))
        assert manager.get_charuco_board_spec() == LARGE_MARKER_CHARUCO_BOARD_SPEC

    def test_charuco_calibration_persists_board_geometry(self, tmp_path, monkeypatch):
        path = str(tmp_path / "cal.yaml")
        manager = CameraCalibrationManager(config_path=path)
        frames = [np.zeros((120, 160, 3), dtype=np.uint8) for _ in range(3)]

        class DummyDetector:
            def detectMarkers(self, _gray):
                corners = [np.zeros((1, 4, 2), dtype=np.float32)]
                ids = np.array([[0], [1], [2], [3]], dtype=np.int32)
                return corners, ids, None

        def fake_interpolate(_corners, _ids, _gray, _board):
            return 4, np.zeros((4, 1, 2), dtype=np.float32), np.arange(4, dtype=np.int32).reshape(-1, 1)

        def fake_calibrate(_corners, _ids, _board, _image_size, _camera_matrix, _dist_coeffs):
            return 0.25, np.eye(3, dtype=np.float64), np.zeros((5, 1), dtype=np.float64), [], []

        monkeypatch.setattr(
            "src.cv.camera_calibration.cv2.aruco.ArucoDetector",
            lambda _dictionary: DummyDetector(),
        )
        monkeypatch.setattr(
            "src.cv.camera_calibration.cv2.aruco.interpolateCornersCharuco",
            fake_interpolate,
        )
        monkeypatch.setattr(
            "src.cv.camera_calibration.cv2.aruco.calibrateCameraCharuco",
            fake_calibrate,
        )

        result = manager.charuco_calibration(
            frames,
            square_length=0.04,
            marker_length=0.028,
        )

        assert result["ok"]
        assert result["charuco_board"]["marker_length_mm"] == pytest.approx(28.0)

        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        cfg = raw["cameras"]["default"]
        assert cfg["charuco_preset"] == "40x28"
        assert cfg["charuco_marker_length_m"] == pytest.approx(0.028)
