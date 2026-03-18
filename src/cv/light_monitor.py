"""Light Stability Monitor — tracks frame brightness variance over a rolling window.

When lighting changes rapidly (e.g. someone walking past, lights flickering),
detection thresholds should be temporarily raised to avoid false positives.
"""

from __future__ import annotations

import logging
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)


class LightStabilityMonitor:
    """Monitors frame brightness stability over a rolling window.

    Parameters
    ----------
    variance_threshold:
        Maximum allowed variance in mean brightness across the window.
        Above this, lighting is considered unstable.
    window_size:
        Number of recent frames to track.
    """

    def __init__(
        self,
        variance_threshold: float = 15.0,
        window_size: int = 10,
    ) -> None:
        if variance_threshold <= 0:
            raise ValueError("variance_threshold must be > 0")
        if window_size < 2:
            raise ValueError("window_size must be >= 2")

        self.variance_threshold = variance_threshold
        self.window_size = window_size
        self._brightness_history: deque[float] = deque(maxlen=window_size)

    def update(self, frame: np.ndarray) -> None:
        """Record the mean brightness of a grayscale frame."""
        mean_val = float(np.mean(frame))
        self._brightness_history.append(mean_val)

    def is_light_unstable(self) -> bool:
        """Return True if brightness variance exceeds threshold."""
        if len(self._brightness_history) < 2:
            return False
        variance = float(np.var(self._brightness_history))
        return variance > self.variance_threshold

    def get_variance(self) -> float:
        """Return current brightness variance (0.0 if insufficient data)."""
        if len(self._brightness_history) < 2:
            return 0.0
        return float(np.var(self._brightness_history))

    def reset(self) -> None:
        """Clear brightness history."""
        self._brightness_history.clear()
