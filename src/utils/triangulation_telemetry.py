"""Triangulation telemetry: ring-buffer for stereo fusion outcomes."""

import threading
from collections import deque
from dataclasses import dataclass, field


@dataclass
class TriangulationSample:
    """Single triangulation attempt record."""
    source: str  # "triangulation", "voting_fallback", "single_fallback", "z_rejected"
    reprojection_error: float | None = None
    z_depth: float | None = None


class TriangulationTelemetry:
    """Tracks triangulation success/failure rates in a fixed-size ring buffer.

    Thread-safe. Provides alert when failure rate exceeds threshold.
    """

    def __init__(self, max_samples: int = 300) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be >= 1")
        self._samples: deque[TriangulationSample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()

        # Counters (lifetime, not bounded by ring buffer)
        self.total_attempts: int = 0
        self.triangulation_ok: int = 0
        self.voting_fallback: int = 0
        self.single_fallback: int = 0
        self.z_rejected: int = 0

    def record_attempt(
        self,
        source: str,
        reprojection_error: float | None = None,
        z_depth: float | None = None,
    ) -> None:
        """Record a triangulation attempt outcome."""
        sample = TriangulationSample(
            source=source,
            reprojection_error=reprojection_error,
            z_depth=z_depth,
        )
        with self._lock:
            self._samples.append(sample)
            self.total_attempts += 1
            if source == "triangulation":
                self.triangulation_ok += 1
            elif source == "voting_fallback":
                self.voting_fallback += 1
            elif source == "single_fallback":
                self.single_fallback += 1
            elif source == "z_rejected":
                self.z_rejected += 1

    @property
    def failure_rate(self) -> float:
        """Fraction of samples in the ring buffer that are NOT successful triangulations."""
        with self._lock:
            if not self._samples:
                return 0.0
            failures = sum(1 for s in self._samples if s.source != "triangulation")
            return failures / len(self._samples)

    @property
    def failure_alert_active(self) -> bool:
        """True if failure rate > 30% AND at least 10 samples in buffer."""
        with self._lock:
            if len(self._samples) < 10:
                return False
            failures = sum(1 for s in self._samples if s.source != "triangulation")
            return (failures / len(self._samples)) > 0.30

    @property
    def sample_count(self) -> int:
        with self._lock:
            return len(self._samples)

    def get_summary(self) -> dict:
        """Return summary stats over the buffer and lifetime counters."""
        with self._lock:
            if not self._samples:
                return {
                    "samples": 0,
                    "total_attempts": self.total_attempts,
                    "triangulation_ok": self.triangulation_ok,
                    "voting_fallback": self.voting_fallback,
                    "single_fallback": self.single_fallback,
                    "z_rejected": self.z_rejected,
                    "failure_rate": 0.0,
                    "failure_alert": False,
                }

            reproj_vals = [
                s.reprojection_error for s in self._samples
                if s.reprojection_error is not None
            ]
            z_vals = [
                s.z_depth for s in self._samples
                if s.z_depth is not None
            ]
            failures = sum(1 for s in self._samples if s.source != "triangulation")
            n = len(self._samples)

            summary: dict = {
                "samples": n,
                "total_attempts": self.total_attempts,
                "triangulation_ok": self.triangulation_ok,
                "voting_fallback": self.voting_fallback,
                "single_fallback": self.single_fallback,
                "z_rejected": self.z_rejected,
                "failure_rate": round(failures / n, 3),
                "failure_alert": n >= 10 and (failures / n) > 0.30,
            }

            if reproj_vals:
                summary["reproj_min"] = round(min(reproj_vals), 4)
                summary["reproj_max"] = round(max(reproj_vals), 4)
                summary["reproj_avg"] = round(sum(reproj_vals) / len(reproj_vals), 4)

            if z_vals:
                summary["z_depth_min"] = round(min(z_vals), 4)
                summary["z_depth_max"] = round(max(z_vals), 4)
                summary["z_depth_avg"] = round(sum(z_vals) / len(z_vals), 4)

            return summary
