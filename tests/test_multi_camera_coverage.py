"""Coverage tests for multi_camera.py — FPSGovernor, stop(), _load_extrinsics(),
_apply_exposure_gain(), reload_stereo_params(), _apply_camera_profile(),
_notify_camera_errors(), and _try_fuse triangulation-success branch.

Targets: multi_camera.py 62% → 70%+
"""

import time
import threading
from dataclasses import dataclass, field
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from src.cv.multi_camera import (
    FPSGovernor,
    MultiCameraPipeline,
    MAX_DETECTION_TIME_DIFF_S,
    BOARD_DEPTH_TOLERANCE_M,
    _TARGET_FPS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class FakeDetection:
    """Minimal detection mock."""
    center: tuple = (200, 200)
    tip: tuple = (200, 210)
    raw_center: tuple = (200, 200)
    raw_tip: tuple = (200, 210)
    area: float = 100.0
    confidence: float = 0.8
    quality: float = 0.7
    frame_count: int = 3


@dataclass
class FakeIntrinsics:
    """Minimal intrinsics mock."""
    camera_matrix: np.ndarray = field(default_factory=lambda: np.eye(3) * 500)
    dist_coeffs: np.ndarray = field(default_factory=lambda: np.zeros((5, 1)))


def _make_pipeline(load_yaml=False, **kwargs):
    """Convenience factory for MultiCameraPipeline with YAML loading disabled."""
    return MultiCameraPipeline(
        camera_configs=kwargs.pop("camera_configs", []),
        load_config_from_yaml=load_yaml,
        **kwargs,
    )


# ===========================================================================
# FPSGovernor tests
# ===========================================================================

class TestFPSGovernorInit:
    def test_default_values(self):
        gov = FPSGovernor()
        assert gov._target_fps == 30
        assert gov._min_fps == 10
        assert gov._is_primary is True
        assert gov._buffer_max_depth == 5
        assert gov._frames_dropped == 0
        assert gov._frames_total == 0

    def test_custom_values(self):
        gov = FPSGovernor(target_fps=15, min_fps=5, is_primary=False, buffer_max_depth=10)
        assert gov._target_fps == 15
        assert gov._min_fps == 5
        assert gov._is_primary is False
        assert gov._buffer_max_depth == 10


class TestFPSGovernorShouldSkipFrame:
    def test_skip_when_buffer_full(self):
        gov = FPSGovernor(buffer_max_depth=3)
        assert gov.should_skip_frame(3) is True
        assert gov._frames_dropped == 1

    def test_no_skip_when_buffer_below_max(self):
        gov = FPSGovernor(buffer_max_depth=3)
        assert gov.should_skip_frame(2) is False
        assert gov._frames_dropped == 0

    def test_skip_increments_dropped_counter(self):
        gov = FPSGovernor(buffer_max_depth=2)
        gov.should_skip_frame(5)
        gov.should_skip_frame(5)
        gov.should_skip_frame(5)
        assert gov._frames_dropped == 3

    def test_no_skip_at_zero_depth(self):
        gov = FPSGovernor(buffer_max_depth=5)
        assert gov.should_skip_frame(0) is False


class TestFPSGovernorRecordFrameTime:
    def test_increments_total_counter(self):
        gov = FPSGovernor()
        gov.record_frame_time(0.01)
        gov.record_frame_time(0.01)
        assert gov._frames_total == 2

    def test_ring_buffer_capped(self):
        gov = FPSGovernor()
        gov._max_samples = 5
        for _ in range(10):
            gov.record_frame_time(0.01)
        assert len(gov._processing_times) == 5

    def test_overload_detection_increments(self):
        """Frame time > 80% of budget should increment overload counter."""
        gov = FPSGovernor(target_fps=10)  # budget = 0.1s
        gov._effective_fps = 10.0
        # 0.09s > 0.8 * 0.1 = 0.08
        gov.record_frame_time(0.09)
        assert gov._overload_count == 1

    def test_no_overload_on_fast_frame(self):
        gov = FPSGovernor(target_fps=10)
        gov._effective_fps = 10.0
        gov.record_frame_time(0.05)  # 0.05 < 0.08
        assert gov._overload_count == 0

    def test_overload_count_decrements_on_fast_frame(self):
        gov = FPSGovernor(target_fps=10)
        gov._effective_fps = 10.0
        gov._overload_count = 5
        gov.record_frame_time(0.05)
        assert gov._overload_count == 4

    def test_fps_reduction_on_secondary_camera(self):
        """Secondary camera should reduce FPS after sustained overload."""
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        gov._overload_threshold = 3
        # Simulate 3 overloaded frames
        for _ in range(3):
            gov.record_frame_time(1.0)  # way over budget
        # FPS should have been reduced
        assert gov._effective_fps < 30.0
        assert gov._effective_fps >= 10.0

    def test_no_fps_reduction_on_primary_camera(self):
        """Primary camera should NOT reduce FPS even when overloaded."""
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=True)
        gov._overload_threshold = 3
        for _ in range(5):
            gov.record_frame_time(1.0)
        assert gov._effective_fps == 30.0

    def test_fps_recovery_when_load_drops(self):
        """FPS should recover toward target when avg processing time drops."""
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        gov._max_samples = 5
        # Reduce FPS first
        gov._effective_fps = 15.0
        # Fill buffer with fast frames (well under 50% of target budget)
        target_budget = 1.0 / 30.0  # ~0.033s
        for _ in range(5):
            gov.record_frame_time(target_budget * 0.3)  # ~0.01s
        # Should have recovered somewhat
        assert gov._effective_fps > 15.0

    def test_fps_does_not_exceed_target_on_recovery(self):
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        gov._max_samples = 5
        gov._effective_fps = 29.5
        for _ in range(5):
            gov.record_frame_time(0.001)
        assert gov._effective_fps <= 30.0

    def test_fps_not_reduced_below_min(self):
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=False)
        gov._overload_threshold = 2
        gov._effective_fps = 11.0
        # Even under sustained overload, should not go below min_fps
        for _ in range(10):
            gov.record_frame_time(1.0)
        assert gov._effective_fps >= 10.0


