"""Integration tests for web endpoints."""

import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestWebEndpoints:
    def test_index_page(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Dart-Vision" in response.text

    def test_get_state_idle(self, client):
        response = client.get("/api/state")
        assert response.status_code == 200
        data = response.json()
        assert "phase" in data

    def test_new_game_x01(self, client):
        response = client.post("/api/game/new", json={
            "mode": "x01", "players": ["A", "B"], "starting_score": 501
        })
        data = response.json()
        assert data["phase"] == "playing"
        assert data["scores"]["A"] == 501
        assert data["scores"]["B"] == 501

    def test_new_game_cricket(self, client):
        response = client.post("/api/game/new", json={
            "mode": "cricket", "players": ["X"]
        })
        data = response.json()
        assert data["mode"] == "cricket"
        marks = data["players"][0]["cricket_marks"]
        # JSON keys are strings
        assert "20" in marks or 20 in marks

    def test_new_game_free(self, client):
        response = client.post("/api/game/new", json={
            "mode": "free", "players": ["Solo"]
        })
        data = response.json()
        assert data["mode"] == "free"
        assert data["scores"]["Solo"] == 0

    def test_undo_endpoint(self, client):
        client.post("/api/game/new", json={
            "mode": "x01", "players": ["A"], "starting_score": 501
        })
        response = client.post("/api/game/undo")
        assert response.status_code == 200

    def test_next_player(self, client):
        client.post("/api/game/new", json={
            "mode": "x01", "players": ["A", "B"], "starting_score": 501
        })
        response = client.post("/api/game/next-player")
        data = response.json()
        assert data["current_player"] == "B"

    def test_remove_darts(self, client):
        client.post("/api/game/new", json={
            "mode": "x01", "players": ["A"], "starting_score": 501
        })
        response = client.post("/api/game/remove-darts")
        assert response.status_code == 200

    def test_stats_endpoint(self, client):
        response = client.get("/api/stats")
        data = response.json()
        assert "fps" in data
        assert "connections" in data

    def test_calibration_frame_no_camera(self, client):
        response = client.get("/api/calibration/frame")
        data = response.json()
        assert "ok" in data

    def test_static_css(self, client):
        response = client.get("/static/css/style.css")
        assert response.status_code == 200
        assert "bg-primary" in response.text

    def test_static_js(self, client):
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "DartApp" in response.text
