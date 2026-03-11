"""Additional route tests for coverage."""

from fastapi.testclient import TestClient
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
