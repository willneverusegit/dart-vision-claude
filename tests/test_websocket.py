"""WebSocket endpoint tests."""

from fastapi.testclient import TestClient
from src.main import app


class TestWebSocket:
    def test_ws_connect_and_receive_state(self):
        """WebSocket should send initial game_state on connect."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                data = ws.receive_json()
                assert data["type"] == "game_state"
                assert "phase" in data["data"]

    def test_ws_ping_pong(self):
        """WebSocket should respond to ping command."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                ws.receive_json()  # Initial state
                ws.send_json({"command": "ping"})
                data = ws.receive_json()
                assert data["type"] == "pong"

    def test_ws_get_state_command(self):
        """WebSocket get_state command returns game state."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                ws.receive_json()  # Initial state
                ws.send_json({"command": "get_state"})
                data = ws.receive_json()
                assert data["type"] == "game_state"
