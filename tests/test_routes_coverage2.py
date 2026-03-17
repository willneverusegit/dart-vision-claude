"""Additional route tests to increase routes.py coverage from 34% to 60%+."""

import threading
import numpy as np
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app, app_state


def _make_dummy_pipeline():
    """Create a mock pipeline with common attributes."""
    pipe = MagicMock()
    pipe.board_calibration.is_valid.return_value = True
    pipe.camera_calibration.get_config.return_value = {"lens_valid": False}
    pipe.camera_calibration.get_intrinsics.return_value = None
    pipe.fps_counter.fps.return_value = 30.0
    pipe.show_overlay_motion = False
    pipe.show_overlay_markers = False
    pipe.get_roi_preview.return_value = np.zeros((400, 400, 3), dtype=np.uint8)
    pipe.get_field_overlay.return_value = np.zeros((400, 400, 3), dtype=np.uint8)
    pipe.get_latest_raw_frame.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
    pipe._last_motion_mask = None
    pipe.get_geometry_info.return_value = {
        "center_px": [200, 200],
        "radii_px": [10, 19, 106, 116, 188, 200],
        "rotation_deg": 0,
        "lens_valid": False,
        "lens_method": None,
    }
    return pipe


class TestGameEndpoints:
    def test_end_game(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "x01", "players": ["A"]})
            resp = client.post("/api/game/end")
            assert resp.status_code == 200

    def test_get_state(self):
        with TestClient(app) as client:
            resp = client.get("/api/state")
            assert resp.status_code == 200
            assert "phase" in resp.json()

    def test_manual_score(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
            })
            assert resp.status_code == 200


