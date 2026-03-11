"""Thread-safe video capture with bounded queue and graceful frame dropping."""

import cv2
import numpy as np
import threading
import queue
import time
import logging

logger = logging.getLogger(__name__)


class ThreadedCamera:
    """Thread-safe video capture with bounded queue and graceful frame dropping."""

    def __init__(self, src: int | str = 0, max_queue_size: int = 5) -> None:
        """
        Args:
            src: Camera index (int) or video file path (str).
            max_queue_size: Maximum frames in queue before dropping oldest.
        """
        self.src = src
        self.capture = cv2.VideoCapture(src)
        if not self.capture.isOpened():
            raise RuntimeError(f"Cannot open camera source: {src}")

        # Reduce internal OpenCV buffer to minimize latency
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.frame_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_queue_size)
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the capture thread."""
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Camera capture started (src=%s)", self.src)

    def _capture_loop(self) -> None:
        reconnect_delay = 1.0
        max_reconnect_delay = 30.0

        while self._running:
            ret, frame = self.capture.read()
            if not ret:
                # Auto-reconnect with exponential backoff
                logger.warning("Frame read failed, reconnecting in %.1fs...", reconnect_delay)
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                self.capture.release()
                self.capture = cv2.VideoCapture(self.src)
                continue

            reconnect_delay = 1.0  # Reset on success

            # Graceful frame dropping: drop oldest if queue full
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                pass

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the latest frame. Returns (success, frame)."""
        try:
            frame = self.frame_queue.get(timeout=0.1)
            return True, frame
        except queue.Empty:
            return False, None

    def stop(self) -> None:
        """Stop capture thread and release camera."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self.capture.release()
        logger.info("Camera capture stopped")

    def is_running(self) -> bool:
        """Check if capture thread is active."""
        return self._running

    @property
    def frame_size(self) -> tuple[int, int]:
        """Return (width, height) of captured frames."""
        w = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)
