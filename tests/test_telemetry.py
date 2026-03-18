"""Tests for telemetry history module."""

import json
import os
import time
import pytest
from src.utils.telemetry import TelemetryHistory, TelemetrySample, TelemetryJSONLWriter


def _sample(fps=30.0, queue=0.1, drops=0, mem=100.0, cpu=None, ts=None):
    """Helper to create a TelemetrySample."""
    return TelemetrySample(
        timestamp=ts or time.time(),
        fps=fps,
        queue_pressure=queue,
        dropped_frames=drops,
        memory_mb=mem,
        cpu_percent=cpu,
    )


class TestTelemetryHistory:
    def test_record_and_count(self):
        th = TelemetryHistory(max_samples=10)
        assert th.sample_count == 0
        th.record(_sample())
        assert th.sample_count == 1

    def test_ring_buffer_overflow(self):
        th = TelemetryHistory(max_samples=5)
        for i in range(10):
            th.record(_sample(fps=float(i)))
        assert th.sample_count == 5
        history = th.get_history()
        assert history[0]["fps"] == 5.0  # oldest remaining
        assert history[-1]["fps"] == 9.0

    def test_get_history_last_n(self):
        th = TelemetryHistory(max_samples=100)
        for i in range(20):
            th.record(_sample(fps=float(i)))
        history = th.get_history(last_n=5)
        assert len(history) == 5
        assert history[0]["fps"] == 15.0

    def test_get_history_format(self):
        th = TelemetryHistory()
        th.record(_sample(fps=25.3, queue=0.45, drops=3, mem=200.5, cpu=12.7))
        h = th.get_history()
        assert len(h) == 1
        assert h[0]["fps"] == 25.3
        assert h[0]["queue"] == 0.45
        assert h[0]["drops"] == 3
        assert h[0]["mem"] == 200.5
        assert h[0]["cpu"] == 12.7

    def test_cpu_none_in_history(self):
        th = TelemetryHistory()
        th.record(_sample(cpu=None))
        h = th.get_history()
        assert h[0]["cpu"] is None

    def test_fps_alert_not_triggered_immediately(self):
        th = TelemetryHistory(fps_alert_threshold=15.0, alert_sustain_seconds=5.0)
        th.record(_sample(fps=10.0, ts=100.0))
        assert not th.fps_alert_active  # Not enough time elapsed

    def test_fps_alert_triggered_after_sustain(self):
        th = TelemetryHistory(fps_alert_threshold=15.0, alert_sustain_seconds=5.0)
        th.record(_sample(fps=10.0, ts=100.0))
        th.record(_sample(fps=10.0, ts=106.0))
        assert th.fps_alert_active

    def test_fps_alert_clears_when_fps_recovers(self):
        th = TelemetryHistory(fps_alert_threshold=15.0, alert_sustain_seconds=2.0)
        th.record(_sample(fps=10.0, ts=100.0))
        th.record(_sample(fps=10.0, ts=103.0))
        assert th.fps_alert_active
        th.record(_sample(fps=25.0, ts=104.0))
        assert not th.fps_alert_active

    def test_fps_alert_not_triggered_at_zero_fps(self):
        """fps=0 means pipeline not running, should not alert."""
        th = TelemetryHistory(fps_alert_threshold=15.0, alert_sustain_seconds=2.0)
        th.record(_sample(fps=0.0, ts=100.0))
        th.record(_sample(fps=0.0, ts=103.0))
        assert not th.fps_alert_active

    def test_queue_alert_triggered(self):
        th = TelemetryHistory(queue_alert_threshold=0.8, alert_sustain_seconds=3.0)
        th.record(_sample(queue=0.9, ts=100.0))
        th.record(_sample(queue=0.9, ts=104.0))
        assert th.queue_alert_active

    def test_queue_alert_clears(self):
        th = TelemetryHistory(queue_alert_threshold=0.8, alert_sustain_seconds=2.0)
        th.record(_sample(queue=0.9, ts=100.0))
        th.record(_sample(queue=0.9, ts=103.0))
        assert th.queue_alert_active
        th.record(_sample(queue=0.3, ts=104.0))
        assert not th.queue_alert_active

    def test_get_alerts_format(self):
        th = TelemetryHistory(fps_alert_threshold=15.0, queue_alert_threshold=0.8)
        alerts = th.get_alerts()
        assert "fps_low" in alerts
        assert "queue_high" in alerts
        assert alerts["fps_threshold"] == 15.0
        assert alerts["queue_threshold"] == 0.8

    def test_get_summary_empty(self):
        th = TelemetryHistory()
        s = th.get_summary()
        assert s["samples"] == 0

    def test_get_summary_with_data(self):
        th = TelemetryHistory()
        th.record(_sample(fps=20.0, queue=0.3, drops=5))
        th.record(_sample(fps=30.0, queue=0.5, drops=10))
        s = th.get_summary()
        assert s["samples"] == 2
        assert s["fps_min"] == 20.0
        assert s["fps_max"] == 30.0
        assert s["fps_avg"] == 25.0
        assert s["queue_max"] == 0.5
        assert s["total_drops"] == 10

    def test_validation_max_samples(self):
        with pytest.raises(ValueError):
            TelemetryHistory(max_samples=0)

    def test_validation_fps_threshold(self):
        with pytest.raises(ValueError):
            TelemetryHistory(fps_alert_threshold=-1)

    def test_validation_queue_threshold(self):
        with pytest.raises(ValueError):
            TelemetryHistory(queue_alert_threshold=1.5)


