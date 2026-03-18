"""Video recorder for capturing camera frames to .mp4 files.

Supports recording raw camera frames during live pipeline operation.
Thread-safe: can be started/stopped from API routes while pipeline runs.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Default output directory
DEFAULT_OUTPUT_DIR = "testvids"

# Recording defaults
DEFAULT_FPS = 30.0
DEFAULT_CODEC = "mp4v"


class VideoRecorder:
    """Records camera frames to an .mp4 file.

    Usage:
        recorder = VideoRecorder()
        recorder.start("testvids/session_001.mp4", fps=30, frame_size=(640, 480))
        # In frame loop:
        recorder.write(frame)
        # When done:
        recorder.stop()
    """

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR) -> None:
        self.output_dir = output_dir
        self._writer: cv2.VideoWriter | None = None
        self._lock = threading.Lock()
        self._recording = False
        self._frame_count = 0
        self._start_time: float = 0.0
        self._output_path: str = ""

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def output_path(self) -> str:
        return self._output_path

    @property
    def elapsed_s(self) -> float:
        if not self._recording:
            return 0.0
        return time.monotonic() - self._start_time

    def status(self) -> dict:
        """Return current recording status."""
        return {
            "recording": self._recording,
            "output_path": self._output_path,
            "frame_count": self._frame_count,
            "elapsed_s": round(self.elapsed_s, 1),
        }

    def start(self, filename: str | None = None,
              fps: float = DEFAULT_FPS,
              frame_size: tuple[int, int] = (640, 480)) -> str:
        """Start recording to file. Returns output path.

        Args:
            filename: Output filename (auto-generated if None).
            fps: Target frames per second for the output file.
            frame_size: (width, height) of frames to be written.

        Returns:
            Absolute path of the output file.
        """
        with self._lock:
            if self._recording:
                raise RuntimeError("Aufnahme laeuft bereits")

            os.makedirs(self.output_dir, exist_ok=True)

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"rec_{timestamp}.mp4"

            self._output_path = os.path.join(self.output_dir, filename)

            fourcc = cv2.VideoWriter_fourcc(*DEFAULT_CODEC)
            self._writer = cv2.VideoWriter(
                self._output_path, fourcc, fps,
                frame_size, isColor=True,
            )

            if not self._writer.isOpened():
                self._writer = None
                raise RuntimeError(
                    f"VideoWriter konnte nicht geoeffnet werden: {self._output_path}"
                )

            self._recording = True
            self._frame_count = 0
            self._start_time = time.monotonic()
            logger.info("Recording gestartet: %s (%.0f fps, %dx%d)",
                        self._output_path, fps, frame_size[0], frame_size[1])
            return self._output_path

    def write(self, frame: np.ndarray) -> None:
        """Write a single frame. No-op if not recording."""
        if not self._recording:
            return
        with self._lock:
            if self._writer is not None:
                self._writer.write(frame)
                self._frame_count += 1

    def stop(self) -> dict:
        """Stop recording and finalize the file. Returns summary."""
        with self._lock:
            if not self._recording:
                return {"stopped": False, "reason": "Keine Aufnahme aktiv"}

            elapsed = time.monotonic() - self._start_time
            self._recording = False

            if self._writer is not None:
                self._writer.release()
                self._writer = None

            summary = {
                "stopped": True,
                "output_path": self._output_path,
                "frame_count": self._frame_count,
                "elapsed_s": round(elapsed, 1),
                "avg_fps": round(self._frame_count / elapsed, 1) if elapsed > 0 else 0.0,
            }
            logger.info("Recording gestoppt: %s (%d Frames, %.1fs, %.1f fps)",
                        self._output_path, self._frame_count,
                        elapsed, summary["avg_fps"])
            return summary
