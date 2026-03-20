"""Unit tests for MotionDetector."""

import numpy as np
import pytest

from src.cv.motion import MotionDetector


class TestMotionDetector:
    def test_no_motion_on_static_frames(self):
        det = MotionDetector(threshold=500, framediff_fallback=False)
        frame = np.full((100, 100), 128, dtype=np.uint8)
        # Feed several identical frames to build background
        for _ in range(20):
            mask, motion = det.detect(frame)
        assert not motion

    def test_motion_detected_on_change(self):
        det = MotionDetector(threshold=50, framediff_fallback=True, framediff_threshold=10)
        dark = np.zeros((100, 100), dtype=np.uint8)
        bright = np.full((100, 100), 255, dtype=np.uint8)
        # Build background on dark
        for _ in range(5):
            det.detect(dark)
        # Sudden change should trigger framediff
        _, motion = det.detect(bright)
        assert motion

    def test_downscale_returns_original_size_mask(self):
        det = MotionDetector(threshold=500, downscale_factor=4, framediff_fallback=False)
        frame = np.full((400, 400), 128, dtype=np.uint8)
        mask, _ = det.detect(frame)
        assert mask.shape == (400, 400)

    def test_get_params(self):
        det = MotionDetector(threshold=300, framediff_threshold=20)
        params = det.get_params()
        assert params["motion_threshold"] == 300
        assert params["framediff_threshold"] == 20
        assert params["framediff_fallback"] is True

    def test_set_threshold(self):
        det = MotionDetector(threshold=500)
        det.set_threshold(100)
        assert det.threshold == 100

    def test_set_threshold_invalid(self):
        det = MotionDetector()
        with pytest.raises(ValueError):
            det.set_threshold(0)

    def test_reset(self):
        det = MotionDetector()
        frame = np.full((100, 100), 128, dtype=np.uint8)
        det.detect(frame)
        det.reset()
        assert det._prev_frame is None

    def test_invalid_params(self):
        with pytest.raises(ValueError):
            MotionDetector(threshold=0)
        with pytest.raises(ValueError):
            MotionDetector(var_threshold=0)
        with pytest.raises(ValueError):
            MotionDetector(learning_rate=0)
        with pytest.raises(ValueError):
            MotionDetector(downscale_factor=0)
