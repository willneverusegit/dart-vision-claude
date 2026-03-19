"""Additional route tests for coverage."""

import numpy as np
from fastapi.testclient import TestClient

from src.cv.stereo_calibration import LARGE_MARKER_CHARUCO_BOARD_SPEC, StereoResult
from src.main import app


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
        app_state["pipeline"] = DummyPipeline()
        try:
            with TestClient(app) as client:
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

        monkeypatch.setattr("src.cv.stereo_calibration.stereo_calibrate", fake_stereo_calibrate)
        monkeypatch.setattr(
            "src.cv.stereo_calibration.detect_charuco_corners",
            lambda gray: (np.array([[0.0, 0.0]]), np.array([0])),
        )
        monkeypatch.setattr("src.utils.config.save_stereo_pair", lambda *args, **kwargs: None)
        monkeypatch.setattr("src.web.routes._time.sleep", lambda _seconds: None)
        monkeypatch.setattr("src.cv.board_calibration.BoardCalibrationManager.has_valid_intrinsics", lambda self: True)
        monkeypatch.setattr(
            "src.cv.stereo_calibration.validate_stereo_prerequisites",
            lambda *args, **kwargs: {"ready": True, "errors": [], "warnings": []},
        )

        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = DummyMultiPipeline()
        try:
            with TestClient(app) as client:
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

    def test_board_geometry_endpoint(self):
        with TestClient(app) as client:
            resp = client.get("/api/board/geometry")
            assert resp.status_code == 200
            data = resp.json()
            assert "ok" in data
