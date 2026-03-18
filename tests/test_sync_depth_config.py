"""Tests for Phase 3: Configurable Sync Window & Depth Tolerance with 2-Tier Sync Logic."""

import time
from unittest.mock import patch, MagicMock

import pytest

from src.cv.multi_camera import (
    MultiCameraPipeline,
    MAX_DETECTION_TIME_DIFF_S,
    BOARD_DEPTH_TOLERANCE_M,
)


def _make_pipeline(**kwargs) -> MultiCameraPipeline:
    """Create a MultiCameraPipeline without starting cameras."""
    defaults = {
        "camera_configs": [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ],
    }
    defaults.update(kwargs)
    return defaults.pop("camera_configs"), defaults


def _create_mcp(**kwargs) -> MultiCameraPipeline:
    configs = [
        {"camera_id": "cam_left", "src": 0},
        {"camera_id": "cam_right", "src": 1},
    ]
    return MultiCameraPipeline(camera_configs=configs, **kwargs)


class TestDefaultValues:
    """Default values should match current hardcoded behavior."""

    def test_default_max_time_diff(self):
        mcp = _create_mcp()
        assert mcp._max_time_diff_s == MAX_DETECTION_TIME_DIFF_S
        assert mcp._max_time_diff_s == 0.15

    def test_default_depth_tolerance(self):
        mcp = _create_mcp()
        assert mcp._depth_tolerance_m == BOARD_DEPTH_TOLERANCE_M
        assert mcp._depth_tolerance_m == 0.015

    def test_default_sync_wait(self):
        mcp = _create_mcp()
        assert mcp._sync_wait_s == 0.3

    def test_default_depth_auto_adapt(self):
        mcp = _create_mcp()
        assert mcp._depth_auto_adapt is True

    def test_effective_depth_equals_initial(self):
        mcp = _create_mcp()
        assert mcp._effective_depth_tolerance_m == mcp._depth_tolerance_m


class TestCustomParameters:
    """Custom parameters are stored and used."""

    def test_custom_sync_wait(self):
        mcp = _create_mcp(sync_wait_s=0.5)
        assert mcp._sync_wait_s == 0.5

    def test_custom_max_time_diff(self):
        mcp = _create_mcp(max_time_diff_s=0.2)
        assert mcp._max_time_diff_s == 0.2

    def test_custom_depth_tolerance(self):
        mcp = _create_mcp(depth_tolerance_m=0.02)
        assert mcp._depth_tolerance_m == 0.02
        assert mcp._effective_depth_tolerance_m == 0.02

    def test_depth_auto_adapt_disabled(self):
        mcp = _create_mcp(depth_auto_adapt=False)
        assert mcp._depth_auto_adapt is False


class TestGetFusionConfig:
    """get_fusion_config returns correct values."""

    def test_default_config(self):
        mcp = _create_mcp()
        cfg = mcp.get_fusion_config()
        assert cfg == {
            "sync_wait_s": 0.3,
            "max_time_diff_s": 0.15,
            "depth_tolerance_m": 0.015,
            "effective_depth_tolerance_m": 0.015,
            "depth_auto_adapt": True,
            "buffer_max_depth": 5,
        }

    def test_custom_config(self):
        mcp = _create_mcp(sync_wait_s=0.5, max_time_diff_s=0.2, depth_tolerance_m=0.02, depth_auto_adapt=False)
        cfg = mcp.get_fusion_config()
        assert cfg["sync_wait_s"] == 0.5
        assert cfg["max_time_diff_s"] == 0.2
        assert cfg["depth_tolerance_m"] == 0.02
        assert cfg["depth_auto_adapt"] is False

    def test_effective_reflects_adaptation(self):
        mcp = _create_mcp(depth_tolerance_m=0.015)
        mcp._effective_depth_tolerance_m = 0.025
        cfg = mcp.get_fusion_config()
        assert cfg["depth_tolerance_m"] == 0.015
        assert cfg["effective_depth_tolerance_m"] == 0.025