class TestHitCandidateEndpoints:
    def test_get_pending_hits_empty(self):
        with TestClient(app) as client:
            resp = client.get("/api/hits/pending")
            assert resp.status_code == 200
            assert resp.json()["hits"] == [] or resp.json()["ok"]

    def test_confirm_missing_candidate(self):
        with TestClient(app) as client:
            resp = client.post("/api/hits/nonexistent/confirm")
            data = resp.json()
            assert data["ok"] is False

    def test_reject_missing_candidate(self):
        with TestClient(app) as client:
            resp = client.post("/api/hits/nonexistent/reject")
            data = resp.json()
            assert data["ok"] is False

    def test_confirm_existing_candidate(self):
        with TestClient(app) as client:
            # Start a game first
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            # Insert a candidate directly
            lock = app_state.get("pending_hits_lock")
            if lock:
                with lock:
                    app_state["pending_hits"]["test123"] = {
                        "candidate_id": "test123",
                        "score": 20, "sector": 20, "multiplier": 1, "ring": "single",
                        "roi_x": 0, "roi_y": 0, "quality": 80, "timestamp": 0,
                    }
            resp = client.post("/api/hits/test123/confirm")
            data = resp.json()
            assert data["ok"] is True

    def test_reject_existing_candidate(self):
        with TestClient(app) as client:
            lock = app_state.get("pending_hits_lock")
            if lock:
                with lock:
                    app_state["pending_hits"]["test456"] = {
                        "candidate_id": "test456",
                        "score": 60, "sector": 20, "multiplier": 3, "ring": "triple",
                        "roi_x": 0, "roi_y": 0, "quality": 90, "timestamp": 0,
                    }
            resp = client.post("/api/hits/test456/reject")
            assert resp.json()["ok"] is True

    def test_correct_hit(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            lock = app_state.get("pending_hits_lock")
            if lock:
                with lock:
                    app_state["pending_hits"]["test789"] = {
                        "candidate_id": "test789",
                        "score": 20, "sector": 20, "multiplier": 1, "ring": "single",
                        "roi_x": 0, "roi_y": 0, "quality": 50, "timestamp": 0,
                    }
            resp = client.post("/api/hits/test789/correct", json={
                "score": 60, "sector": 20, "multiplier": 3, "ring": "triple"
            })
            assert resp.json()["ok"] is True

    def test_correct_hit_missing(self):
        with TestClient(app) as client:
            resp = client.post("/api/hits/missing/correct", json={"score": 10})
            assert resp.json()["ok"] is False


class TestOverlayEndpoints:
    def test_set_overlays(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = _make_dummy_pipeline()
        try:
            with TestClient(app) as client:
                resp = client.post("/api/overlays", json={"motion": True, "markers": True})
                assert resp.status_code == 200
                assert resp.json()["ok"] is True
        finally:
            app_state["pipeline"] = saved

    def test_get_overlays(self):
        with TestClient(app) as client:
            resp = client.get("/api/overlays")
            assert resp.status_code == 200

    def test_set_overlays_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/overlays", json={"motion": True})
                assert resp.status_code == 200
        finally:
            app_state["pipeline"] = saved


class TestCalibrationEndpoints:
    def test_get_calibration_frame_no_frame(self):
        saved = app_state.get("latest_frame")
        app_state["latest_frame"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/frame")
                assert resp.status_code == 200
                assert resp.json()["ok"] is False
        finally:
            app_state["latest_frame"] = saved

    def test_get_calibration_frame_with_frame(self):
        app_state["latest_frame"] = np.zeros((480, 640, 3), dtype=np.uint8)
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/frame")
                data = resp.json()
                assert data["ok"] is True
                assert "image" in data
        finally:
            app_state["latest_frame"] = None

    def test_roi_preview_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/roi-preview")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_roi_preview_with_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = _make_dummy_pipeline()
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/roi-preview")
                assert resp.json()["ok"] is True
        finally:
            app_state["pipeline"] = saved

    def test_field_overlay_with_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = _make_dummy_pipeline()
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/overlay")
                assert resp.json()["ok"] is True
        finally:
            app_state["pipeline"] = saved

    def test_field_overlay_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/overlay")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_verify_rings_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/verify-rings")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_optical_center_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_optical_center_manual_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={"x": 200, "y": 200})
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_optical_center_manual_missing_xy(self):
        saved = app_state.get("pipeline")
        pipe = _make_dummy_pipeline()
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={})
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_optical_center_manual_invalid_xy(self):
        saved = app_state.get("pipeline")
        pipe = _make_dummy_pipeline()
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={"x": "abc", "y": "def"})
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_optical_center_manual_success(self):
        saved = app_state.get("pipeline")
        pipe = _make_dummy_pipeline()
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={"x": 200.5, "y": 199.3})
                assert resp.json()["ok"] is True
        finally:
            app_state["pipeline"] = saved

    def test_calibration_info_with_pipeline(self):
        saved = app_state.get("pipeline")
        pipe = _make_dummy_pipeline()
        pipe.board_calibration.get_config.return_value = {
            "valid": True, "method": "aruco", "mm_per_px": 0.85,
            "radii_px": [10, 19, 106, 116, 188, 200],
            "center_px": [200, 200], "schema_version": 2,
        }
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/info")
                data = resp.json()
                assert data["ok"] is True
                assert data["board_valid"] is True
        finally:
            app_state["pipeline"] = saved

    def test_calibration_info_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/info")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_aruco_calibration_no_frame(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        app_state["latest_frame"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/aruco")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_board_aruco_no_frame(self):
        saved = app_state.get("pipeline")
        pipe = _make_dummy_pipeline()
        pipe.get_latest_raw_frame.return_value = None
        app_state["pipeline"] = pipe
        app_state["latest_frame"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/board/aruco")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_board_manual_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/board/manual",
                                   json={"points": [[0,0],[1,0],[1,1],[0,1]]})
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved


class TestCaptureConfigEndpoints:
    def test_get_capture_config_no_camera(self):
        saved_pipe = app_state.get("pipeline")
        saved_multi = app_state.get("multi_pipeline")
        app_state["pipeline"] = None
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/capture/config")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved_pipe
            app_state["multi_pipeline"] = saved_multi

    def test_set_capture_config_no_params(self):
        with TestClient(app) as client:
            resp = client.post("/api/capture/config", json={"camera_id": "default"})
            assert resp.json()["ok"] is False

    def test_set_capture_config_camera_not_found(self):
        saved_pipe = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/capture/config",
                                   json={"camera_id": "default", "width": 640, "height": 480, "fps": 30})
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved_pipe


