"""EventManager: WebSocket broadcast and event distribution."""

import asyncio
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventManager:
    """Manages WebSocket connections and broadcasts game events.

    Thread-safe: broadcast_sync() can be called from any thread
    as long as set_loop() was called with the main asyncio loop.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store reference to the main asyncio event loop for cross-thread use."""
        self._loop = loop
        logger.info("EventManager bound to event loop")

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
        """Thread-safe synchronous wrapper for broadcast.

        Uses asyncio.run_coroutine_threadsafe to schedule the broadcast
        on the main event loop. Safe to call from any thread (e.g., CV pipeline).
        """
        if self._loop is None or self._loop.is_closed():
            logger.debug("No event loop bound, broadcast skipped (%s)", event_type)
            return

        try:
            future = asyncio.run_coroutine_threadsafe(
                self.broadcast(event_type, data), self._loop
            )
            # Don't block waiting for result — fire and forget
            future.add_done_callback(self._broadcast_done)
        except RuntimeError as e:
            logger.debug("broadcast_sync failed: %s", e)

    @staticmethod
    def _broadcast_done(future: asyncio.Future) -> None:
        """Callback for completed broadcast futures (logs errors)."""
        try:
            future.result()
        except Exception as e:
            logger.error("Broadcast error: %s", e)

    @property
    def connection_count(self) -> int:
        """Number of active WebSocket connections."""
        return len(self._connections)
