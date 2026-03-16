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

    # Conservative defaults for CPU-constrained hardware (e.g. i5-1035G1)
    DEFAULT_WIDTH = 640
    DEFAULT_HEIGHT = 480
    DEFAULT_FPS = 30

    def __init__(
        self,
        src: int | str = 0,
        max_queue_size: int = 5,
        width: int | None = None,
        height: int | None = None,
        fps: int | None = None,
    ) -> None:
        """
        Args:
            src: Camera index (int) or video file path (str).
            max_queue_size: Maximum frames in queue before dropping oldest.
            width: Requested capture width (default 640).
            height: Requested capture height (default 480).
            fps: Requested capture FPS (default 30).
        """
        self.src = src
        self.capture = cv2.VideoCapture(src)
        if not self.capture.isOpened():
            raise RuntimeError(f"Cannot open camera source: {src}")

        # Reduce internal OpenCV buffer to minimize latency
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Apply capture resolution and FPS — keeps hardware load predictable
        req_w = width if width is not None else self.DEFAULT_WIDTH
        req_h = height if height is not None else self.DEFAULT_HEIGHT
        req_fps = fps if fps is not None else self.DEFAULT_FPS
        self._req_width = req_w
        self._req_height = req_h
        self._req_fps = req_fps
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, req_w)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, req_h)
        self.capture.set(cv2.CAP_PROP_FPS, req_fps)

        actual_w = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.capture.get(cv2.CAP_PROP_FPS)
        if actual_w != req_w or actual_h != req_h:
            logger.warning(
                "Requested %dx%d but camera reports %dx%d — hardware may not support this resolution",
                req_w, req_h, actual_w, actual_h,
            )
        logger.info("Capture config: %dx%d @ %.0f fps (src=%s)", actual_w, actual_h, actual_fps, src)

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

    def _apply_capture_props(self) -> None:
        """(Re-)apply resolution and FPS settings to the capture device."""
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._req_width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._req_height)
        self.capture.set(cv2.CAP_PROP_FPS, self._req_fps)

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
                self._apply_capture_props()
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

    def get_capture_config(self) -> dict:
        """Return requested and actual capture settings."""
        actual_w = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.capture.get(cv2.CAP_PROP_FPS)
        return {
            "requested": {
                "width": self._req_width,
                "height": self._req_height,
                "fps": self._req_fps,
            },
            "actual": {
                "width": actual_w,
                "height": actual_h,
                "fps": round(actual_fps, 1),
            },
            "mismatch": actual_w != self._req_width or actual_h != self._req_height,
        }

    def apply_settings(self, width: int, height: int, fps: int) -> dict:
        """Apply new capture settings by restarting the camera.

        Stops the capture thread, re-opens the device with new settings,
        and restarts. Returns the resulting capture config.
        """
        was_running = self._running
        if was_running:
            self._running = False
            if self._thread is not None:
                self._thread.join(timeout=5.0)

        self.capture.release()

        self._req_width = width
        self._req_height = height
        self._req_fps = fps

        self.capture = cv2.VideoCapture(self.src)
        if not self.capture.isOpened():
            raise RuntimeError(f"Cannot re-open camera source: {self.src}")
        self._apply_capture_props()

        actual_w = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self.capture.get(cv2.CAP_PROP_FPS)
        logger.info("Capture settings applied: %dx%d @ %.0f fps (src=%s)",
                     actual_w, actual_h, actual_fps, self.src)

        # Drain old frames
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

        if was_running:
            self.start()

        return self.get_capture_config()
