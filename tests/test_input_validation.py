"""Tests for input validation in web routes and game engine."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from starlette.testclient import TestClient
from fastapi import FastAPI

from src.game.engine import GameEngine
from src.web.routes import setup_routes


# --- Fixtures ---

@pytest.fixture
def engine():
    return GameEngine()


@pytest.fixture
def app_state():
    engine = GameEngine()
    return {
        "game_engine": engine,
        "event_manager": None,
        "pipeline": None,
        "pending_hits": {},
        "pending_hits_lock": __import__("threading").Lock(),
    }


@pytest.fixture
def client(app_state):
    # setup_routes now creates a fresh router each call (P67), no module-level cleanup needed
    router = setup_routes(app_state)
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app), app_state


# --- Game Engine: new_game validation ---

class TestEngineNewGameValidation:

    def test_valid_new_game(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=301)
        assert engine.state.starting_score == 301

    def test_invalid_starting_score_zero(self, engine):
        with pytest.raises(ValueError, match="starting_score"):
            engine.new_game(starting_score=0)

    def test_invalid_starting_score_negative(self, engine):
        with pytest.raises(ValueError, match="starting_score"):
            engine.new_game(starting_score=-1)

    def test_invalid_starting_score_too_high(self, engine):
        with pytest.raises(ValueError, match="starting_score"):
            engine.new_game(starting_score=10001)

    def test_invalid_starting_score_string(self, engine):
        with pytest.raises(ValueError, match="starting_score"):
            engine.new_game(starting_score="abc")

    def test_empty_players_list(self, engine):
        with pytest.raises(ValueError, match="players"):
            engine.new_game(players=[])

    def test_invalid_mode(self, engine):
        with pytest.raises(ValueError):
            engine.new_game(mode="invalid_mode")

    def test_boundary_starting_score_1(self, engine):
        engine.new_game(starting_score=1)
        assert engine.state.starting_score == 1

    def test_boundary_starting_score_10000(self, engine):
        engine.new_game(starting_score=10000)
        assert engine.state.starting_score == 10000


# --- Game Engine: register_throw validation ---

class TestEngineRegisterThrowValidation:

    def test_missing_keys_returns_state(self, engine):
        engine.new_game()
        result = engine.register_throw({"score": 20})  # missing sector, multiplier, ring
        # Should return state without crashing
        assert "phase" in result

    def test_empty_dict_returns_state(self, engine):
        engine.new_game()
        result = engine.register_throw({})
        assert "phase" in result

    def test_valid_throw(self, engine):
        engine.new_game()
        result = engine.register_throw({
            "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
        })
        assert result["darts_thrown"] == 1

    def test_fourth_dart_auto_completes_turn(self, engine):
        engine.new_game(players=["A", "B"])
        for _ in range(3):
            engine.register_throw({
                "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
            })
        # Turn should have been completed, now 4th dart starts new turn
        result = engine.register_throw({
            "score": 19, "sector": 19, "multiplier": 1, "ring": "single"
        })
        # After 3 darts the turn completes and player switches to B,
        # then 4th dart goes to B
        assert result["darts_thrown"] == 1


# --- Web Routes: game/new validation ---

class TestRouteNewGameValidation:

    def test_valid_new_game(self, client):
        c, state = client
        resp = c.post("/api/game/new", json={
            "mode": "x01", "players": ["Alice"], "starting_score": 301
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "x01"

    def test_invalid_mode_defaults_to_x01(self, client):
        c, state = client
        resp = c.post("/api/game/new", json={"mode": "invalid"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "x01"

    def test_invalid_players_defaults(self, client):
        c, state = client
        resp = c.post("/api/game/new", json={"players": "not_a_list"})
        assert resp.status_code == 200
        assert len(resp.json()["players"]) == 1

    def test_empty_players_defaults(self, client):
        c, state = client
        resp = c.post("/api/game/new", json={"players": []})
        assert resp.status_code == 200
        assert len(resp.json()["players"]) == 1

    def test_invalid_starting_score_defaults(self, client):
        c, state = client
        resp = c.post("/api/game/new", json={"starting_score": -5})
        assert resp.status_code == 200
        # Should default to 501

    def test_starting_score_too_high_defaults(self, client):
        c, state = client
        resp = c.post("/api/game/new", json={"starting_score": 99999})
        assert resp.status_code == 200


# --- Web Routes: manual-score validation ---

class TestRouteManualScoreValidation:

    def test_valid_manual_score(self, client):
        c, state = client
        # Start a game first
        c.post("/api/game/new", json={})
        resp = c.post("/api/game/manual-score", json={
            "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
        })
        assert resp.status_code == 200
        assert "error" not in resp.json()

    def test_invalid_score_too_high(self, client):
        c, state = client
        c.post("/api/game/new", json={})
        resp = c.post("/api/game/manual-score", json={
            "score": 181, "sector": 20, "multiplier": 1, "ring": "single"
        })
        assert "error" in resp.json()

    def test_invalid_sector(self, client):
        c, state = client
        c.post("/api/game/new", json={})
        resp = c.post("/api/game/manual-score", json={
            "score": 20, "sector": 99, "multiplier": 1, "ring": "single"
        })
        assert "error" in resp.json()

    def test_invalid_multiplier(self, client):
        c, state = client
        c.post("/api/game/new", json={})
        resp = c.post("/api/game/manual-score", json={
            "score": 20, "sector": 20, "multiplier": 5, "ring": "single"
        })
        assert "error" in resp.json()

    def test_invalid_ring(self, client):
        c, state = client
        c.post("/api/game/new", json={})
        resp = c.post("/api/game/manual-score", json={
            "score": 20, "sector": 20, "multiplier": 1, "ring": "bullseye"
        })
        assert "error" in resp.json()


# --- Web Routes: correct_hit validation ---

class TestRouteCorrectHitValidation:

    def test_correct_hit_invalid_score(self, client):
        c, state = client
        c.post("/api/game/new", json={})
        # Add a pending hit
        state["pending_hits"]["test1"] = {
            "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
        }
        resp = c.post("/api/hits/test1/correct", json={"score": 999})
        data = resp.json()
        assert data.get("ok") is False
        assert "error" in data

    def test_correct_hit_invalid_ring(self, client):
        c, state = client
        c.post("/api/game/new", json={})
        state["pending_hits"]["test2"] = {
            "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
        }
        resp = c.post("/api/hits/test2/correct", json={"ring": "invalid"})
        data = resp.json()
        assert data.get("ok") is False

    def test_correct_hit_valid(self, client):
        c, state = client
        c.post("/api/game/new", json={})
        state["pending_hits"]["test3"] = {
            "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
        }
        resp = c.post("/api/hits/test3/correct", json={"score": 40, "multiplier": 2, "ring": "double"})
        data = resp.json()
        assert data.get("ok") is True, f"Response: {data}"

    def test_correct_hit_not_found(self, client):
        c, state = client
        resp = c.post("/api/hits/nonexistent/correct", json={"score": 20})
        data = resp.json()
        assert data.get("ok") is False