class TestStatsEndpoint:
    def test_get_stats(self):
        with TestClient(app) as client:
            resp = client.get("/api/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert "fps" in data
            assert "pipeline_running" in data

    def test_get_stats_with_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = _make_dummy_pipeline()
        try:
            with TestClient(app) as client:
                resp = client.get("/api/stats")
                data = resp.json()
                assert data["fps"] == 30.0
        finally:
            app_state["pipeline"] = saved


class TestMultiCamEndpoints:
    def test_multi_status_not_running(self):
        with TestClient(app) as client:
            resp = client.get("/api/multi/status")
            data = resp.json()
            assert data["ok"] is True
            assert data["running"] is False

    def test_multi_stop_not_running(self):
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/multi/stop")
                assert resp.json()["ok"] is False
        finally:
            app_state["multi_pipeline"] = saved

    def test_multi_start_too_few_cameras(self):
        with TestClient(app) as client:
            resp = client.post("/api/multi/start", json={"cameras": [{"camera_id": "only_one"}]})
            assert resp.json()["ok"] is False

    def test_multi_start_no_camera_id(self):
        with TestClient(app) as client:
            resp = client.post("/api/multi/start", json={"cameras": [{"src": 0}, {"src": 1}]})
            assert resp.json()["ok"] is False

    def test_multi_start_already_running(self):
        saved = app_state.get("multi_pipeline_running")
        app_state["multi_pipeline_running"] = True
        try:
            with TestClient(app) as client:
                resp = client.post("/api/multi/start", json={
                    "cameras": [{"camera_id": "a", "src": 0}, {"camera_id": "b", "src": 1}]
                })
                assert resp.json()["ok"] is False
        finally:
            app_state["multi_pipeline_running"] = saved

    def test_multi_status_with_pipeline(self):
        saved = app_state.get("multi_pipeline")

        mock_pipe = MagicMock()
        mock_pipe.fps_counter.fps.return_value = 25.0
        mock_pipe.board_calibration.is_valid.return_value = False
        mock_pipe.camera_calibration.get_config.return_value = {"lens_valid": True}

        mock_multi = MagicMock()
        mock_multi.get_pipelines.return_value = {"cam_a": mock_pipe}
        mock_multi.get_camera_errors.return_value = {}

        app_state["multi_pipeline"] = mock_multi
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/status")
                data = resp.json()
                assert data["ok"] is True
                assert len(data["cameras"]) == 1
                assert data["cameras"][0]["fps"] == 25.0
        finally:
            app_state["multi_pipeline"] = saved


class TestSinglePipelineEndpoints:
    def test_single_stop_not_running(self):
        saved = app_state.get("pipeline_running")
        app_state["pipeline_running"] = False
        try:
            with TestClient(app) as client:
                resp = client.post("/api/single/stop")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline_running"] = saved


class TestStereoEndpoints:
    def test_stereo_no_camera_b(self):
        with TestClient(app) as client:
            resp = client.post("/api/calibration/stereo", json={"camera_a": "a"})
            assert resp.json()["ok"] is False

    def test_stereo_no_multi_pipeline(self):
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo",
                                   json={"camera_a": "a", "camera_b": "b"})
                assert resp.json()["ok"] is False
        finally:
            app_state["multi_pipeline"] = saved

    def test_stereo_reload_not_running(self):
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                assert resp.json()["ok"] is False
        finally:
            app_state["multi_pipeline"] = saved


class TestBoardGeometry:
    def test_board_geometry_no_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/board/geometry")
                assert resp.json()["ok"] is False
        finally:
            app_state["pipeline"] = saved

    def test_board_geometry_with_pipeline(self):
        saved = app_state.get("pipeline")
        app_state["pipeline"] = _make_dummy_pipeline()
        try:
            with TestClient(app) as client:
                resp = client.get("/api/board/geometry")
                data = resp.json()
                assert data["ok"] is True
        finally:
            app_state["pipeline"] = saved


class TestBoardPoseEndpoint:
    def test_board_pose_no_camera_id(self):
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = MagicMock()
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/board-pose", json={})
                assert resp.json()["ok"] is False
        finally:
            app_state["multi_pipeline"] = saved

    def test_board_pose_no_multi(self):
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/board-pose",
                                   json={"camera_id": "cam_a"})
                assert resp.json()["ok"] is False
        finally:
            app_state["multi_pipeline"] = saved
