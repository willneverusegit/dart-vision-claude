"""Tests for multi-camera hardening: readiness endpoint, config persistence, validation."""

import numpy as np
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from src.main import app, app_state


def _make_multi_pipeline(cam_ids, with_stereo=False, with_board_transforms=False):
    """Create a mock multi-pipeline with configurable readiness."""
    pipes = {}
    for cid in cam_ids:
        pipe = MagicMock()
        pipe.camera_calibration.get_intrinsics.return_value = None
        pipe.camera_calibration.get_config.return_value = {"lens_valid": False}
        pipe.board_calibration.is_valid.return_value = False
        pipe.fps_counter.fps.return_value = 30.0
        pipes[cid] = pipe

    multi = MagicMock()
    multi.get_pipelines.return_value = pipes
    multi.get_camera_errors.return_value = {}
    multi._board_transforms = {}
    multi._stereo_params = {}

    if with_board_transforms:
        for cid in cam_ids:
            multi._board_transforms[cid] = {
                "R_cb": np.eye(3), "t_cb": np.zeros(3)
            }

    if with_stereo:
        for cid in cam_ids:
            multi._stereo_params[cid] = MagicMock()

    return multi


class TestReadinessEndpoint:
    def test_readiness_no_multi(self):
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["ok"] is True
                assert data["running"] is False
        finally:
            app_state["multi_pipeline"] = saved

    def test_readiness_all_uncalibrated(self):
        saved = app_state.get("multi_pipeline")
        try:
            with TestClient(app) as client:
                app_state["multi_pipeline"] = _make_multi_pipeline(["cam_a", "cam_b"])
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["ok"] is True
                assert data["running"] is True
                assert data["all_ready"] is False
                assert data["triangulation_possible"] is False
                # Each camera should have issues
                for cam in data["cameras"]:
                    assert len(cam["issues"]) > 0
                    assert cam["ready"] is False
        finally:
            app_state["multi_pipeline"] = saved

    def test_readiness_fully_calibrated(self):
        saved = app_state.get("multi_pipeline")
        multi = _make_multi_pipeline(
            ["cam_a", "cam_b"],
            with_stereo=True,
            with_board_transforms=True,
        )
        # Make all cameras fully calibrated
        for pipe in multi.get_pipelines().values():
            pipe.camera_calibration.get_intrinsics.return_value = MagicMock()
            pipe.board_calibration.is_valid.return_value = True
        try:
            with TestClient(app) as client:
                app_state["multi_pipeline"] = multi
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["all_ready"] is True
                assert data["triangulation_possible"] is True
                for cam in data["cameras"]:
                    assert cam["ready"] is True
                    assert len(cam["issues"]) == 0
        finally:
            app_state["multi_pipeline"] = saved

    def test_readiness_partial_calibration(self):
        saved = app_state.get("multi_pipeline")
        multi = _make_multi_pipeline(["cam_a", "cam_b"])
        # Only cam_a has lens
        pipes = multi.get_pipelines()
        pipes["cam_a"].camera_calibration.get_intrinsics.return_value = MagicMock()
        pipes["cam_a"].board_calibration.is_valid.return_value = True
        try:
            with TestClient(app) as client:
                app_state["multi_pipeline"] = multi
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["all_ready"] is False
                cam_a = next(c for c in data["cameras"] if c["camera_id"] == "cam_a")
                cam_b = next(c for c in data["cameras"] if c["camera_id"] == "cam_b")
                assert cam_a["lens_calibrated"] is True
                assert cam_b["lens_calibrated"] is False
        finally:
            app_state["multi_pipeline"] = saved

    def test_readiness_stereo_pairs(self):
        saved = app_state.get("multi_pipeline")
        multi = _make_multi_pipeline(["cam_a", "cam_b"], with_stereo=True)
        try:
            with TestClient(app) as client:
                app_state["multi_pipeline"] = multi
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert len(data["stereo_pairs"]) == 1
                assert data["stereo_pairs"][0]["calibrated"] is True
        finally:
            app_state["multi_pipeline"] = saved


class TestLastConfigEndpoint:
    def test_get_last_config_empty(self, monkeypatch):
        monkeypatch.setattr("src.utils.config.load_multi_cam_config", lambda path=None: {})
        with TestClient(app) as client:
            resp = client.get("/api/multi/last-config")
            data = resp.json()
            assert data["ok"] is True
            assert data["cameras"] == []

    def test_get_last_config_with_data(self, monkeypatch):
        monkeypatch.setattr(
            "src.utils.config.load_multi_cam_config",
            lambda path=None: {"last_cameras": [
                {"camera_id": "cam_left", "src": 0},
                {"camera_id": "cam_right", "src": 2},
            ]},
        )
        with TestClient(app) as client:
            resp = client.get("/api/multi/last-config")
            data = resp.json()
            assert len(data["cameras"]) == 2


class TestMultiStartValidation:
    def test_duplicate_camera_id_rejected(self):
        with TestClient(app) as client:
            resp = client.post("/api/multi/start", json={
                "cameras": [
                    {"camera_id": "cam_a", "src": 0},
                    {"camera_id": "cam_a", "src": 1},
                ]
            })
            data = resp.json()
            assert data["ok"] is False
            assert "Doppelte" in data["error"]

    def test_missing_camera_id_rejected(self):
        with TestClient(app) as client:
            resp = client.post("/api/multi/start", json={
                "cameras": [{"src": 0}, {"camera_id": "b", "src": 1}]
            })
            data = resp.json()
            assert data["ok"] is False


class TestConfigPersistence:
    def test_save_and_load_last_cameras(self, tmp_path):
        from src.utils.config import save_last_cameras, get_last_cameras
        path = str(tmp_path / "test_multi.yaml")
        cameras = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 2},
        ]
        save_last_cameras(cameras, path=path)
        loaded = get_last_cameras(path=path)
        assert len(loaded) == 2
        assert loaded[0]["camera_id"] == "cam_left"
        assert loaded[1]["src"] == 2

    def test_get_last_cameras_empty(self, tmp_path):
        from src.utils.config import get_last_cameras
        path = str(tmp_path / "nonexistent.yaml")
        assert get_last_cameras(path=path) == []
