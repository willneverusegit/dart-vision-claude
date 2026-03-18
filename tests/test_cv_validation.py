"""Tests for configuration validation in CV pipeline modules."""

import numpy as np
import pytest

from src.cv.detector import DartImpactDetector
from src.cv.motion import MotionDetector


class TestDartImpactDetectorValidation:
    def test_area_min_greater_than_area_max_raises(self):
        with pytest.raises(ValueError, match="area_min must be less than area_max"):
            DartImpactDetector(area_min=500, area_max=100)

    def test_area_min_equal_area_max_raises(self):
        with pytest.raises(ValueError, match="area_min must be less than area_max"):
            DartImpactDetector(area_min=100, area_max=100)

    def test_area_min_negative_raises(self):
        with pytest.raises(ValueError, match="area_min must be >= 0"):
            DartImpactDetector(area_min=-1)

    def test_confirmation_frames_zero_raises(self):
        with pytest.raises(ValueError, match="confirmation_frames must be >= 1"):
            DartImpactDetector(confirmation_frames=0)

    def test_position_tolerance_zero_raises(self):
        with pytest.raises(ValueError, match="position_tolerance_px must be > 0"):
            DartImpactDetector(position_tolerance_px=0)

    def test_aspect_ratio_range_inverted_raises(self):
        with pytest.raises(ValueError, match="aspect_ratio_range"):
            DartImpactDetector(aspect_ratio_range=(3.0, 0.3))

    def test_aspect_ratio_range_zero_raises(self):
        with pytest.raises(ValueError, match="aspect_ratio_range values must be > 0"):
            DartImpactDetector(aspect_ratio_range=(0.0, 3.0))

    def test_inclusive_area_boundary(self):
        """area == area_min should be included (inclusive bounds)."""
        # A 10x10 filled square in a mask yields contour area 81 (OpenCV convention).
        det = DartImpactDetector(area_min=81, area_max=200)
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:50, 40:50] = 255
        shapes = det._find_dart_shapes(mask)
        assert len(shapes) >= 1
        assert any(abs(s["area"] - 81.0) < 1 for s in shapes)

    def test_get_params_returns_current_values(self):
        det = DartImpactDetector(area_min=5, area_max=2000)
        params = det.get_params()
        assert params["area_min"] == 5
        assert params["area_max"] == 2000
        assert "confirmation_frames" in params

    def test_set_params_updates_area_range(self):
        det = DartImpactDetector(area_min=10, area_max=1000)
        result = det.set_params(area_min=5, area_max=2000)
        assert det.area_min == 5
        assert det.area_max == 2000
        assert result["area_min"] == 5
        assert result["area_max"] == 2000

    def test_set_params_partial_update(self):
        det = DartImpactDetector(area_min=10, area_max=1000)
        det.set_params(area_max=2000)
        assert det.area_min == 10  # unchanged
        assert det.area_max == 2000

    def test_set_params_rejects_invalid_range(self):
        det = DartImpactDetector(area_min=10, area_max=1000)
        with pytest.raises(ValueError, match="area_min must be less than area_max"):
            det.set_params(area_min=2000, area_max=500)
        # Original values unchanged
        assert det.area_min == 10
        assert det.area_max == 1000

    def test_set_params_rejects_negative_area_min(self):
        det = DartImpactDetector()
        with pytest.raises(ValueError, match="area_min must be >= 0"):
            det.set_params(area_min=-1)

    def test_custom_area_max_allows_small_blobs(self):
        """With area_max=5000, larger blobs (like outer-bull) pass the filter."""
        det = DartImpactDetector(area_min=5, area_max=5000)
        # Create a larger blob (~20x20 = ~361px area)
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[30:50, 30:50] = 255
        shapes = det._find_dart_shapes(mask)
        assert len(shapes) >= 1

    def test_max_candidates_limit(self):
        det = DartImpactDetector(max_candidates=3)
        # Manually inject candidates beyond the limit via detect path
        for i in range(5):
            det._candidates.append({"center": (i * 100, 0), "area": 50, "count": 1})
        # Simulate adding one more via detect's else branch
        det._candidates.append({"center": (999, 999), "area": 50, "count": 1})
        while len(det._candidates) > det.max_candidates:
            det._candidates.pop(0)
        assert len(det._candidates) == 3


class TestMotionDetectorValidation:
    def test_threshold_zero_raises(self):
        with pytest.raises(ValueError, match="threshold must be > 0"):
            MotionDetector(threshold=0)

    def test_threshold_negative_raises(self):
        with pytest.raises(ValueError, match="threshold must be > 0"):
            MotionDetector(threshold=-5)

    def test_var_threshold_zero_raises(self):
        with pytest.raises(ValueError, match="var_threshold must be > 0"):
            MotionDetector(var_threshold=0)

    def test_valid_params_accepted(self):
        m = MotionDetector(threshold=100, var_threshold=25)
        assert m.threshold == 100
