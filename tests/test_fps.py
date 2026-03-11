"""Tests for FPS counter."""

import time
from src.utils.fps import FPSCounter


class TestFPSCounter:
    def test_no_frames_returns_zero(self):
        counter = FPSCounter()
        assert counter.fps() == 0.0

    def test_single_frame_returns_zero(self):
        counter = FPSCounter()
        counter.update()
        assert counter.fps() == 0.0

    def test_multiple_frames_gives_positive_fps(self):
        counter = FPSCounter(window_size=10)
        for _ in range(5):
            counter.update()
            time.sleep(0.01)
        fps = counter.fps()
        assert fps > 0.0

    def test_window_size_limits_timestamps(self):
        counter = FPSCounter(window_size=3)
        for _ in range(10):
            counter.update()
        assert len(counter._timestamps) == 3