class TestFPSGovernorProperties:
    def test_frame_interval_s(self):
        gov = FPSGovernor(target_fps=20)
        assert gov.frame_interval_s == pytest.approx(1.0 / 20.0)

    def test_effective_fps_rounded(self):
        gov = FPSGovernor(target_fps=30)
        gov._effective_fps = 24.567
        assert gov.effective_fps == 24.6

    def test_get_stats_keys(self):
        gov = FPSGovernor(target_fps=30, min_fps=10, is_primary=True, buffer_max_depth=5)
        gov.record_frame_time(0.02)
        stats = gov.get_stats()
        assert stats["target_fps"] == 30
        assert stats["is_primary"] is True
        assert stats["buffer_max_depth"] == 5
        assert "effective_fps" in stats
        assert "avg_processing_ms" in stats
        assert "overload_count" in stats
        assert "frames_dropped" in stats
        assert "frames_total" in stats
        assert stats["frames_total"] == 1

    def test_get_stats_avg_time_zero_when_empty(self):
        gov = FPSGovernor()
        stats = gov.get_stats()
        assert stats["avg_processing_ms"] == 0.0


# ===========================================================================
# MultiCameraPipeline: stop()
# ===========================================================================

class TestMultiCameraPipelineStop:
    def test_stop_sets_running_false(self):
        mcp = _make_pipeline()
        mcp._running = True
        mcp.stop()
        assert mcp._running is False

    def test_stop_calls_pipeline_stop(self):
        mcp = _make_pipeline()
        mcp._running = True
        p1 = MagicMock()
        p2 = MagicMock()
        mcp._pipelines = {"cam1": p1, "cam2": p2}
        mcp._threads = {
            "cam1": MagicMock(spec=threading.Thread),
            "cam2": MagicMock(spec=threading.Thread),
        }
        mcp.stop()
        p1.stop.assert_called_once()
        p2.stop.assert_called_once()

    def test_stop_joins_threads(self):
        mcp = _make_pipeline()
        mcp._running = True
        t1 = MagicMock(spec=threading.Thread)
        t2 = MagicMock(spec=threading.Thread)
        mcp._pipelines = {"cam1": MagicMock(), "cam2": MagicMock()}
        mcp._threads = {"cam1": t1, "cam2": t2}
        mcp.stop()
        t1.join.assert_called_once_with(timeout=5.0)
        t2.join.assert_called_once_with(timeout=5.0)

    def test_stop_joins_fusion_thread(self):
        mcp = _make_pipeline()
        mcp._running = True
        mcp._pipelines = {}
        mcp._threads = {}
        ft = MagicMock(spec=threading.Thread)
        mcp._fusion_thread = ft
        mcp.stop()
        ft.join.assert_called_once_with(timeout=5.0)

    def test_stop_no_fusion_thread(self):
        """stop() should not crash when fusion_thread is None."""
        mcp = _make_pipeline()
        mcp._running = True
        mcp._pipelines = {}
        mcp._threads = {}
        mcp._fusion_thread = None
        mcp.stop()  # should not raise


