"""Tests for P35 sync/depth presets and P33 governor buffer features."""

from __future__ import annotations

import pytest
import yaml

from src.utils.config import (
    SYNC_DEPTH_PRESETS,
    get_sync_depth_config,
    get_governor_config,
)
from src.cv.multi_camera import (
    FPSGovernor,
    MultiCameraPipeline,
    MAX_DETECTION_TIME_DIFF_S,
    BOARD_DEPTH_TOLERANCE_M,
)


# ── Preset definitions ──────────────────────────────────────────────

class TestSyncDepthPresets:
    def test_presets_exist(self):
        assert "tight" in SYNC_DEPTH_PRESETS
        assert "standard" in SYNC_DEPTH_PRESETS
        assert "loose" in SYNC_DEPTH_PRESETS

    def test_tight_values(self):
        p = SYNC_DEPTH_PRESETS["tight"]
        assert p["max_time_diff_s"] == 0.100
        assert p["depth_tolerance_m"] == 0.010

    def test_standard_values(self):
        p = SYNC_DEPTH_PRESETS["standard"]
        assert p["max_time_diff_s"] == 0.150
        assert p["depth_tolerance_m"] == 0.015

    def test_loose_values(self):
        p = SYNC_DEPTH_PRESETS["loose"]
        assert p["max_time_diff_s"] == 0.200
        assert p["depth_tolerance_m"] == 0.020


# ── Config loading from YAML ────────────────────────────────────────

def _write_yaml(path: str, data: dict) -> None:
    with open(path, "w") as f:
        yaml.safe_dump(data, f)


class TestGetSyncDepthConfig:
    def test_preset_tight(self, tmp_path):
        cfg_path = str(tmp_path / "mc.yaml")
        _write_yaml(cfg_path, {"sync_depth": {"preset": "tight"}})
        result = get_sync_depth_config(cfg_path)
        assert result["max_time_diff_s"] == 0.100
        assert result["depth_tolerance_m"] == 0.010

    def test_preset_loose(self, tmp_path):
        cfg_path = str(tmp_path / "mc.yaml")
        _write_yaml(cfg_path, {"sync_depth": {"preset": "loose"}})
        result = get_sync_depth_config(cfg_path)
        assert result["max_time_diff_s"] == 0.200
        assert result["depth_tolerance_m"] == 0.020

    def test_explicit_overrides_preset(self, tmp_path):
        cfg_path = str(tmp_path / "mc.yaml")
        _write_yaml(cfg_path, {
            "sync_depth": {
                "preset": "tight",
                "max_time_diff_s": 0.175,
            },
        })
        result = get_sync_depth_config(cfg_path)
        assert result["max_time_diff_s"] == 0.175  # overridden
        assert result["depth_tolerance_m"] == 0.010  # from tight preset

    def test_missing_section_falls_back_to_standard(self, tmp_path):
        cfg_path = str(tmp_path / "mc.yaml")
        _write_yaml(cfg_path, {"cameras": {}})
        result = get_sync_depth_config(cfg_path)
        assert result["max_time_diff_s"] == 0.150
        assert result["depth_tolerance_m"] == 0.015

    def test_unknown_preset_falls_back_to_standard(self, tmp_path):
        cfg_path = str(tmp_path / "mc.yaml")
        _write_yaml(cfg_path, {"sync_depth": {"preset": "ultra"}})
        result = get_sync_depth_config(cfg_path)
        assert result["max_time_diff_s"] == 0.150
        assert result["depth_tolerance_m"] == 0.015


class TestGetGovernorConfig:
    def test_defaults(self, tmp_path):
        cfg_path = str(tmp_path / "mc.yaml")
        _write_yaml(cfg_path, {})
        result = get_governor_config(cfg_path)
        assert result["secondary_target_fps"] == 15
        assert result["min_fps"] == 10
        assert result["buffer_max_depth"] == 5

    def test_custom_values(self, tmp_path):
        cfg_path = str(tmp_path / "mc.yaml")
        _write_yaml(cfg_path, {
            "governor": {
                "secondary_target_fps": 20,
                "min_fps": 5,
                "buffer_max_depth": 10,
            },
        })
        result = get_governor_config(cfg_path)
        assert result["secondary_target_fps"] == 20
        assert result["min_fps"] == 5
        assert result["buffer_max_depth"] == 10


# ── FPSGovernor buffer & backpressure ────────────────────────────────

