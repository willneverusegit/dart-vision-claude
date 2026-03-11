"""FPS counter with rolling average."""

import time
from collections import deque


class FPSCounter:
    """Tracks frames per second with a rolling window average."""

    def __init__(self, window_size: int = 30) -> None:
        self._timestamps: deque[float] = deque(maxlen=window_size)

    def update(self) -> None:
        """Record a frame timestamp."""
        self._timestamps.append(time.monotonic())

    def fps(self) -> float:
        """Return current FPS based on rolling window."""
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / elapsed