# ===========================================================================
# _apply_camera_profile()
# ===========================================================================

class TestApplyCameraProfile:
    def test_logs_profile_keys(self):
        mcp = _make_pipeline()
        cfg = {"camera_id": "cam1", "src": 0, "exposure": -5, "gain": 1.5, "diff_threshold": 40}
        # Should not raise; just logs
        mcp._apply_camera_profile("cam1", cfg)

    def test_no_profile_keys(self):
        mcp = _make_pipeline()
        cfg = {"camera_id": "cam1", "src": 0}
        mcp._apply_camera_profile("cam1", cfg)  # no crash


# ===========================================================================
# _apply_exposure_gain()
# ===========================================================================

class TestApplyExposureGain:
    def test_applies_exposure_and_gain(self):
        configs = [{"camera_id": "cam1", "src": 0, "exposure": -3, "gain": 2.0}]
        mcp = _make_pipeline(camera_configs=configs)
        mock_pipeline = MagicMock()
        mock_cam = MagicMock()
        mock_cam.set_exposure = MagicMock()
        mock_cam.set_gain = MagicMock()
        mock_pipeline.camera = mock_cam
        mcp._apply_exposure_gain("cam1", mock_pipeline)
        mock_cam.set_exposure.assert_called_once_with(-3)
        mock_cam.set_gain.assert_called_once_with(2.0)

    def test_skips_when_no_exposure_configured(self):
        configs = [{"camera_id": "cam1", "src": 0}]
        mcp = _make_pipeline(camera_configs=configs)
        mock_pipeline = MagicMock()
        mock_cam = MagicMock()
        mock_cam.set_exposure = MagicMock()
        mock_cam.set_gain = MagicMock()
        mock_pipeline.camera = mock_cam
        mcp._apply_exposure_gain("cam1", mock_pipeline)
        mock_cam.set_exposure.assert_not_called()
        mock_cam.set_gain.assert_not_called()

    def test_skips_when_camera_has_no_set_exposure(self):
        configs = [{"camera_id": "cam1", "src": 0, "exposure": -3}]
        mcp = _make_pipeline(camera_configs=configs)
        mock_pipeline = MagicMock()
        mock_pipeline.camera = object()  # no set_exposure attr
        mcp._apply_exposure_gain("cam1", mock_pipeline)  # should not raise

    def test_unknown_camera_id_is_noop(self):
        configs = [{"camera_id": "cam1", "src": 0, "exposure": -3}]
        mcp = _make_pipeline(camera_configs=configs)
        mock_pipeline = MagicMock()
        mcp._apply_exposure_gain("cam_unknown", mock_pipeline)  # should not raise


# ===========================================================================
# _load_extrinsics()
# ===========================================================================

