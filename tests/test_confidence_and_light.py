"""Tests for compute_dart_confidence (#11) and LightStabilityMonitor (#12)."""

import numpy as np
import cv2
import pytest

from src.cv.detector import compute_dart_confidence
from src.cv.light_monitor import LightStabilityMonitor
from src.cv.diff_detector import FrameDiffDetector


# ------------------------------------------------------------------
# compute_dart_confidence tests
# ------------------------------------------------------------------


def _make_contour(points: list[tuple[int, int]]) -> np.ndarray:
    """Create a contour from a list of (x, y) points."""
    return np.array(points, dtype=np.int32).reshape(-1, 1, 2)


def _rect_contour(x: int, y: int, w: int, h: int) -> np.ndarray:
    """Create a rectangular contour."""
    return _make_contour([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


class TestComputeDartConfidence:
    def test_ideal_dart_contour_high_confidence(self):
        """Elongated contour with good area should score high."""
        # 6px wide, 30px tall -> aspect ~5, area ~180
        c = _rect_contour(0, 0, 6, 30)
        area = cv2.contourArea(c)
        conf = compute_dart_confidence(c, area)
        assert conf > 0.7

    def test_square_blob_lower_confidence(self):
        """Square contour (aspect ~1) should score lower on aspect."""
        c = _rect_contour(0, 0, 20, 20)
        area = cv2.contourArea(c)
        conf = compute_dart_confidence(c, area)
        # aspect_score ~ 1/3, but area and solidity may still be ok
        assert conf < 0.8

    def test_tiny_area_low_confidence(self):
        """Very small area should reduce confidence."""
        c = _rect_contour(0, 0, 2, 5)
        area = cv2.contourArea(c)  # ~10
        conf = compute_dart_confidence(c, area)
        assert conf < 0.75

    def test_huge_area_low_confidence(self):
        """Very large area should reduce confidence."""
        c = _rect_contour(0, 0, 100, 100)
        area = cv2.contourArea(c)  # 10000
        conf = compute_dart_confidence(c, area)
        assert conf < 0.7

    def test_confidence_bounded_0_1(self):
        """Confidence should always be in [0.0, 1.0]."""
        for w, h in [(1, 1), (5, 30), (20, 20), (100, 100)]:
            c = _rect_contour(0, 0, max(w, 1), max(h, 1))
            area = cv2.contourArea(c)
            if area == 0:
                area = 1.0
            conf = compute_dart_confidence(c, area)
            assert 0.0 <= conf <= 1.0

    def test_good_solidity_helps(self):
        """A solid contour should score higher than a hollow one."""
        solid = _rect_contour(0, 0, 6, 30)
        solid_area = cv2.contourArea(solid)
        solid_conf = compute_dart_confidence(solid, solid_area)

        # L-shaped contour has lower solidity
        l_shape = _make_contour([
            (0, 0), (6, 0), (6, 15), (3, 15), (3, 30), (0, 30),
        ])
        l_area = cv2.contourArea(l_shape)
        l_conf = compute_dart_confidence(l_shape, l_area)

        assert solid_conf >= l_conf


# ------------------------------------------------------------------
# LightStabilityMonitor tests
# ------------------------------------------------------------------


class TestLightStabilityMonitor:
    def test_stable_light(self):
        """Constant brightness should not be flagged as unstable."""
        mon = LightStabilityMonitor(variance_threshold=15.0, window_size=5)
        for _ in range(5):
            mon.update(np.full((50, 50), 128, dtype=np.uint8))
        assert not mon.is_light_unstable()
        assert mon.get_variance() < 1.0

    def test_unstable_light(self):
        """Rapidly changing brightness should be flagged."""
        mon = LightStabilityMonitor(variance_threshold=10.0, window_size=5)
        for val in [50, 200, 50, 200, 50]:
            mon.update(np.full((50, 50), val, dtype=np.uint8))
        assert mon.is_light_unstable()
        assert mon.get_variance() > 10.0

    def test_insufficient_data_stable(self):
        """With only 1 frame, should report stable."""
        mon = LightStabilityMonitor()
        mon.update(np.full((50, 50), 128, dtype=np.uint8))
        assert not mon.is_light_unstable()
        assert mon.get_variance() == 0.0

    def test_reset_clears_history(self):
        mon = LightStabilityMonitor(variance_threshold=10.0, window_size=5)
        for val in [50, 200, 50, 200, 50]:
            mon.update(np.full((50, 50), val, dtype=np.uint8))
        assert mon.is_light_unstable()
        mon.reset()
        assert not mon.is_light_unstable()

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            LightStabilityMonitor(variance_threshold=0)
        with pytest.raises(ValueError):
            LightStabilityMonitor(window_size=1)


# ------------------------------------------------------------------
# Integration: light monitor in FrameDiffDetector
# ------------------------------------------------------------------


def _gray(val: int, size: int = 100) -> np.ndarray:
    return np.full((size, size), val, dtype=np.uint8)


class TestLightMonitorIntegration:
    def test_threshold_raised_during_unstable_light(self):
        """When light is unstable, diff_threshold should be raised."""
        d = FrameDiffDetector(
            diff_threshold=30,
            light_variance_threshold=5.0,
            light_window_size=4,
        )
        # Feed alternating brightness frames to trigger instability
        for val in [50, 200, 50, 200]:
            d.update(_gray(val), has_motion=False)

        assert d._light_monitor.is_light_unstable()
        assert d.diff_threshold > 30  # should be raised

    def test_threshold_restored_when_stable(self):
        """After light stabilizes, threshold returns to base."""
        d = FrameDiffDetector(
            diff_threshold=30,
            light_variance_threshold=5.0,
            light_window_size=4,
        )
        # Make unstable
        for val in [50, 200, 50, 200]:
            d.update(_gray(val), has_motion=False)
        assert d.diff_threshold > 30

        # Stabilize
        for _ in range(10):
            d.update(_gray(128), has_motion=False)
        assert d.diff_threshold == 30

    def test_reset_restores_threshold(self):
        d = FrameDiffDetector(
            diff_threshold=30,
            light_variance_threshold=5.0,
            light_window_size=4,
        )
        for val in [50, 200, 50, 200]:
            d.update(_gray(val), has_motion=False)
        d.reset()
        assert d.diff_threshold == 30

    def test_get_params_includes_light_info(self):
        d = FrameDiffDetector()
        params = d.get_params()
        assert "light_unstable" in params
        assert "light_variance" in params
