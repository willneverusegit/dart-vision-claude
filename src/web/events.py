"""EventManager: WebSocket broadcast and event distribution."""

import asyncio
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventManager:
    """Manages WebSocket connections and broadcasts game events."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info("WebSocket connected (%d total)", len(self._connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info("WebSocket disconnected (%d remaining)", len(self._connections))

    async def broadcast(self, event_type: str, data: dict) -> None:
        """Broadcast an event to all connected WebSocket clients."""
        message = {"type": event_type, "data": data}
        dead: list[WebSocket] = []
        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)
            logger.info("Removed %d dead connections", len(dead))

    def broadcast_sync(self, event_type: str, data: dict) -> None:
        """Synchronous wrapper for broadcast (for use from sync code)."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(event_type, data))
        except RuntimeError:
            logger.debug("No event loop for broadcast, skipping")

    @property
    def connection_count(self) -> int:
        """Number of active WebSocket connections."""
        return len(self._connections)