class TestLoadExtrinsics:
    def test_loads_board_transforms(self):
        configs = [{"camera_id": "cam1", "src": 0}]
        mcp = _make_pipeline(camera_configs=configs)
        R = np.eye(3).tolist()
        t = [0.0, 0.0, 1.0]
        with patch("src.cv.multi_camera.get_board_transform", return_value={"R_cb": R, "t_cb": t}):
            with patch("src.cv.multi_camera.get_stereo_pair", return_value=None):
                mcp._load_extrinsics()
        assert "cam1" in mcp._board_transforms
        np.testing.assert_array_almost_equal(mcp._board_transforms["cam1"]["R_cb"], np.eye(3))
        np.testing.assert_array_almost_equal(mcp._board_transforms["cam1"]["t_cb"], [0, 0, 1])

    def test_missing_board_transform_logged(self):
        configs = [{"camera_id": "cam1", "src": 0}]
        mcp = _make_pipeline(camera_configs=configs)
        with patch("src.cv.multi_camera.get_board_transform", return_value=None):
            with patch("src.cv.multi_camera.get_stereo_pair", return_value=None):
                mcp._load_extrinsics()
        assert "cam1" not in mcp._board_transforms

    def test_invalid_board_transform_handled(self):
        configs = [{"camera_id": "cam1", "src": 0}]
        mcp = _make_pipeline(camera_configs=configs)
        with patch("src.cv.multi_camera.get_board_transform", return_value={"R_cb": "bad", "t_cb": "bad"}):
            with patch("src.cv.multi_camera.get_stereo_pair", return_value=None):
                mcp._load_extrinsics()
        assert "cam1" not in mcp._board_transforms

    def test_loads_stereo_pair(self):
        configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ]
        mcp = _make_pipeline(camera_configs=configs)
        # Set up mock pipelines with intrinsics
        p_left = MagicMock()
        p_left.camera_calibration.get_intrinsics.return_value = FakeIntrinsics()
        p_left.camera_calibration._config_io.get_config.return_value = {}
        p_right = MagicMock()
        p_right.camera_calibration.get_intrinsics.return_value = FakeIntrinsics()
        p_right.camera_calibration._config_io.get_config.return_value = {}
        mcp._pipelines = {"cam_left": p_left, "cam_right": p_right}

        pair_data = {
            "R": np.eye(3).flatten().tolist(),
            "T": [0.1, 0.0, 0.0],
        }
        with patch("src.cv.multi_camera.get_board_transform", return_value=None):
            with patch("src.cv.multi_camera.get_stereo_pair", return_value=pair_data):
                mcp._load_extrinsics()
        assert "cam_left" in mcp._stereo_params
        assert "cam_right" in mcp._stereo_params
        # cam_left should be identity (world origin)
        np.testing.assert_array_almost_equal(mcp._stereo_params["cam_left"].R, np.eye(3))
        # cam_right should have the stereo R/T
        np.testing.assert_array_almost_equal(mcp._stereo_params["cam_right"].R, np.eye(3))

    def test_missing_intrinsics_skips_pair(self):
        configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ]
        mcp = _make_pipeline(camera_configs=configs)
        p_left = MagicMock()
        p_left.camera_calibration.get_intrinsics.return_value = None
        p_right = MagicMock()
        p_right.camera_calibration.get_intrinsics.return_value = FakeIntrinsics()
        mcp._pipelines = {"cam_left": p_left, "cam_right": p_right}

        pair_data = {"R": np.eye(3).flatten().tolist(), "T": [0.1, 0.0, 0.0]}
        with patch("src.cv.multi_camera.get_board_transform", return_value=None):
            with patch("src.cv.multi_camera.get_stereo_pair", return_value=pair_data):
                mcp._load_extrinsics()
        assert len(mcp._stereo_params) == 0

    def test_stale_stereo_warning(self):
        """When lens calibration is newer than stereo, a warning should be logged."""
        configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ]
        mcp = _make_pipeline(camera_configs=configs)
        p_left = MagicMock()
        p_left.camera_calibration.get_intrinsics.return_value = FakeIntrinsics()
        p_left.camera_calibration._config_io.get_config.return_value = {
            "lens_last_update_utc": "2026-03-25T12:00:00"
        }
        p_right = MagicMock()
        p_right.camera_calibration.get_intrinsics.return_value = FakeIntrinsics()
        p_right.camera_calibration._config_io.get_config.return_value = {}
        mcp._pipelines = {"cam_left": p_left, "cam_right": p_right}

        pair_data = {
            "R": np.eye(3).flatten().tolist(),
            "T": [0.1, 0.0, 0.0],
            "calibrated_utc": "2026-03-20T10:00:00",
        }
        with patch("src.cv.multi_camera.get_board_transform", return_value=None):
            with patch("src.cv.multi_camera.get_stereo_pair", return_value=pair_data):
                # Should not raise, just log warning
                mcp._load_extrinsics()
        assert "cam_left" in mcp._stereo_params


# ===========================================================================
# reload_stereo_params()
# ===========================================================================

class TestReloadStereoParams:
    def test_clears_and_reloads(self):
        mcp = _make_pipeline(camera_configs=[{"camera_id": "cam1", "src": 0}])
        mcp._stereo_params = {"old": "data"}
        mcp._board_transforms = {"old": "data"}

        with patch("src.cv.multi_camera.get_board_transform", return_value=None):
            with patch("src.cv.multi_camera.get_stereo_pair", return_value=None):
                mcp.reload_stereo_params()

        assert "old" not in mcp._stereo_params
        assert "old" not in mcp._board_transforms


# ===========================================================================
# _notify_camera_errors()
# ===========================================================================

