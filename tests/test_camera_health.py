"""Tests for CameraHealthMonitor (P30)."""
import time
from unittest.mock import MagicMock

from src.web.camera_health import CameraHealthMonitor


def _make_multi_pipeline(configs, errors=None, pipelines=None):
    mp = MagicMock()
    mp.camera_configs = configs
    mp.get_camera_errors.return_value = errors or {}
    mp.get_pipelines.return_value = pipelines or {}
    return mp


def _make_pipeline_with_fps(fps):
    p = MagicMock()
    p.get_stats.return_value = {"fps": fps}
    return p


class TestCameraHealthMonitor:
    def test_all_green(self):
        configs = [{"camera_id": "cam_0"}, {"camera_id": "cam_1"}]
        pipelines = {
            "cam_0": _make_pipeline_with_fps(30.0),
            "cam_1": _make_pipeline_with_fps(25.0),
        }
        mp = _make_multi_pipeline(configs, errors={}, pipelines=pipelines)
        monitor = CameraHealthMonitor()
        result = monitor.check_health(mp)
        assert result["cam_0"]["status"] == "green"
        assert result["cam_1"]["status"] == "green"

    def test_error_is_red(self):
        configs = [{"camera_id": "cam_0"}]
        pipelines = {"cam_0": _make_pipeline_with_fps(25.0)}
        mp = _make_multi_pipeline(configs, errors={"cam_0": "Disconnected"}, pipelines=pipelines)
        monitor = CameraHealthMonitor()
        result = monitor.check_health(mp)
        assert result["cam_0"]["status"] == "red"
        assert result["cam_0"]["error"] == "Disconnected"

    def test_low_fps_is_yellow(self):
        configs = [{"camera_id": "cam_0"}]
        pipelines = {"cam_0": _make_pipeline_with_fps(5.0)}
        mp = _make_multi_pipeline(configs, errors={}, pipelines=pipelines)
        monitor = CameraHealthMonitor()
        result = monitor.check_health(mp)
        assert result["cam_0"]["status"] == "yellow"

    def test_zero_fps_is_green(self):
        configs = [{"camera_id": "cam_0"}]
        pipelines = {"cam_0": _make_pipeline_with_fps(0.0)}
        mp = _make_multi_pipeline(configs, errors={}, pipelines=pipelines)
        monitor = CameraHealthMonitor()
        result = monitor.check_health(mp)
        assert result["cam_0"]["status"] == "green"

    def test_error_overrides_low_fps(self):
        configs = [{"camera_id": "cam_0"}]
        pipelines = {"cam_0": _make_pipeline_with_fps(5.0)}
        mp = _make_multi_pipeline(configs, errors={"cam_0": "Timeout"}, pipelines=pipelines)
        monitor = CameraHealthMonitor()
        result = monitor.check_health(mp)
        assert result["cam_0"]["status"] == "red"

    def test_includes_timestamp_and_fps(self):
        configs = [{"camera_id": "cam_0"}]
        pipelines = {"cam_0": _make_pipeline_with_fps(15.5)}
        mp = _make_multi_pipeline(configs, errors={}, pipelines=pipelines)
        monitor = CameraHealthMonitor()
        before = time.time()
        result = monitor.check_health(mp)
        after = time.time()
        cam = result["cam_0"]
        assert cam["fps"] == 15.5
        assert before - 0.1 <= cam["timestamp"] <= after + 0.1

    def test_pipeline_without_get_stats(self):
        configs = [{"camera_id": "cam_0"}]
        p = MagicMock(spec=[])  # no get_stats attribute
        mp = _make_multi_pipeline(configs, errors={}, pipelines={"cam_0": p})
        monitor = CameraHealthMonitor()
        result = monitor.check_health(mp)
        assert result["cam_0"]["fps"] == 0.0
        assert result["cam_0"]["status"] == "green"

    def test_missing_pipeline_for_camera(self):
        configs = [{"camera_id": "cam_0"}]
        mp = _make_multi_pipeline(configs, errors={}, pipelines={})
        monitor = CameraHealthMonitor()
        result = monitor.check_health(mp)
        assert result["cam_0"]["fps"] == 0.0
        assert result["cam_0"]["status"] == "green"
