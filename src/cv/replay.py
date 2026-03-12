"""Replay camera source for deterministic offline CV evaluation."""

import cv2
import numpy as np
import time


class ReplayCamera:
    """Video-backed camera adapter with the same read() contract as ThreadedCamera.

    This source is intentionally simple:
    - No frame queue, no background thread
    - Deterministic frame order for replay tests
    - Optional loop mode for long-running local debugging
    """

    def __init__(self, video_path: str, loop: bool = False, throttle_fps: float | None = None) -> None:
        self.video_path = video_path
        self.loop = loop
        self.throttle_fps = throttle_fps
        self.capture = cv2.VideoCapture(video_path)
        if not self.capture.isOpened():
            raise RuntimeError(f"Cannot open replay source: {video_path}")
        self._running = False
        self._last_read_ts = 0.0

    def start(self) -> None:
        """Mark the replay source as active."""
        self._running = True

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the next replay frame, optionally throttled."""
        if not self._running:
            self.start()

        if self.throttle_fps and self.throttle_fps > 0:
            min_dt = 1.0 / self.throttle_fps
            dt = time.time() - self._last_read_ts
            if dt < min_dt:
                time.sleep(min_dt - dt)

        ok, frame = self.capture.read()
        if ok and frame is not None:
            self._last_read_ts = time.time()
            return True, frame

        if not self.loop:
            return False, None

        # Loop playback by seeking to frame 0 and trying once more.
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ok, frame = self.capture.read()
        if ok and frame is not None:
            self._last_read_ts = time.time()
            return True, frame
        return False, None

    def stop(self) -> None:
        """Stop replay source and release file handle."""
        self._running = False
        self.capture.release()

    def is_running(self) -> bool:
        """Expose running state for compatibility with ThreadedCamera."""
        return self._running

    @property
    def frame_size(self) -> tuple[int, int]:
        """Return replay frame dimensions as (width, height)."""
        w = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)
