"""Additional route tests for coverage."""

import threading
import numpy as np
from fastapi.testclient import TestClient

from src.cv.stereo_calibration import LARGE_MARKER_CHARUCO_BOARD_SPEC, StereoResult
from src.main import app, app_state


class TestRoutesCoverage:
    def test_new_game_default_players(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={"mode": "x01"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["players"]) == 1
            assert data["players"][0]["name"] == "Player 1"

    def test_new_game_multiple_players(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={
                "mode": "x01",
                "players": ["Alice", "Bob", "Charlie"],
                "starting_score": 301
            })
            data = resp.json()
            assert len(data["players"]) == 3
            # Verify players got 301 starting score
            assert data["players"][0]["score"] == 301

    def test_undo_in_idle_state(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/undo")
            assert resp.status_code == 200

    def test_next_player_in_idle(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/next-player")
            assert resp.status_code == 200

    def test_remove_darts_resets(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "x01", "players": ["A", "B"]})
            resp = client.post("/api/game/remove-darts")
            assert resp.status_code == 200

    def test_calibration_manual_no_pipeline(self):
        from src.main import app_state
        saved = app_state.pop("pipeline", None)
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/manual", json={"points": [[0,0],[1,0],[1,1],[0,1]]})
                data = resp.json()
                assert data.get("ok") is False or "error" in data
        finally:
            if saved is not None:
                app_state["pipeline"] = saved

    def test_lens_info_endpoint(self):
        with TestClient(app) as client:
            resp = client.get("/api/calibration/lens/info")
            assert resp.status_code == 200
            data = resp.json()
            assert "ok" in data

    def test_lens_info_endpoint_includes_charuco_board(self):
        from src.main import app_state

        class DummyCameraCalibration:
            def get_config(self):
                return {
                    "lens_valid": True,
                    "lens_method": "charuco",
                    "lens_image_size": [640, 480],
                    "lens_reprojection_error": 0.12,
                }

            def get_charuco_board_spec(self):
                return LARGE_MARKER_CHARUCO_BOARD_SPEC

        class DummyPipeline:
            camera_calibration = DummyCameraCalibration()

        saved = app_state.get("pipeline")
        try:
            with TestClient(app) as client:
                app_state["pipeline"] = DummyPipeline()
                resp = client.get("/api/calibration/lens/info")
                data = resp.json()
                assert data["charuco_board"]["preset"] == "40x28"
                assert data["charuco_board"]["marker_length_mm"] == 28.0
        finally:
            if saved is None:
                app_state.pop("pipeline", None)
            else:
                app_state["pipeline"] = saved

    def test_stereo_calibration_endpoint_accepts_charuco_override(self, monkeypatch):
        from src.main import app_state

        captured = {}

        class DummyIntrinsics:
            camera_matrix = np.eye(3, dtype=np.float64)
            dist_coeffs = np.zeros((5, 1), dtype=np.float64)

        class DummyCameraCalibration:
            def get_intrinsics(self):
                return DummyIntrinsics()

            def get_charuco_board_spec(self, **kwargs):
                if kwargs:
                    return LARGE_MARKER_CHARUCO_BOARD_SPEC
                return LARGE_MARKER_CHARUCO_BOARD_SPEC

        class DummyPipeline:
            camera_calibration = DummyCameraCalibration()

            def get_latest_raw_frame(self):
                return np.zeros((32, 32, 3), dtype=np.uint8)

        class DummyMultiPipeline:
            def __init__(self):
                self._pipelines = {
                    "cam_a": DummyPipeline(),
                    "cam_b": DummyPipeline(),
                }
                self.reloaded = False

            def get_pipelines(self):
                return self._pipelines

            def reload_stereo_params(self):
                self.reloaded = True

        def fake_stereo_calibrate(
            frames_a,
            frames_b,
            camera_matrix_1,
            dist_coeffs_1,
            camera_matrix_2,
            dist_coeffs_2,
            image_size=None,
            board_spec=None,
        ):
            captured["pairs"] = len(frames_a)
            captured["board_spec"] = board_spec
            return StereoResult(
                ok=True,
                R=np.eye(3, dtype=np.float64),
                T=np.zeros((3, 1), dtype=np.float64),
                reprojection_error=0.25,
                error_message=None,
            )

        async def fake_sleep(_seconds):
            return None

        monkeypatch.setattr("src.cv.stereo_calibration.stereo_calibrate", fake_stereo_calibrate)
        monkeypatch.setattr("src.utils.config.save_stereo_pair", lambda *args, **kwargs: None)
        monkeypatch.setattr("src.web.routes.asyncio.sleep", fake_sleep)

        saved = app_state.get("multi_pipeline")
        try:
            with TestClient(app) as client:
                app_state["multi_pipeline"] = DummyMultiPipeline()
                resp = client.post(
                    "/api/calibration/stereo",
                    json={
                        "camera_a": "cam_a",
                        "camera_b": "cam_b",
                        "num_pairs": 5,
                        "capture_delay": 0,
                        "preset": "40x28",
                    },
                )
                data = resp.json()
                assert data["ok"] is True
                assert data["charuco_board"]["preset"] == "40x28"
                assert captured["pairs"] == 5
                assert captured["board_spec"] == LARGE_MARKER_CHARUCO_BOARD_SPEC
        finally:
            if saved is None:
                app_state.pop("multi_pipeline", None)
            else:
                app_state["multi_pipeline"] = saved

    def test_single_start_uses_async_pause(self, monkeypatch):
        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)

        def fake_stop_pipeline_thread(state, kind, timeout=5.0):
            if kind == "single":
                state["pipeline_running"] = False
                state["pipeline"] = None
            else:
                state["multi_pipeline_running"] = False
                state["multi_pipeline"] = None

        def fake_start_single_pipeline(state, camera_src=0):
            state["pipeline_running"] = True
            state["pipeline"] = object()

        saved = {
            "pipeline": app_state.get("pipeline"),
            "pipeline_running": app_state.get("pipeline_running"),
            "multi_pipeline": app_state.get("multi_pipeline"),
            "multi_pipeline_running": app_state.get("multi_pipeline_running"),
            "pipeline_lock": app_state.get("pipeline_lock"),
            "pipeline_stop_event": app_state.get("pipeline_stop_event"),
            "pipeline_thread": app_state.get("pipeline_thread"),
            "multi_pipeline_stop_event": app_state.get("multi_pipeline_stop_event"),
            "multi_pipeline_thread": app_state.get("multi_pipeline_thread"),
        }

        monkeypatch.setattr("src.web.routes.asyncio.sleep", fake_sleep)
        monkeypatch.setattr("src.main.stop_pipeline_thread", fake_stop_pipeline_thread)
        monkeypatch.setattr("src.main.start_single_pipeline", fake_start_single_pipeline)

        app_state["pipeline"] = object()
        app_state["pipeline_running"] = True
        app_state["multi_pipeline"] = None
        app_state["multi_pipeline_running"] = False
        app_state["pipeline_lock"] = threading.Lock()
        app_state["pipeline_stop_event"] = None
        app_state["pipeline_thread"] = None
        app_state["multi_pipeline_stop_event"] = None
        app_state["multi_pipeline_thread"] = None

        try:
            with TestClient(app) as client:
                resp = client.post("/api/single/start", json={"src": 2})
                data = resp.json()
                assert data["ok"] is True
                assert data["src"] == 2
                assert sleep_calls == [0.5]
        finally:
            for key, value in saved.items():
                app_state[key] = value

    def test_multi_start_uses_async_pause(self, monkeypatch):
        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)

        def fake_stop_pipeline_thread(state, kind, timeout=5.0):
            if kind == "single":
                state["pipeline_running"] = False
                state["pipeline"] = None

        saved = {
            "pipeline": app_state.get("pipeline"),
            "pipeline_running": app_state.get("pipeline_running"),
            "multi_pipeline": app_state.get("multi_pipeline"),
            "multi_pipeline_running": app_state.get("multi_pipeline_running"),
            "pipeline_lock": app_state.get("pipeline_lock"),
            "pipeline_stop_event": app_state.get("pipeline_stop_event"),
            "pipeline_thread": app_state.get("pipeline_thread"),
            "multi_pipeline_stop_event": app_state.get("multi_pipeline_stop_event"),
            "multi_pipeline_thread": app_state.get("multi_pipeline_thread"),
        }

        def fake_run_multi_pipeline(state, cameras, stop_event):
            state["multi_pipeline_running"] = True
            state["multi_pipeline"] = object()

        monkeypatch.setattr("src.web.routes.asyncio.sleep", fake_sleep)
        monkeypatch.setattr("src.main.stop_pipeline_thread", fake_stop_pipeline_thread)
        monkeypatch.setattr("src.main._run_multi_pipeline", fake_run_multi_pipeline)
        monkeypatch.setattr("src.utils.config.save_last_cameras", lambda *args, **kwargs: None)

        app_state["pipeline"] = object()
        app_state["pipeline_running"] = True
        app_state["multi_pipeline"] = None
        app_state["multi_pipeline_running"] = False
        app_state["pipeline_lock"] = threading.Lock()
        app_state["pipeline_stop_event"] = None
        app_state["pipeline_thread"] = None
        app_state["multi_pipeline_stop_event"] = None
        app_state["multi_pipeline_thread"] = None

        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/api/multi/start",
                    json={
                        "cameras": [
                            {"camera_id": "left", "src": 0},
                            {"camera_id": "right", "src": 1},
                        ]
                    },
                )
                data = resp.json()
                assert data["ok"] is True
                assert data["running"] is True
                assert data["cameras"] == ["left", "right"]
                assert sleep_calls == [0.5]
        finally:
            for key, value in saved.items():
                app_state[key] = value

    def test_multi_stop_restart_single_uses_async_pause(self, monkeypatch):
        sleep_calls = []

        async def fake_sleep(seconds):
            sleep_calls.append(seconds)

        def fake_stop_pipeline_thread(state, kind, timeout=5.0):
            if kind == "multi":
                state["multi_pipeline"] = None
                state["multi_pipeline_running"] = False

        def fake_start_single_pipeline(state, camera_src=0):
            state["pipeline_running"] = True
            state["pipeline"] = object()

        saved = {
            "pipeline": app_state.get("pipeline"),
            "pipeline_running": app_state.get("pipeline_running"),
            "multi_pipeline": app_state.get("multi_pipeline"),
            "multi_pipeline_running": app_state.get("multi_pipeline_running"),
            "pipeline_lock": app_state.get("pipeline_lock"),
            "multi_latest_frames": app_state.get("multi_latest_frames"),
            "pipeline_stop_event": app_state.get("pipeline_stop_event"),
            "pipeline_thread": app_state.get("pipeline_thread"),
            "multi_pipeline_stop_event": app_state.get("multi_pipeline_stop_event"),
            "multi_pipeline_thread": app_state.get("multi_pipeline_thread"),
        }

        monkeypatch.setattr("src.web.routes.asyncio.sleep", fake_sleep)
        monkeypatch.setattr("src.main.stop_pipeline_thread", fake_stop_pipeline_thread)
        monkeypatch.setattr("src.main.start_single_pipeline", fake_start_single_pipeline)

        try:
            with TestClient(app) as client:
                app_state["pipeline"] = None
                app_state["pipeline_running"] = False
                app_state["multi_pipeline"] = object()
                app_state["multi_pipeline_running"] = True
                app_state["pipeline_lock"] = threading.Lock()
                app_state["multi_latest_frames"] = {"left": object()}
                app_state["pipeline_stop_event"] = None
                app_state["pipeline_thread"] = None
                app_state["multi_pipeline_stop_event"] = None
                app_state["multi_pipeline_thread"] = None
                resp = client.post("/api/multi/stop", json={"restart_single": True, "single_src": 3})
                data = resp.json()
                assert data["ok"] is True
                assert data["single_restarted"] is True
                assert data["single_src"] == 3
                assert sleep_calls == [0.5]
        finally:
            for key, value in saved.items():
                app_state[key] = value

    def test_board_geometry_endpoint(self):
        with TestClient(app) as client:
            resp = client.get("/api/board/geometry")
            assert resp.status_code == 200
            data = resp.json()
            assert "ok" in data
