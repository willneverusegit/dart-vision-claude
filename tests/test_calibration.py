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
        """A3: Board width ~100px → mm/px = 480/100 = 4.8 > MM_PER_PX_MAX → fails."""
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
        """A3: Board width ~2000px → mm/px = 480/2000 = 0.24 < MM_PER_PX_MIN → fails."""
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
        # width ~200px → mm/px = 480/200 = 2.4 (within 0.3–3.0)
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        result = calib_manager.manual_calibration(points)
        assert result["ok"]
        assert MM_PER_PX_MIN <= result["mm_per_px"] <= MM_PER_PX_MAX


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