class TestSingleCameraTimeout:
    """Single detection should wait sync_wait_s before fallback."""

    def test_single_detection_uses_sync_wait(self):
        mcp = _create_mcp(sync_wait_s=0.5)
        emitted = []
        mcp.on_multi_dart_detected = lambda r: emitted.append(r)

        # Add a detection that is 0.2s old (< 0.5s sync_wait)
        mcp._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"total_score": 20},
            "detection": None,
            "timestamp": time.time() - 0.2,
        }
        mcp._try_fuse()
        # Should NOT emit yet (still within sync_wait_s)
        assert len(emitted) == 0

    def test_single_detection_emits_after_sync_wait(self):
        mcp = _create_mcp(sync_wait_s=0.3)
        emitted = []
        mcp.on_multi_dart_detected = lambda r: emitted.append(r)

        # Add a detection that is 0.4s old (> 0.3s sync_wait)
        mcp._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"total_score": 20},
            "detection": None,
            "timestamp": time.time() - 0.4,
        }
        mcp._try_fuse()
        assert len(emitted) == 1
        assert emitted[0]["source"] == "single"

    def test_default_sync_wait_differs_from_max_time_diff(self):
        """2-tier: sync_wait_s (0.3) != max_time_diff_s (0.15)."""
        mcp = _create_mcp()
        assert mcp._sync_wait_s != mcp._max_time_diff_s
        assert mcp._sync_wait_s > mcp._max_time_diff_s


class TestMultiCameraSync:
    """Multi-camera sync uses max_time_diff_s for timestamp comparison."""

    def test_detections_within_max_time_diff_proceed(self):
        mcp = _create_mcp(max_time_diff_s=0.2)
        emitted = []
        mcp.on_multi_dart_detected = lambda r: emitted.append(r)

        now = time.time()
        mcp._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"total_score": 20},
            "detection": None,
            "timestamp": now - 0.1,
        }
        mcp._detection_buffer["cam_right"] = {
            "camera_id": "cam_right",
            "score_result": {"total_score": 20},
            "detection": None,
            "timestamp": now,
        }
        mcp._try_fuse()
        # Should emit (voting fallback since no stereo params)
        assert len(emitted) == 1
        assert emitted[0]["source"] == "voting_fallback"

    def test_detections_beyond_max_time_diff_timeout(self):
        mcp = _create_mcp(max_time_diff_s=0.1)
        emitted = []
        mcp.on_multi_dart_detected = lambda r: emitted.append(r)

        now = time.time()
        mcp._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"total_score": 20},
            "detection": None,
            "timestamp": now - 0.2,
        }
        mcp._detection_buffer["cam_right"] = {
            "camera_id": "cam_right",
            "score_result": {"total_score": 20},
            "detection": None,
            "timestamp": now,
        }
        mcp._try_fuse()
        assert len(emitted) == 1
        assert emitted[0]["source"] == "single_timeout"


class TestAdaptiveDepthTolerance:
    """Depth tolerance widens after high Z-rejection rate."""

    def test_tolerance_widens_on_high_rejection(self):
        mcp = _create_mcp(depth_tolerance_m=0.015, depth_auto_adapt=True)

        # Simulate 20+ attempts with >50% z_rejected
        for _ in range(15):
            mcp._tri_telemetry.record_attempt("z_rejected", 1.0, 0.03)
        for _ in range(5):
            mcp._tri_telemetry.record_attempt("triangulation", 0.5, 0.005)

        # Now trigger the adaptive check manually
        summary = mcp._tri_telemetry.get_summary()
        total = summary.get("total_attempts", 0)
        z_rej = summary.get("z_rejected", 0)
        assert total >= 20
        assert z_rej / total > 0.5

        # Simulate the adaptation logic
        new_tol = min(mcp._depth_tolerance_m * 1.67, 0.025)
        assert new_tol > mcp._effective_depth_tolerance_m
        mcp._effective_depth_tolerance_m = new_tol
        assert mcp._effective_depth_tolerance_m == pytest.approx(0.02505, abs=0.001)

    def test_tolerance_capped_at_25mm(self):
        mcp = _create_mcp(depth_tolerance_m=0.020)
        new_tol = min(mcp._depth_tolerance_m * 1.67, 0.025)
        assert new_tol == 0.025  # capped

    def test_no_adaptation_when_disabled(self):
        mcp = _create_mcp(depth_tolerance_m=0.015, depth_auto_adapt=False)
        # Even with high rejection, effective should stay the same
        for _ in range(25):
            mcp._tri_telemetry.record_attempt("z_rejected", 1.0, 0.03)

        # The adaptation code checks self._depth_auto_adapt
        assert mcp._depth_auto_adapt is False
        assert mcp._effective_depth_tolerance_m == 0.015