class TestNotifyCameraErrors:
    def test_calls_callback(self):
        cb = MagicMock()
        mcp = _make_pipeline(on_camera_errors_changed=cb)
        mcp._set_camera_error("cam1", "Test error", level="warning")
        cb.assert_called()
        args = cb.call_args[0][0]
        assert "cam1" in args

    def test_callback_exception_handled(self):
        cb = MagicMock(side_effect=RuntimeError("callback fail"))
        mcp = _make_pipeline(on_camera_errors_changed=cb)
        # Should not raise
        mcp._set_camera_error("cam1", "Test error", level="error")

    def test_clear_notifies(self):
        cb = MagicMock()
        mcp = _make_pipeline(on_camera_errors_changed=cb)
        mcp._camera_errors["cam1"] = {"message": "err", "timestamp": 0, "level": "error"}
        mcp._clear_camera_error("cam1")
        # callback called on clear
        assert cb.call_count >= 1


# ===========================================================================
# reset_all()
# ===========================================================================

class TestResetAll:
    def test_resets_pipelines_and_buffer(self):
        mcp = _make_pipeline()
        p1 = MagicMock()
        p2 = MagicMock()
        mcp._pipelines = {"cam1": p1, "cam2": p2}
        mcp._detection_buffer = {"cam1": {"data": "something"}}
        mcp.reset_all()
        p1.reset_turn.assert_called_once()
        p2.reset_turn.assert_called_once()
        assert len(mcp._detection_buffer) == 0


# ===========================================================================
# get_* accessor methods
# ===========================================================================

class TestAccessors:
    def test_get_pipelines_returns_copy(self):
        mcp = _make_pipeline()
        p1 = MagicMock()
        mcp._pipelines = {"cam1": p1}
        result = mcp.get_pipelines()
        assert result == {"cam1": p1}
        # Mutation should not affect internal state
        result["cam2"] = MagicMock()
        assert "cam2" not in mcp._pipelines

    def test_get_fusion_config(self):
        mcp = _make_pipeline(sync_wait_s=1.5)
        cfg = mcp.get_fusion_config()
        assert cfg["sync_wait_s"] == 1.5
        assert "max_time_diff_s" in cfg
        assert "depth_tolerance_m" in cfg
        assert "effective_depth_tolerance_m" in cfg
        assert "depth_auto_adapt" in cfg
        assert "buffer_max_depth" in cfg

    def test_get_triangulation_telemetry(self):
        mcp = _make_pipeline()
        tel = mcp.get_triangulation_telemetry()
        assert isinstance(tel, dict)

    def test_get_governor_stats(self):
        mcp = _make_pipeline()
        gov = FPSGovernor(target_fps=30)
        mcp._governors = {"cam1": gov}
        stats = mcp.get_governor_stats()
        assert "cam1" in stats
        assert stats["cam1"]["target_fps"] == 30

    def test_get_degraded_cameras_empty(self):
        mcp = _make_pipeline()
        assert mcp.get_degraded_cameras() == []

    def test_get_degraded_cameras_populated(self):
        mcp = _make_pipeline()
        mcp._camera_degraded.add("cam1")
        assert "cam1" in mcp.get_degraded_cameras()

    def test_get_camera_errors_returns_copy(self):
        mcp = _make_pipeline()
        mcp._camera_errors["cam1"] = {"message": "err", "timestamp": 0, "level": "error"}
        result = mcp.get_camera_errors()
        result["cam2"] = {"message": "new"}
        assert "cam2" not in mcp._camera_errors


# ===========================================================================
# _try_fuse: triangulation success path
# ===========================================================================

