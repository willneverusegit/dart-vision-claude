"""Unit tests for CalibrationManager."""

import pytest
import os
import numpy as np
from src.cv.calibration import CalibrationManager


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
