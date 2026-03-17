"""Tests for TriangulationTelemetry."""

import pytest

from src.utils.triangulation_telemetry import TriangulationTelemetry


class TestTriangulationTelemetryInit:
    def test_initial_state(self):
        t = TriangulationTelemetry()
        assert t.sample_count == 0
        assert t.total_attempts == 0
        assert t.triangulation_ok == 0
        assert t.voting_fallback == 0
        assert t.single_fallback == 0
        assert t.z_rejected == 0
        assert t.failure_rate == 0.0
        assert t.failure_alert_active is False

    def test_invalid_max_samples(self):
        with pytest.raises(ValueError, match="max_samples must be >= 1"):
            TriangulationTelemetry(max_samples=0)
        with pytest.raises(ValueError):
            TriangulationTelemetry(max_samples=-5)


class TestRecordAttempt:
    def test_record_triangulation(self):
        t = TriangulationTelemetry()
        t.record_attempt("triangulation", 0.5, 0.002)
        assert t.sample_count == 1
        assert t.total_attempts == 1
        assert t.triangulation_ok == 1

    def test_record_voting_fallback(self):
        t = TriangulationTelemetry()
        t.record_attempt("voting_fallback")
        assert t.voting_fallback == 1

    def test_record_single_fallback(self):
        t = TriangulationTelemetry()
        t.record_attempt("single_fallback")
        assert t.single_fallback == 1

    def test_record_z_rejected(self):
        t = TriangulationTelemetry()
        t.record_attempt("z_rejected", 1.2, 0.05)
        assert t.z_rejected == 1


class TestFailureRate:
    def test_all_success(self):
        t = TriangulationTelemetry()
        for _ in range(10):
            t.record_attempt("triangulation", 0.3, 0.001)
        assert t.failure_rate == 0.0

    def test_all_failure(self):
        t = TriangulationTelemetry()
        for _ in range(10):
            t.record_attempt("voting_fallback")
        assert t.failure_rate == 1.0

    def test_mixed(self):
        t = TriangulationTelemetry()
        for _ in range(7):
            t.record_attempt("triangulation", 0.3, 0.001)
        for _ in range(3):
            t.record_attempt("voting_fallback")
        assert t.failure_rate == pytest.approx(0.3)


class TestFailureAlert:
    def test_no_alert_below_10_samples(self):
        t = TriangulationTelemetry()
        # All failures but only 9 samples
        for _ in range(9):
            t.record_attempt("voting_fallback")
        assert t.failure_alert_active is False

    def test_alert_above_threshold(self):
        t = TriangulationTelemetry()
        # 4 success, 7 failure = 63.6% failure
        for _ in range(4):
            t.record_attempt("triangulation", 0.3, 0.001)
        for _ in range(7):
            t.record_attempt("voting_fallback")
        assert t.failure_alert_active is True

    def test_no_alert_at_threshold(self):
        t = TriangulationTelemetry()
        # 7 success, 3 failure = 30% failure (not > 30%)
        for _ in range(7):
            t.record_attempt("triangulation", 0.3, 0.001)
        for _ in range(3):
            t.record_attempt("voting_fallback")
        assert t.failure_alert_active is False

    def test_alert_just_above_threshold(self):
        t = TriangulationTelemetry()
        # 69 success, 31 failure = 31% > 30%
        for _ in range(69):
            t.record_attempt("triangulation", 0.3, 0.001)
        for _ in range(31):
            t.record_attempt("voting_fallback")
        assert t.failure_alert_active is True


class TestBufferOverflow:
    def test_ring_buffer_max(self):
        t = TriangulationTelemetry(max_samples=5)
        for i in range(10):
            t.record_attempt("triangulation", float(i), 0.001)
        assert t.sample_count == 5
        # Lifetime counters still reflect all 10
        assert t.total_attempts == 10
        assert t.triangulation_ok == 10


class TestSummary:
    def test_empty_summary(self):
        t = TriangulationTelemetry()
        s = t.get_summary()
        assert s["samples"] == 0
        assert s["failure_rate"] == 0.0
        assert s["failure_alert"] is False

    def test_summary_with_reproj_and_z(self):
        t = TriangulationTelemetry()
        t.record_attempt("triangulation", 0.5, 0.002)
        t.record_attempt("triangulation", 1.5, 0.008)
        t.record_attempt("z_rejected", 3.0, 0.05)
        s = t.get_summary()
        assert s["samples"] == 3
        assert s["reproj_min"] == 0.5
        assert s["reproj_max"] == 3.0
        assert s["reproj_avg"] == pytest.approx(1.6667, rel=1e-3)
        assert s["z_depth_min"] == 0.002
        assert s["z_depth_max"] == 0.05

    def test_summary_no_reproj(self):
        t = TriangulationTelemetry()
        t.record_attempt("voting_fallback")
        s = t.get_summary()
        assert "reproj_min" not in s
        assert "z_depth_min" not in s
