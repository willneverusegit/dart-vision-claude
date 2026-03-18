"""Tests for P56: Multi-Cam Error Recovery and Auto-Restart."""

import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.cv.multi_camera import MultiCameraPipeline


def _make_pipeline_mock(start_ok=True, process_ok=True):
    """Create a mock DartPipeline."""
    p = MagicMock()
    if not start_ok:
        p.start.side_effect = RuntimeError("Camera not available")
    if not process_ok:
        p.process_frame.side_effect = RuntimeError("Frame read failed")
    p.camera = MagicMock()
    p._build_camera_source.return_value = MagicMock()
    p.detector = MagicMock()
    p.board_calibration.get_viewing_angle_quality.return_value = 1.0
    p.camera_calibration.get_intrinsics.return_value = None
    p.camera_calibration.get_config.return_value = {"lens_valid": False}
    p.board_calibration.is_valid.return_value = False
    p.fps_counter.fps.return_value = 30.0
    return p


class TestStartPipelineWithRetry:
    """Tests for _start_pipeline_with_retry."""

    def test_start_succeeds_first_try(self):
        mcp = MultiCameraPipeline(
            camera_configs=[{"camera_id": "cam1", "src": 0}],
            load_config_from_yaml=False,
        )
        pipeline = _make_pipeline_mock(start_ok=True)
        result = mcp._start_pipeline_with_retry("cam1", pipeline)
        assert result is True
        pipeline.start.assert_called_once()

    def test_start_retries_on_failure(self):
        mcp = MultiCameraPipeline(
            camera_configs=[{"camera_id": "cam1", "src": 0}],
            load_config_from_yaml=False,
        )
        mcp._max_reconnect_attempts = 3
        mcp._reconnect_base_delay_s = 0.01  # fast for tests
        mcp._reconnect_max_delay_s = 0.02

        pipeline = _make_pipeline_mock()
        pipeline.start.side_effect = [RuntimeError("fail"), RuntimeError("fail"), None]

        result = mcp._start_pipeline_with_retry("cam1", pipeline)
        assert result is True
        assert pipeline.start.call_count == 3

    def test_start_degrades_after_max_attempts(self):
        mcp = MultiCameraPipeline(
            camera_configs=[{"camera_id": "cam1", "src": 0}],
            load_config_from_yaml=False,
        )
        mcp._max_reconnect_attempts = 2
        mcp._reconnect_base_delay_s = 0.01

        pipeline = _make_pipeline_mock(start_ok=False)

        result = mcp._start_pipeline_with_retry("cam1", pipeline)
        assert result is False
        assert "cam1" in mcp._camera_degraded
        assert pipeline.start.call_count == 2


class TestAttemptReconnect:
    """Tests for _attempt_reconnect."""

    def test_reconnect_succeeds(self):
        mcp = MultiCameraPipeline(
            camera_configs=[{"camera_id": "cam1", "src": 0}],
            load_config_from_yaml=False,
        )
        mcp._running = True
        mcp._reconnect_base_delay_s = 0.01
        mcp._max_reconnect_attempts = 2

        pipeline = _make_pipeline_mock()
        # stop() ok, then rebuild succeeds
        pipeline._build_camera_source.return_value = MagicMock()

        result = mcp._attempt_reconnect("cam1", pipeline)
        assert result is True
        assert "cam1" not in mcp._camera_degraded
        # Error should be cleared
        assert "cam1" not in mcp._camera_errors

    def test_reconnect_fails_permanently(self):
        mcp = MultiCameraPipeline(
            camera_configs=[{"camera_id": "cam1", "src": 0}],
            load_config_from_yaml=False,
        )
        mcp._running = True
        mcp._max_reconnect_attempts = 2
        mcp._reconnect_base_delay_s = 0.01

        pipeline = _make_pipeline_mock()
        pipeline._build_camera_source.side_effect = RuntimeError("No camera")

        result = mcp._attempt_reconnect("cam1", pipeline)
        assert result is False
        assert "cam1" in mcp._camera_degraded


class TestDegradation:
    """Tests for graceful degradation."""

    def test_degrade_camera_tracking(self):
        mcp = MultiCameraPipeline(
            camera_configs=[
                {"camera_id": "cam1", "src": 0},
                {"camera_id": "cam2", "src": 1},
            ],
            load_config_from_yaml=False,
        )
        mcp._pipelines = {"cam1": MagicMock(), "cam2": MagicMock()}
        mcp._degrade_camera("cam1")
        assert mcp.get_degraded_cameras() == ["cam1"]
        assert "cam1" in mcp._camera_errors

    def test_manual_reconnect_clears_degraded(self):
        mcp = MultiCameraPipeline(
            camera_configs=[{"camera_id": "cam1", "src": 0}],
            load_config_from_yaml=False,
        )
        mcp._running = True
        pipeline = _make_pipeline_mock()
        mcp._pipelines = {"cam1": pipeline}
        mcp._camera_degraded.add("cam1")

        result = mcp.reconnect_camera("cam1")
        assert result["ok"] is True
        # degraded set cleared immediately
        assert "cam1" not in mcp._camera_degraded

    def test_reconnect_unknown_camera(self):
        mcp = MultiCameraPipeline(
            camera_configs=[{"camera_id": "cam1", "src": 0}],
            load_config_from_yaml=False,
        )
        mcp._pipelines = {"cam1": MagicMock()}
        result = mcp.reconnect_camera("cam_unknown")
        assert result["ok"] is False


class TestReconnectAPI:
    """Tests for the POST /api/multi/camera/{id}/reconnect endpoint."""

    def test_reconnect_endpoint_no_pipeline(self):
        from src.main import app, app_state
        from fastapi.testclient import TestClient

        client = TestClient(app)
        old = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = None
        try:
            resp = client.post("/api/multi/camera/cam1/reconnect")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is False
        finally:
            app_state["multi_pipeline"] = old

    def test_reconnect_endpoint_with_pipeline(self):
        from src.main import app, app_state
        from fastapi.testclient import TestClient

        client = TestClient(app)
        multi = MagicMock()
        multi.reconnect_camera.return_value = {"ok": True, "message": "Reconnect gestartet"}

        old = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = multi
        try:
            resp = client.post("/api/multi/camera/cam1/reconnect")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            multi.reconnect_camera.assert_called_once_with("cam1")
        finally:
            app_state["multi_pipeline"] = old

    def test_degraded_endpoint_no_pipeline(self):
        from src.main import app, app_state
        from fastapi.testclient import TestClient

        client = TestClient(app)
        old = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = None
        try:
            resp = client.get("/api/multi/degraded")
            assert resp.status_code == 200
            data = resp.json()
            assert data["degraded"] == []
        finally:
            app_state["multi_pipeline"] = old

    def test_degraded_endpoint_with_cameras(self):
        from src.main import app, app_state
        from fastapi.testclient import TestClient

        client = TestClient(app)
        multi = MagicMock()
        multi.get_degraded_cameras.return_value = ["cam2"]

        old = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = multi
        try:
            resp = client.get("/api/multi/degraded")
            data = resp.json()
            assert data["ok"] is True
            assert data["degraded"] == ["cam2"]
        finally:
            app_state["multi_pipeline"] = old
