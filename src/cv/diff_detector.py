"""Frame-Diff-basierte Dart-Treffererkennung.

Ansatz: Stabilen Frame vor dem Wurf (Baseline) gegen stabilen Frame nach
dem Wurf diffen. Der neue stationäre Bereich = Dart-Silhouette.
MOG2-Motion-Flag steuert nur die State-Machine, nicht die Positionsbestimmung.

WICHTIG: update() muss für JEDEN Frame aufgerufen werden, auch bewegungsfreie —
der SETTLING-State braucht bewegungsfreie Frames zum Herunterzählen.
"""

from __future__ import annotations

import logging
from enum import Enum

import cv2
import numpy as np

from src.cv.detector import DartDetection

logger = logging.getLogger(__name__)


class _State(Enum):
    IDLE = "idle"
    IN_MOTION = "in_motion"
    SETTLING = "settling"


class FrameDiffDetector:
    """Erkennt Dart-Treffer via Before/After-Frame-Differenz.

    Parameters
    ----------
    settle_frames:
        Anzahl aufeinanderfolgender bewegungsfreier Frames bevor der Diff
        berechnet wird. Empfehlung: 5 bei 30fps (~167ms Wartezeit).
    diff_threshold:
        Minimale Pixelintensitäts-Differenz um als Änderung zu zählen (1-255).
        50 filtert Beleuchtungsrauschen gut heraus.
    min_diff_area:
        Minimale Fläche (px²) des Diff-Blobs damit es als Dart gilt.
    max_diff_area:
        Maximale Fläche (px²) — Sanity-Check gegen globale Beleuchtungsänderungen.
    """

    def __init__(
        self,
        settle_frames: int = 5,
        diff_threshold: int = 50,
        min_diff_area: int = 50,
        max_diff_area: int = 8000,
    ) -> None:
        if settle_frames < 1:
            raise ValueError("settle_frames must be >= 1")
        if not (0 < diff_threshold < 256):
            raise ValueError("diff_threshold must be in 1..255")
        if min_diff_area >= max_diff_area:
            raise ValueError("min_diff_area must be < max_diff_area")

        self.settle_frames = settle_frames
        self.diff_threshold = diff_threshold
        self.min_diff_area = min_diff_area
        self.max_diff_area = max_diff_area

        self._state = _State.IDLE
        self._baseline: np.ndarray | None = None
        self._settle_count: int = 0
        self._closing_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, frame: np.ndarray, has_motion: bool) -> DartDetection | None:
        """Einen Frame verarbeiten. Gibt DartDetection zurück wenn Dart gelandet.

        Muss für JEDEN Frame aufgerufen werden — auch wenn has_motion=False.
        Frames müssen single-channel (Grayscale) sein.
        """
        if self._state == _State.IDLE:
            return self._handle_idle(frame, has_motion)
        if self._state == _State.IN_MOTION:
            return self._handle_in_motion(frame, has_motion)
        if self._state == _State.SETTLING:
            return self._handle_settling(frame, has_motion)
        return None  # pragma: no cover

    def reset(self) -> None:
        """State zurücksetzen (nach Dart-Entfernung / Turn-Reset)."""
        self._state = _State.IDLE
        self._baseline = None
        self._settle_count = 0

    @property
    def state(self) -> str:
        return self._state.value

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _handle_idle(self, frame: np.ndarray, has_motion: bool) -> DartDetection | None:
        if has_motion:
            # Motion detected — freeze baseline at last stable frame, switch state
            self._state = _State.IN_MOTION
            self._settle_count = 0
            logger.debug("FrameDiff: IDLE → IN_MOTION")
        else:
            # No motion — update baseline continuously
            self._baseline = frame.copy()
        return None

    def _handle_in_motion(self, frame: np.ndarray, has_motion: bool) -> DartDetection | None:
        if has_motion:
            return None  # Bewegung geht weiter, Baseline eingefroren
        # Bewegung aufgehört → Settling starten (count beginnt bei 1)
        self._state = _State.SETTLING
        self._settle_count = 1
        logger.debug("FrameDiff: IN_MOTION → SETTLING (settle_count=1)")
        return None

    def _handle_settling(self, frame: np.ndarray, has_motion: bool) -> DartDetection | None:
        if has_motion:
            # Dart wackelt noch — zurück zu IN_MOTION, Baseline bleibt eingefroren
            self._state = _State.IN_MOTION
            self._settle_count = 0
            logger.debug("FrameDiff: SETTLING → IN_MOTION (motion resumed)")
            return None

        self._settle_count += 1  # count starts at 1 (set in _handle_in_motion) → fires when == settle_frames
        if self._settle_count < self.settle_frames:
            return None

        # Genug stabile Frames — Diff berechnen
        detection = self._compute_diff(frame)
        self._state = _State.IDLE
        self._settle_count = 0
        return detection

    # ------------------------------------------------------------------
    # Diff-Berechnung (CPU-konservativ: absdiff + threshold + closing)
    # ------------------------------------------------------------------

    def _compute_diff(self, post_frame: np.ndarray) -> DartDetection | None:
        if self._baseline is None:
            logger.warning("FrameDiff: _compute_diff aufgerufen ohne Baseline — übersprungen")
            return None

        if post_frame.ndim != 2 or self._baseline.ndim != 2:
            raise ValueError("FrameDiffDetector requires single-channel (grayscale) frames")

        diff = cv2.absdiff(self._baseline, post_frame)
        _, thresh = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)

        # Morphologisches Closing: schließt Konturlücken (Dart-Schaft)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, self._closing_kernel)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            logger.debug("FrameDiff: kein Kontur im Diff")
            return None

        # Größten Blob nehmen (Dart-Körper dominiert)
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        if area < self.min_diff_area:
            logger.debug("FrameDiff: Diff-Blob zu klein (%.0f px²)", area)
            return None
        if area > self.max_diff_area:
            logger.debug("FrameDiff: Diff-Blob zu groß (%.0f px²) — Beleuchtungsaenderung?", area)
            return None

        # Centroid als vorläufige Position (P20 ersetzt dies durch Tip-Detection)
        M = cv2.moments(largest)
        if M["m00"] <= 0:
            return None
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        confidence = min(area / 500.0, 1.0)
        logger.info("FrameDiff: Dart bei (%d, %d) area=%.0f conf=%.2f", cx, cy, area, confidence)
        # frame_count repurposed here as "settle duration" (== settle_frames at this callsite).
        # P20 will replace this with tip-detection and can clean up the field semantics then.
        return DartDetection(center=(cx, cy), area=area, confidence=confidence, frame_count=self.settle_frames)
