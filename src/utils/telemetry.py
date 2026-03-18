"""Telemetry history: ring-buffer for FPS, queue pressure, dropped frames, CPU."""

import json
import logging
import os
import threading
from collections import deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TelemetrySample:
    """Single telemetry snapshot."""
    timestamp: float
    fps: float
    queue_pressure: float
    dropped_frames: int
    memory_mb: float
    cpu_percent: float | None = None


class TelemetryHistory:
    """Collects telemetry samples in a fixed-size ring buffer.

    Provides alert detection when metrics cross thresholds.
    """

    def __init__(
        self,
        max_samples: int = 300,
        fps_alert_threshold: float = 15.0,
        queue_alert_threshold: float = 0.8,
        alert_sustain_seconds: float = 5.0,
    ) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be >= 1")
        if fps_alert_threshold < 0:
            raise ValueError("fps_alert_threshold must be >= 0")
        if not (0 <= queue_alert_threshold <= 1):
            raise ValueError("queue_alert_threshold must be between 0 and 1")

        self._samples: deque[TelemetrySample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self.fps_alert_threshold = fps_alert_threshold
        self.queue_alert_threshold = queue_alert_threshold
        self._alert_sustain = alert_sustain_seconds

        # Alert state
        self._fps_alert_since: float | None = None
        self._queue_alert_since: float | None = None

        # Optional JSONL writer
        self._jsonl_writer: TelemetryJSONLWriter | None = None

    def attach_jsonl_writer(self, writer: "TelemetryJSONLWriter") -> None:
        """Attach a JSONL writer for persistent telemetry logging."""
        self._jsonl_writer = writer

    def record(self, sample: TelemetrySample) -> None:
        """Add a telemetry sample."""
        with self._lock:
            self._samples.append(sample)
            self._update_alerts(sample)
        # Write to JSONL outside the lock to avoid blocking
        if self._jsonl_writer is not None:
            self._jsonl_writer.write(sample)

    def _update_alerts(self, sample: TelemetrySample) -> None:
        """Update alert state based on latest sample."""
        now = sample.timestamp

        # FPS alert
        if sample.fps > 0 and sample.fps < self.fps_alert_threshold:
            if self._fps_alert_since is None:
                self._fps_alert_since = now
        else:
            self._fps_alert_since = None

        # Queue pressure alert
        if sample.queue_pressure > self.queue_alert_threshold:
            if self._queue_alert_since is None:
                self._queue_alert_since = now
        else:
            self._queue_alert_since = None

    @property
    def fps_alert_active(self) -> bool:
        """True if FPS has been below threshold for sustain period."""
        if self._fps_alert_since is None:
            return False
        with self._lock:
            if not self._samples:
                return False
            elapsed = self._samples[-1].timestamp - self._fps_alert_since
            return elapsed >= self._alert_sustain

    @property
    def queue_alert_active(self) -> bool:
        """True if queue pressure has been above threshold for sustain period."""
        if self._queue_alert_since is None:
            return False
        with self._lock:
            if not self._samples:
                return False
            elapsed = self._samples[-1].timestamp - self._queue_alert_since
            return elapsed >= self._alert_sustain

    def get_history(self, last_n: int | None = None) -> list[dict]:
        """Return telemetry history as list of dicts."""
        with self._lock:
            samples = list(self._samples)
        if last_n is not None and last_n > 0:
            samples = samples[-last_n:]
        return [
            {
                "t": round(s.timestamp, 2),
                "fps": round(s.fps, 1),
                "queue": round(s.queue_pressure, 2),
                "drops": s.dropped_frames,
                "mem": round(s.memory_mb, 1),
                "cpu": round(s.cpu_percent, 1) if s.cpu_percent is not None else None,
            }
            for s in samples
        ]

    def get_alerts(self) -> dict:
        """Return current alert state."""
        return {
            "fps_low": self.fps_alert_active,
            "queue_high": self.queue_alert_active,
            "fps_threshold": self.fps_alert_threshold,
            "queue_threshold": self.queue_alert_threshold,
        }

    @property
    def sample_count(self) -> int:
        with self._lock:
            return len(self._samples)

    def get_summary(self) -> dict:
        """Return summary stats over the buffer."""
        with self._lock:
            if not self._samples:
                return {"samples": 0}
            fps_vals = [s.fps for s in self._samples if s.fps > 0]
            queue_vals = [s.queue_pressure for s in self._samples]
            return {
                "samples": len(self._samples),
                "fps_min": round(min(fps_vals), 1) if fps_vals else 0,
                "fps_max": round(max(fps_vals), 1) if fps_vals else 0,
                "fps_avg": round(sum(fps_vals) / len(fps_vals), 1) if fps_vals else 0,
                "queue_avg": round(sum(queue_vals) / len(queue_vals), 2),
                "queue_max": round(max(queue_vals), 2),
                "total_drops": self._samples[-1].dropped_frames,
            }


class TelemetryJSONLWriter:
    """Writes telemetry samples as JSONL to a file.

    Activated via DARTVISION_TELEMETRY_FILE environment variable.
    Each line is a JSON object with session_id and sample data.
    """

    def __init__(self, filepath: str, session_id: str) -> None:
        self._filepath = filepath
        self._session_id = session_id
        self._lock = threading.Lock()
        # Ensure directory exists
        dirpath = os.path.dirname(filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        logger.info("Telemetry JSONL writer: %s (session=%s)", filepath, session_id)

    @property
    def filepath(self) -> str:
        return self._filepath

    @property
    def session_id(self) -> str:
        return self._session_id

    def write(self, sample: TelemetrySample) -> None:
        """Append a single sample as a JSON line."""
        record = {
            "session": self._session_id,
            "t": round(sample.timestamp, 3),
            "fps": round(sample.fps, 1),
            "queue": round(sample.queue_pressure, 3),
            "drops": sample.dropped_frames,
            "mem": round(sample.memory_mb, 1),
            "cpu": round(sample.cpu_percent, 1) if sample.cpu_percent is not None else None,
        }
        line = json.dumps(record, separators=(",", ":")) + "\n"
        with self._lock:
            try:
                with open(self._filepath, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                logger.warning("Failed to write telemetry JSONL", exc_info=True)

    @staticmethod
    def from_env(session_id: str) -> "TelemetryJSONLWriter | None":
        """Create writer if DARTVISION_TELEMETRY_FILE is set, else None."""
        path = os.environ.get("DARTVISION_TELEMETRY_FILE")
        if not path:
            return None
        return TelemetryJSONLWriter(path, session_id)
