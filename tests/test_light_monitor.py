"""Tests for LightStabilityMonitor."""

import numpy as np
import pytest

from src.cv.light_monitor import LightStabilityMonitor


class TestLightStabilityMonitor:
    def test_stable_lighting(self):
        mon = LightStabilityMonitor(variance_threshold=15.0, window_size=5)
        # Feed frames with consistent brightness
        for _ in range(5):
            frame = np.full((100, 100), 128, dtype=np.uint8)
            mon.update(frame)
        assert not mon.is_light_unstable()
        assert mon.get_variance() < 1.0

    def test_unstable_lighting(self):
        mon = LightStabilityMonitor(variance_threshold=10.0, window_size=5)
        # Feed frames with wildly varying brightness
        for val in [50, 200, 50, 200, 50]:
            frame = np.full((100, 100), val, dtype=np.uint8)
            mon.update(frame)
        assert mon.is_light_unstable()
        assert mon.get_variance() > 10.0

    def test_insufficient_data_is_stable(self):
        mon = LightStabilityMonitor()
        frame = np.full((100, 100), 128, dtype=np.uint8)
        mon.update(frame)
        assert not mon.is_light_unstable()
        assert mon.get_variance() == 0.0

    def test_reset_clears_history(self):
        mon = LightStabilityMonitor()
        for val in [50, 200, 50]:
            mon.update(np.full((100, 100), val, dtype=np.uint8))
        mon.reset()
        assert mon.get_variance() == 0.0
        assert not mon.is_light_unstable()

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            LightStabilityMonitor(variance_threshold=0)
        with pytest.raises(ValueError):
            LightStabilityMonitor(window_size=1)