class TestFPSGovernorBuffer:
    def test_should_skip_when_buffer_full(self):
        gov = FPSGovernor(buffer_max_depth=3)
        assert gov.should_skip_frame(3) is True
        assert gov.should_skip_frame(5) is True

    def test_should_not_skip_when_buffer_ok(self):
        gov = FPSGovernor(buffer_max_depth=3)
        assert gov.should_skip_frame(0) is False
        assert gov.should_skip_frame(2) is False

    def test_frames_dropped_counter(self):
        gov = FPSGovernor(buffer_max_depth=2)
        gov.should_skip_frame(0)  # not skipped
        gov.should_skip_frame(2)  # skipped
        gov.should_skip_frame(3)  # skipped
        assert gov._frames_dropped == 2

    def test_frames_total_counter(self):
        gov = FPSGovernor()
        gov.record_frame_time(0.01)
        gov.record_frame_time(0.02)
        assert gov._frames_total == 2

    def test_stats_include_buffer_fields(self):
        gov = FPSGovernor(buffer_max_depth=7)
        gov.should_skip_frame(10)
        gov.record_frame_time(0.01)
        stats = gov.get_stats()
        assert stats["buffer_max_depth"] == 7
        assert stats["frames_dropped"] == 1
        assert stats["frames_total"] == 1


# ── FPSGovernor adaptive FPS ─────────────────────────────────────────

class TestFPSGovernorAdaptive:
    def test_secondary_reduces_fps_on_overload(self):
        """Secondary camera should reduce FPS after sustained overload."""
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        # Simulate frames that take 90% of budget (overloaded)
        budget = 1.0 / 30
        for _ in range(15):
            gov.record_frame_time(budget * 0.9)
        assert gov.effective_fps < 30

    def test_primary_does_not_reduce_fps(self):
        """Primary camera must never reduce FPS even under overload."""
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=True)
        budget = 1.0 / 30
        for _ in range(30):
            gov.record_frame_time(budget * 0.95)
        assert gov.effective_fps == 30

    def test_fps_does_not_go_below_min(self):
        """FPS should never drop below min_fps."""
        gov = FPSGovernor(target_fps=30, min_fps=15, is_primary=False)
        budget = 1.0 / 30
        # Trigger many overload reductions
        for _ in range(200):
            gov.record_frame_time(budget * 0.95)
        assert gov.effective_fps >= 15

    def test_recovery_increases_fps(self):
        """When load drops, FPS should recover toward target."""
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        # First force a reduction
        budget = 1.0 / 30
        for _ in range(15):
            gov.record_frame_time(budget * 0.9)
        reduced = gov.effective_fps
        assert reduced < 30
        # Now simulate very fast processing to trigger recovery
        for _ in range(40):
            gov.record_frame_time(budget * 0.1)
        assert gov.effective_fps > reduced

    def test_frame_interval_matches_effective_fps(self):
        gov = FPSGovernor(target_fps=20)
        assert gov.frame_interval_s == pytest.approx(1.0 / 20)

    def test_get_stats_keys(self):
        gov = FPSGovernor(target_fps=25, min_fps=8, is_primary=False, buffer_max_depth=4)
        stats = gov.get_stats()
        assert stats["target_fps"] == 25
        assert stats["is_primary"] is False
        assert "effective_fps" in stats
        assert "avg_processing_ms" in stats
        assert "overload_count" in stats


# ── MultiCameraPipeline config integration ───────────────────────────

class TestMultiCamConfigIntegration:
    def _make(self, **kwargs):
        configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ]
        return MultiCameraPipeline(camera_configs=configs, **kwargs)

    def test_explicit_args_override_config(self):
        mcp = self._make(max_time_diff_s=0.25, depth_tolerance_m=0.022)
        assert mcp._max_time_diff_s == 0.25
        assert mcp._depth_tolerance_m == 0.022

    def test_none_args_load_from_config(self):
        """When no explicit values given, values come from YAML (standard preset)."""
        mcp = self._make()
        # Standard preset values
        assert mcp._max_time_diff_s == pytest.approx(0.15)
        assert mcp._depth_tolerance_m == pytest.approx(0.015)

    def test_load_config_disabled(self):
        mcp = self._make(load_config_from_yaml=False)
        # Should use module-level constants as fallback
        assert mcp._max_time_diff_s == MAX_DETECTION_TIME_DIFF_S
        assert mcp._depth_tolerance_m == BOARD_DEPTH_TOLERANCE_M

    def test_buffer_max_depth_in_fusion_config(self):
        mcp = self._make()
        cfg = mcp.get_fusion_config()
        assert "buffer_max_depth" in cfg
        assert isinstance(cfg["buffer_max_depth"], int)
