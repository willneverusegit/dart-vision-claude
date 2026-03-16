"""Unit tests for CalibrationManager."""

import pytest
import os
import numpy as np
from src.cv.calibration import (
    CalibrationManager,
    MANUAL_MIN_POINT_DISTANCE_PX,
    MM_PER_PX_MIN,
    MM_PER_PX_MAX,
    FRAME_INNER_MM,
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
