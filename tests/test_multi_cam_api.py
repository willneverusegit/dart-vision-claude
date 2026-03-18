"""Tests for multi-cam error reporting and telemetry API endpoints."""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.main import app, app_state


class TestMultiCamErrorsEndpoint:
    """GET /api/multi-cam/errors"""

    def test_no_pipeline_returns_inactive(self):
        saved = app_state.pop("multi_pipeline", None)
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/errors")
                assert resp.status_code == 200
                data = resp.json()
                assert data["errors"] == {}
                assert "nicht aktiv" in data["message"]
        finally:
            if saved is not None:
                app_state["multi_pipeline"] = saved

    def test_active_pipeline_returns_errors(self):
        mock_multi = MagicMock()
        mock_multi.get_camera_errors.return_value = {
            "cam0": ["timeout"],
            "cam1": [],
        }
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = mock_multi
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/errors")
                assert resp.status_code == 200
                data = resp.json()
                assert data["errors"]["cam0"] == ["timeout"]
                assert data["errors"]["cam1"] == []
        finally:
            if saved is not None:
                app_state["multi_pipeline"] = saved
            else:
                app_state.pop("multi_pipeline", None)


class TestMultiCamTelemetryEndpoint:
    """GET /api/multi-cam/telemetry"""

    def test_no_pipeline_returns_inactive(self):
        saved = app_state.pop("multi_pipeline", None)
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                assert resp.status_code == 200
                data = resp.json()
                assert data["active"] is False
                assert "nicht aktiv" in data["message"]
        finally:
            if saved is not None:
                app_state["multi_pipeline"] = saved

    def test_active_pipeline_returns_telemetry(self):
        mock_multi = MagicMock()
        mock_multi.get_triangulation_telemetry.return_value = {
            "total_attempts": 10,
            "successful": 8,
        }
        mock_multi.get_fusion_config.return_value = {
            "method": "weighted_average",
        }
        mock_multi.get_governor_stats.return_value = {
            "cam0": {"fps": 30},
        }
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = mock_multi
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                assert resp.status_code == 200
                data = resp.json()
                assert data["active"] is True
                assert data["triangulation"]["total_attempts"] == 10
                assert data["fusion_config"]["method"] == "weighted_average"
                assert "governors" in data
        finally:
            if saved is not None:
                app_state["multi_pipeline"] = saved
            else:
                app_state.pop("multi_pipeline", None)