class TestTelemetryJSONLWriter:
    def test_write_creates_file(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="abc123")
        writer.write(_sample(fps=25.0, queue=0.3, drops=2, mem=150.0, cpu=45.0, ts=1000.0))
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["session"] == "abc123"
        assert record["fps"] == 25.0
        assert record["queue"] == 0.3
        assert record["drops"] == 2
        assert record["mem"] == 150.0
        assert record["cpu"] == 45.0

    def test_write_appends(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1")
        writer.write(_sample(fps=10.0, ts=1.0))
        writer.write(_sample(fps=20.0, ts=2.0))
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 2

    def test_cpu_none(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1")
        writer.write(_sample(cpu=None, ts=1.0))
        record = json.loads(open(filepath).readline())
        assert record["cpu"] is None

    def test_from_env_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("DARTVISION_TELEMETRY_FILE", raising=False)
        assert TelemetryJSONLWriter.from_env("abc") is None

    def test_from_env_returns_writer(self, tmp_path, monkeypatch):
        filepath = str(tmp_path / "t.jsonl")
        monkeypatch.setenv("DARTVISION_TELEMETRY_FILE", filepath)
        writer = TelemetryJSONLWriter.from_env("sess1")
        assert writer is not None
        assert writer.session_id == "sess1"

    def test_attach_to_history(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1")
        th = TelemetryHistory()
        th.attach_jsonl_writer(writer)
        th.record(_sample(fps=30.0, ts=1.0))
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1

    def test_creates_directory(self, tmp_path):
        filepath = str(tmp_path / "subdir" / "deep" / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1")
        writer.write(_sample(ts=1.0))
        assert os.path.exists(filepath)


class TestTelemetryRotation:
    def test_rotation_renames_file_when_exceeds_max(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        # 1 byte max to force rotation
        writer = TelemetryJSONLWriter(filepath, session_id="s1", max_mb=0.000001)
        # Write enough to exceed limit
        for i in range(5):
            writer.write(_sample(ts=float(i)))
        # Force rotation check
        writer.force_rotate()
        # Original file should have been rotated (renamed)
        rotated = [f for f in os.listdir(tmp_path) if "telemetry_" in f]
        assert len(rotated) >= 1

    def test_rotation_happens_every_100_writes(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1", max_mb=0.000001)
        for i in range(101):
            writer.write(_sample(ts=float(i)))
        rotated = [f for f in os.listdir(tmp_path) if "telemetry_" in f]
        assert len(rotated) >= 1

    def test_no_rotation_when_under_limit(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1", max_mb=50)
        writer.write(_sample(ts=1.0))
        writer.force_rotate()
        rotated = [f for f in os.listdir(tmp_path) if "telemetry_" in f]
        assert len(rotated) == 0


class TestTelemetryCleanup:
    def test_cleanup_deletes_old_files(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1", retain_days=1)
        # Create a fake rotated file with old mtime
        old_file = tmp_path / "telemetry_20200101_000000.jsonl"
        old_file.write_text("old data\n")
        old_mtime = time.time() - 86400 * 10  # 10 days ago
        os.utime(str(old_file), (old_mtime, old_mtime))
        deleted = writer.cleanup_old_files()
        assert deleted == 1
        assert not old_file.exists()

    def test_cleanup_keeps_recent_files(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1", retain_days=7)
        recent = tmp_path / "telemetry_20260318_120000.jsonl"
        recent.write_text("recent data\n")
        deleted = writer.cleanup_old_files()
        assert deleted == 0
        assert recent.exists()

    def test_cleanup_zero_retain_days_noop(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1", retain_days=0)
        old_file = tmp_path / "telemetry_20200101_000000.jsonl"
        old_file.write_text("old\n")
        old_mtime = time.time() - 86400 * 100
        os.utime(str(old_file), (old_mtime, old_mtime))
        deleted = writer.cleanup_old_files()
        assert deleted == 0


class TestTelemetryCheckFileSize:
    def test_check_size_no_file(self, tmp_path):
        filepath = str(tmp_path / "nonexistent.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1", max_mb=10)
        info = writer.check_file_size()
        assert info["size_mb"] == 0.0
        assert info["warning"] is None

    def test_check_size_small_file(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1", max_mb=10)
        writer.write(_sample(ts=1.0))
        info = writer.check_file_size()
        assert info["size_mb"] < 1.0
        assert info["warning"] is None
        assert info["max_mb"] == 10.0

    def test_check_size_warning_at_80_pct(self, tmp_path):
        filepath = str(tmp_path / "telemetry.jsonl")
        # Write data first, then create writer with tiny max
        with open(filepath, "w") as f:
            f.write("x" * 200)
        writer = TelemetryJSONLWriter(filepath, session_id="s1", max_mb=0.0001)
        info = writer.check_file_size()
        assert info["warning"] is not None
        assert "MB" in info["warning"]

    def test_force_rotate_then_cleanup(self, tmp_path):
        """Integration: force_rotate + cleanup_old_files work together."""
        filepath = str(tmp_path / "telemetry.jsonl")
        writer = TelemetryJSONLWriter(filepath, session_id="s1", max_mb=0.000001, retain_days=0)
        # Write data to create a file
        for i in range(5):
            writer.write(_sample(ts=float(i)))
        writer.force_rotate()
        # With retain_days=0, cleanup is a no-op
        assert writer.cleanup_old_files() == 0

    def test_from_env_with_config(self, tmp_path, monkeypatch):
        filepath = str(tmp_path / "t.jsonl")
        monkeypatch.setenv("DARTVISION_TELEMETRY_FILE", filepath)
        monkeypatch.setenv("DARTVISION_TELEMETRY_MAX_MB", "25")
        monkeypatch.setenv("DARTVISION_TELEMETRY_RETAIN_DAYS", "3")
        writer = TelemetryJSONLWriter.from_env("sess1")
        assert writer is not None
        assert writer._max_bytes == 25 * 1024 * 1024
        assert writer._retain_days == 3
