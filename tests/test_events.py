"""Tests for EventManager."""

import pytest
from unittest.mock import AsyncMock
from src.web.events import EventManager


@pytest.fixture
def event_manager():
    return EventManager()


class TestEventManager:
    def test_initial_connection_count(self, event_manager):
        assert event_manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_connect_increments_count(self, event_manager):
        ws = AsyncMock()
        await event_manager.connect(ws)
        assert event_manager.connection_count == 1
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disconnect_decrements_count(self, event_manager):
        ws = AsyncMock()
        await event_manager.connect(ws)
        await event_manager.disconnect(ws)
        assert event_manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_is_safe(self, event_manager):
        ws = AsyncMock()
        await event_manager.disconnect(ws)
        assert event_manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self, event_manager):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await event_manager.connect(ws1)
        await event_manager.connect(ws2)
        await event_manager.broadcast("score", {"score": 60})
        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self, event_manager):
        ws_alive = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_json.side_effect = Exception("Connection closed")
        await event_manager.connect(ws_alive)
        await event_manager.connect(ws_dead)
        assert event_manager.connection_count == 2
        await event_manager.broadcast("test", {})
        assert event_manager.connection_count == 1

    def test_broadcast_sync_no_loop(self, event_manager):
        """broadcast_sync should not raise when no event loop."""
        event_manager.broadcast_sync("test", {})