class TestTryFuseTriangulationSuccess:
    """Test the triangulation success branch in _try_fuse."""

    def test_triangulation_success_emits_result(self):
        mcp = _make_pipeline()
        callback = MagicMock()
        mcp.on_multi_dart_detected = callback

        # Set up two detections within time window
        now = time.time()
        det1 = FakeDetection(confidence=0.9, quality=0.8)
        det2 = FakeDetection(confidence=0.85, quality=0.7)
        mcp._detection_buffer = {
            "cam_left": {
                "camera_id": "cam_left",
                "score_result": {"total_score": 20, "ring": "single", "sector": 20, "multiplier": 1},
                "detection": det1,
                "timestamp": now,
            },
            "cam_right": {
                "camera_id": "cam_right",
                "score_result": {"total_score": 20, "ring": "single", "sector": 20, "multiplier": 1},
                "detection": det2,
                "timestamp": now + 0.05,
            },
        }

        # Mock geometry on pipeline
        mock_geo = MagicMock()
        mock_geo.double_outer_radius_px = 170.0
        mock_geo.optical_center_px = (200, 200)
        mock_hit = MagicMock()
        mock_geo.point_to_score.return_value = mock_hit
        mock_geo.hit_to_dict.return_value = {"total_score": 20, "ring": "single", "sector": 20}

        mock_pipeline = MagicMock()
        mock_pipeline.geometry = mock_geo
        mcp._pipelines = {"cam_left": mock_pipeline, "cam_right": MagicMock(geometry=None)}

        # Mock triangulate_multi_pair to return success
        tri_result = {
            "board_x_mm": 50.0,
            "board_y_mm": -30.0,
            "reprojection_error": 2.5,
            "pairs_used": 1,
            "z_depth": 0.002,
        }
        with patch("src.cv.multi_camera.triangulate_multi_pair", return_value=tri_result):
            mcp._try_fuse()

        callback.assert_called_once()
        result = callback.call_args[0][0]
        assert result["source"] == "triangulation"
        assert result["reprojection_error"] == 2.5
        assert result["pairs_used"] == 1

    def test_triangulation_failed_triggers_voting_fallback(self):
        mcp = _make_pipeline()
        callback = MagicMock()
        mcp.on_multi_dart_detected = callback

        now = time.time()
        det1 = FakeDetection(confidence=0.9, quality=0.8)
        det2 = FakeDetection(confidence=0.6, quality=0.5)
        mcp._detection_buffer = {
            "cam_left": {
                "camera_id": "cam_left",
                "score_result": {"total_score": 20, "ring": "single", "sector": 20, "multiplier": 1},
                "detection": det1,
                "timestamp": now,
            },
            "cam_right": {
                "camera_id": "cam_right",
                "score_result": {"total_score": 18, "ring": "single", "sector": 18, "multiplier": 1},
                "detection": det2,
                "timestamp": now + 0.05,
            },
        }

        tri_result = {"failed": True, "z_rejected": 2}
        with patch("src.cv.multi_camera.triangulate_multi_pair", return_value=tri_result):
            mcp._try_fuse()

        callback.assert_called_once()
        result = callback.call_args[0][0]
        assert result["source"] == "voting_fallback"

    def test_depth_auto_adapt_widens_tolerance(self):
        """High z_rejection rate should widen effective depth tolerance."""
        mcp = _make_pipeline(depth_auto_adapt=True)
        mcp._depth_tolerance_m = 0.010  # 10mm
        mcp._effective_depth_tolerance_m = 0.010
        callback = MagicMock()
        mcp.on_multi_dart_detected = callback

        # Pre-seed telemetry with many z_rejected attempts
        for _ in range(15):
            mcp._tri_telemetry.record_attempt("z_rejected")
        for _ in range(5):
            mcp._tri_telemetry.record_attempt("triangulation")

        now = time.time()
        det1 = FakeDetection(confidence=0.9, quality=0.8)
        det2 = FakeDetection(confidence=0.8, quality=0.7)
        mcp._detection_buffer = {
            "cam_left": {
                "camera_id": "cam_left",
                "score_result": {"total_score": 20},
                "detection": det1,
                "timestamp": now,
            },
            "cam_right": {
                "camera_id": "cam_right",
                "score_result": {"total_score": 20},
                "detection": det2,
                "timestamp": now + 0.05,
            },
        }

        tri_result = {"failed": True, "z_rejected": 2}
        with patch("src.cv.multi_camera.triangulate_multi_pair", return_value=tri_result):
            mcp._try_fuse()

        # Effective tolerance should have widened
        assert mcp._effective_depth_tolerance_m > 0.010


# ===========================================================================
# _voting_fallback detailed branches
# ===========================================================================

