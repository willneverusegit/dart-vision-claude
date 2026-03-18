"""Tests for FPSGovernor adaptive frame-rate control."""

from __future__ import annotations

import pytest

from src.cv.multi_camera import FPSGovernor


class TestFPSGovernorDefaults:
    def test_initial_state(self):
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        assert gov.effective_fps == 30.0
        assert gov.frame_interval_s == pytest.approx(1.0 / 30.0)

    def test_get_stats_fields(self):
        gov = FPSGovernor()
        stats = gov.get_stats()
        assert "target_fps" in stats
        assert "effective_fps" in stats
        assert "is_primary" in stats
        assert "avg_processing_ms" in stats
        assert "overload_count" in stats

    def test_get_stats_defaults(self):
        gov = FPSGovernor(target_fps=25, is_primary=True)
        stats = gov.get_stats()
        assert stats["target_fps"] == 25
        assert stats["effective_fps"] == 25.0
        assert stats["is_primary"] is True
        assert stats["avg_processing_ms"] == 0.0
        assert stats["overload_count"] == 0


class TestFPSGovernorOverload:
    def test_secondary_reduces_fps_under_overload(self):
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        # Simulate frames that exceed 80% of the frame budget
        slow_time = 0.030  # 30ms, budget is ~33ms, 80% = ~26.7ms
        for _ in range(15):
            gov.record_frame_time(slow_time)
        assert gov.effective_fps < 30.0

    def test_primary_never_reduces(self):
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=True)
        slow_time = 0.035  # exceeds budget
        for _ in range(30):
            gov.record_frame_time(slow_time)
        assert gov.effective_fps == 30.0

    def test_fps_does_not_go_below_min(self):
        gov = FPSGovernor(target_fps=30, min_fps=15, is_primary=False)
        # Hammer with very slow frames repeatedly
        for _ in range(200):
            gov.record_frame_time(0.1)
        assert gov.effective_fps >= 15.0


class TestFPSGovernorRecovery:
    def test_recovery_increases_fps(self):
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        # First, force reduction
        for _ in range(15):
            gov.record_frame_time(0.035)
        reduced = gov.effective_fps
        assert reduced < 30.0

        # Now simulate very fast frames to trigger recovery
        fast_time = 0.005  # well under 50% of budget
        for _ in range(35):
            gov.record_frame_time(fast_time)
        assert gov.effective_fps > reduced


class TestFrameIntervalConsistency:
    def test_frame_interval_matches_effective_fps(self):
        gov = FPSGovernor(target_fps=20, is_primary=False)
        # The interval should be 1/effective_fps
        expected = 1.0 / gov._effective_fps
        assert gov.frame_interval_s == pytest.approx(expected)

    def test_frame_interval_updates_after_reduction(self):
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        initial_interval = gov.frame_interval_s
        for _ in range(15):
            gov.record_frame_time(0.035)
        # After reduction, interval should be longer
        assert gov.frame_interval_s > initial_interval