class TestVotingFallbackDetailed:
    def _make_entry(self, camera_id, total_score, confidence=0.8, quality=0.7):
        return {
            "camera_id": camera_id,
            "score_result": {"total_score": total_score, "ring": "single", "sector": total_score},
            "detection": FakeDetection(confidence=confidence, quality=quality),
            "timestamp": time.time(),
        }

    def test_two_cameras_weighted_average(self):
        mcp = _make_pipeline()
        entries = [
            self._make_entry("cam1", 20, confidence=0.9, quality=0.8),
            self._make_entry("cam2", 18, confidence=0.5, quality=0.6),
        ]
        result = mcp._voting_fallback(entries)
        assert result["source"] == "voting_fallback"
        # Weighted toward cam1 (higher confidence*quality)
        assert result["total_score"] >= 18
        assert result["total_score"] <= 20

    def test_three_cameras_uses_median(self):
        mcp = _make_pipeline()
        entries = [
            self._make_entry("cam1", 20, confidence=0.9, quality=0.8),
            self._make_entry("cam2", 18, confidence=0.8, quality=0.7),
            self._make_entry("cam3", 100, confidence=0.3, quality=0.3),  # outlier
        ]
        result = mcp._voting_fallback(entries)
        # Median of [18, 20, 100] = 20
        assert result["total_score"] == 20

    def test_fallback_to_highest_confidence_when_no_total_score(self):
        mcp = _make_pipeline()
        entries = [
            {
                "camera_id": "cam1",
                "score_result": {"ring": "miss"},  # no total_score
                "detection": FakeDetection(confidence=0.9, quality=0.8),
                "timestamp": time.time(),
            },
            {
                "camera_id": "cam2",
                "score_result": {"ring": "miss"},
                "detection": FakeDetection(confidence=0.3, quality=0.5),
                "timestamp": time.time(),
            },
        ]
        result = mcp._voting_fallback(entries)
        assert result["source"] == "voting_fallback"
        assert result["camera_id"] == "cam1"  # higher confidence

    def test_viewing_angle_quality_weights_voting(self):
        mcp = _make_pipeline()
        mcp._viewing_angle_qualities = {"cam1": 1.0, "cam2": 0.5}
        entries = [
            self._make_entry("cam1", 20, confidence=0.5, quality=0.8),
            self._make_entry("cam2", 18, confidence=0.5, quality=0.8),
        ]
        result = mcp._voting_fallback(entries)
        # cam1 has higher VAQ so should be weighted more
        assert result["total_score"] >= 19  # closer to cam1's 20


# ===========================================================================
# __init__ config loading branches
# ===========================================================================

class TestMultiCameraPipelineInitConfig:
    def test_yaml_loading_disabled(self):
        mcp = _make_pipeline(load_yaml=False)
        assert mcp._max_time_diff_s == MAX_DETECTION_TIME_DIFF_S
        assert mcp._depth_tolerance_m == BOARD_DEPTH_TOLERANCE_M

    def test_yaml_loading_with_exception(self):
        """When config loading fails, defaults should be used."""
        with patch("src.cv.multi_camera.get_sync_depth_config", side_effect=FileNotFoundError):
            with patch("src.cv.multi_camera.get_governor_config", side_effect=FileNotFoundError):
                mcp = MultiCameraPipeline(
                    camera_configs=[],
                    load_config_from_yaml=True,
                )
        assert mcp._max_time_diff_s == MAX_DETECTION_TIME_DIFF_S

    def test_explicit_args_override_yaml(self):
        mcp = MultiCameraPipeline(
            camera_configs=[],
            load_config_from_yaml=False,
            max_time_diff_s=0.999,
            depth_tolerance_m=0.555,
        )
        assert mcp._max_time_diff_s == 0.999
        assert mcp._depth_tolerance_m == 0.555


# ===========================================================================
# _degrade_camera()
# ===========================================================================

class TestDegradeCamera:
    def test_marks_camera_degraded(self):
        mcp = _make_pipeline()
        mcp._pipelines = {"cam1": MagicMock(), "cam2": MagicMock()}
        mcp._degrade_camera("cam1")
        assert "cam1" in mcp._camera_degraded
        assert "cam1" in mcp._camera_errors

    def test_remaining_cameras_in_error_message(self):
        mcp = _make_pipeline()
        mcp._pipelines = {"cam1": MagicMock(), "cam2": MagicMock()}
        mcp._degrade_camera("cam1")
        msg = mcp._camera_errors["cam1"]["message"]
        assert "cam2" in msg


# ===========================================================================
# _emit()
# ===========================================================================

class TestEmit:
    def test_emit_with_callback(self):
        cb = MagicMock()
        mcp = _make_pipeline(on_multi_dart_detected=cb)
        mcp._emit({"score": 20})
        cb.assert_called_once_with({"score": 20})

    def test_emit_no_callback(self):
        mcp = _make_pipeline()
        mcp._emit({"score": 20})  # should not raise
