"""Frame-Diff-basierte Dart-Treffererkennung.

Ansatz: Stabilen Frame vor dem Wurf (Baseline) gegen stabilen Frame nach
dem Wurf diffen. Der neue stationäre Bereich = Dart-Silhouette.
MOG2-Motion-Flag steuert nur die State-Machine, nicht die Positionsbestimmung.

WICHTIG: update() muss für JEDEN Frame aufgerufen werden, auch bewegungsfreie —
der SETTLING-State braucht bewegungsfreie Frames zum Herunterzählen.
"""

from __future__ import annotations

import json
import logging
import time
from enum import Enum
from pathlib import Path

import cv2
import numpy as np

from src.cv.detector import DartDetection, compute_dart_confidence
from src.cv.light_monitor import LightStabilityMonitor
from src.cv.sharpness import SharpnessTracker, adjusted_diff_threshold, compute_wire_filter_kernel_size
from src.cv.tip_detection import find_dart_tip

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
        Default 30 px² ermöglicht Outer-Bull-Erkennung (~40px Blobs).
    max_diff_area:
        Maximale Fläche (px²) — Sanity-Check gegen globale Beleuchtungsänderungen.
    """

    def __init__(
        self,
        settle_frames: int = 3,
        diff_threshold: int = 30,
        min_diff_area: int = 30,
        max_diff_area: int = 8000,
        diagnostics_dir: str | None = None,
        min_elongation: float = 1.2,
        bounce_diff_threshold: float = 0.2,
        bounce_check_frames: int = 3,
        stability_frames: int = 2,
        stability_max_drift_px: float = 5.0,
        adaptive_threshold: bool = True,
        otsu_bias_factor: float = 0.7,
        min_threshold: int = 20,
        search_mode_frames: int = 90,
        search_mode_threshold_factor: float = 0.8,
        light_variance_threshold: float = 15.0,
        light_window_size: int = 10,
        baseline_avg_frames: int = 5,
        pre_blur_ksize: int = 3,
    ) -> None:
        if settle_frames < 1:
            raise ValueError("settle_frames must be >= 1")
        if not (0 < diff_threshold < 256):
            raise ValueError("diff_threshold must be in 1..255")
        if min_diff_area >= max_diff_area:
            raise ValueError("min_diff_area must be < max_diff_area")
        if min_elongation < 1.0:
            raise ValueError("min_elongation must be >= 1.0")
        if stability_frames < 1:
            raise ValueError("stability_frames must be >= 1")
        if stability_max_drift_px <= 0:
            raise ValueError("stability_max_drift_px must be > 0")

        self.settle_frames = settle_frames
        self.diff_threshold = diff_threshold
        self.min_diff_area = min_diff_area
        self.max_diff_area = max_diff_area
        self.min_elongation = min_elongation
        self.bounce_diff_threshold = bounce_diff_threshold
        self.bounce_check_frames = bounce_check_frames
        self.stability_frames = stability_frames
        self.stability_max_drift_px = stability_max_drift_px
        self.adaptive_threshold = adaptive_threshold
        self.otsu_bias_factor = otsu_bias_factor
        self.min_threshold = min_threshold
        self.search_mode_frames = search_mode_frames
        self.search_mode_threshold_factor = search_mode_threshold_factor

        self._no_detect_count: int = 0

        # Baseline averaging: accumulate N idle frames to reduce temporal noise
        self._baseline_avg_frames = max(1, baseline_avg_frames)
        self._baseline_accum: list[np.ndarray] = []

        # Pre-blur: Gaussian kernel size applied before absdiff (0 = disabled)
        self._pre_blur_ksize = pre_blur_ksize if pre_blur_ksize > 1 else 0

        # Sharpness tracking for per-camera quality compensation
        self._sharpness_tracker = SharpnessTracker(ema_alpha=0.1, sample_interval=10)
        self._sharpness_adjust_enabled: bool = True

        # Light stability monitor
        self._light_monitor = LightStabilityMonitor(
            variance_threshold=light_variance_threshold,
            window_size=light_window_size,
        )
        self._base_diff_threshold = diff_threshold  # original threshold for restore

        self._state = _State.IDLE
        self._baseline: np.ndarray | None = None
        self._settle_count: int = 0
        self._had_motion_event: bool = False
        self._stability_centroids: list[tuple[int, int]] = []
        # Three-stage morphology:
        # 1) Opening with small kernel removes thin board-wire artefacts
        # 2) Ellipse closing fills small gaps
        # 3) Elongated closing connects dart shaft fragments along the main axis
        self._opening_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        self._closing_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self._elongated_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 11))

        # Edge cache: compute Canny edges once per detection, reuse for
        # contour analysis and any future HoughLinesP calls (P41).
        self._edge_cache_enabled: bool = True
        self._cached_edges: np.ndarray | None = None
        self._cached_edges_frame_id: int = -1
        self._frame_id: int = 0

        # P47: Diff + morphology cache — avoid redundant cv2.absdiff
        # between _quick_centroid and _compute_diff on the same frame.
        self._cached_diff: np.ndarray | None = None
        self._cached_diff_frame_id: int = -1
        self._cached_morph: np.ndarray | None = None
        self._cached_morph_frame_id: int = -1

        # Diagnostics: save diff masks + contour images on each detection
        self._diagnostics_dir: Path | None = None
        if diagnostics_dir is not None:
            self._diagnostics_dir = Path(diagnostics_dir)
            self._diagnostics_dir.mkdir(parents=True, exist_ok=True)
            logger.info("FrameDiff diagnostics enabled → %s", self._diagnostics_dir)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_cached_edges(self, frame: np.ndarray) -> np.ndarray:
        """Return Canny edges for the given frame, using cache if available.

        Computes Canny edges once per frame_id and caches the result.
        Subsequent calls within the same frame return the cached edges.
        """
        if (
            self._edge_cache_enabled
            and self._cached_edges is not None
            and self._cached_edges_frame_id == self._frame_id
        ):
            return self._cached_edges

        edges = cv2.Canny(frame, 50, 150)
        if self._edge_cache_enabled:
            self._cached_edges = edges
            self._cached_edges_frame_id = self._frame_id
        return edges

    def update(self, frame: np.ndarray, has_motion: bool) -> DartDetection | None:
        """Einen Frame verarbeiten. Gibt DartDetection zurück wenn Dart gelandet.

        Muss für JEDEN Frame aufgerufen werden — auch wenn has_motion=False.
        Frames müssen single-channel (Grayscale) sein.
        """
        self._frame_id += 1
        # Update sharpness tracker
        self._sharpness_tracker.update(frame)

        # Update light stability monitor and adjust threshold
        self._light_monitor.update(frame)
        if self._light_monitor.is_light_unstable():
            # Raise threshold by 50% during unstable lighting
            self.diff_threshold = min(int(self._base_diff_threshold * 1.5), 254)
        elif self._sharpness_adjust_enabled and self._sharpness_tracker.sharpness > 0:
            # Sharpness-based threshold adjustment
            self.diff_threshold = adjusted_diff_threshold(
                self._base_diff_threshold,
                self._sharpness_tracker.sharpness,
            )
        else:
            self.diff_threshold = self._base_diff_threshold

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
        self._baseline_accum.clear()
        self._settle_count = 0
        self._had_motion_event = False
        self._stability_centroids = []
        self._cached_edges = None
        self._cached_diff = None
        self._cached_diff_frame_id = -1
        self._cached_morph = None
        self._cached_morph_frame_id = -1
        self._light_monitor.reset()
        self.diff_threshold = self._base_diff_threshold
        self._no_detect_count = 0

    @property
    def state(self) -> str:
        return self._state.value

    def get_params(self) -> dict:
        """Return current tunable parameters as dict."""
        return {
            "settle_frames": self.settle_frames,
            "diff_threshold": self.diff_threshold,
            "min_diff_area": self.min_diff_area,
            "max_diff_area": self.max_diff_area,
            "min_elongation": self.min_elongation,
            "diagnostics_enabled": self._diagnostics_dir is not None,
            "adaptive_threshold": self.adaptive_threshold,
            "otsu_bias_factor": self.otsu_bias_factor,
            "min_threshold": self.min_threshold,
            "search_mode_frames": self.search_mode_frames,
            "search_mode_threshold_factor": self.search_mode_threshold_factor,
            "no_detect_count": self._no_detect_count,
            "light_unstable": self._light_monitor.is_light_unstable(),
            "light_variance": round(self._light_monitor.get_variance(), 2),
            "sharpness": round(self._sharpness_tracker.sharpness, 1),
            "sharpness_quality": self._sharpness_tracker.get_quality_report().get("quality_label", "unknown"),
            "brightness": round(self._sharpness_tracker.brightness, 1),
            "brightness_label": self._sharpness_tracker.get_quality_report().get("brightness_label", "unknown"),
        }

    def set_params(self, **kwargs) -> dict:
        """Update tunable parameters at runtime. Returns updated params.

        Only provided keys are updated. Validates before applying.
        Raises ValueError on invalid values.
        """
        sf = kwargs.get("settle_frames", self.settle_frames)
        dt = kwargs.get("diff_threshold", self.diff_threshold)
        mina = kwargs.get("min_diff_area", self.min_diff_area)
        maxa = kwargs.get("max_diff_area", self.max_diff_area)
        me = kwargs.get("min_elongation", self.min_elongation)

        # Validate (same rules as __init__)
        if sf < 1:
            raise ValueError("settle_frames must be >= 1")
        if not (0 < dt < 256):
            raise ValueError("diff_threshold must be in 1..255")
        if mina >= maxa:
            raise ValueError("min_diff_area must be < max_diff_area")
        if me < 1.0:
            raise ValueError("min_elongation must be >= 1.0")

        self.settle_frames = sf
        self.diff_threshold = dt
        self.min_diff_area = mina
        self.max_diff_area = maxa
        self.min_elongation = me

        logger.info("CV params updated: %s", self.get_params())
        return self.get_params()

    def toggle_diagnostics(self, path: str | None) -> bool:
        """Enable or disable diagnostics at runtime.

        Returns True if diagnostics are now enabled.
        """
        if path is not None:
            self._diagnostics_dir = Path(path)
            self._diagnostics_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Diagnostics enabled → %s", self._diagnostics_dir)
            return True
        else:
            self._diagnostics_dir = None
            logger.info("Diagnostics disabled")
            return False

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _handle_idle(self, frame: np.ndarray, has_motion: bool) -> DartDetection | None:
        if has_motion:
            # Warmup guard: if baseline was never set (e.g. after reset/seek),
            # force-initialize it from this frame so subsequent diffs work.
            if self._baseline is None:
                self._baseline = frame.copy()
                logger.debug("FrameDiff: Baseline warmup — forced from first frame")
            # Motion detected — freeze baseline (averaged), switch state
            self._state = _State.IN_MOTION
            self._settle_count = 0
            self._had_motion_event = True
            self._stability_centroids = []
            self._baseline_accum.clear()
            logger.debug("FrameDiff: IDLE → IN_MOTION")
        else:
            # No motion — accumulate frames for averaged baseline
            self._baseline_accum.append(frame.copy())
            if len(self._baseline_accum) > self._baseline_avg_frames:
                self._baseline_accum.pop(0)
            # Compute averaged baseline from accumulated frames
            if len(self._baseline_accum) == 1:
                self._baseline = self._baseline_accum[0]
            else:
                acc = np.mean(self._baseline_accum, axis=0).astype(np.uint8)
                self._baseline = acc
        return None

    def _handle_in_motion(self, frame: np.ndarray, has_motion: bool) -> DartDetection | None:
        if has_motion:
            return None  # Bewegung geht weiter, Baseline eingefroren
        # Bewegung aufgehört → Settling starten (count beginnt bei 1)
        self._state = _State.SETTLING
        self._settle_count = 1
        logger.debug("FrameDiff: IN_MOTION → SETTLING (settle_count=1)")
        # Pre-populate diff cache and stability centroids for this frame
        # so that _quick_centroid's diff is available immediately.
        _centroid = self._quick_centroid(frame)
        if _centroid is not None:
            self._stability_centroids.append(_centroid)
        return None

    def _handle_settling(self, frame: np.ndarray, has_motion: bool) -> DartDetection | None:
        if has_motion:
            # Dart wackelt noch — zurück zu IN_MOTION, Baseline bleibt eingefroren
            self._state = _State.IN_MOTION
            self._settle_count = 0
            logger.debug("FrameDiff: SETTLING → IN_MOTION (motion resumed)")
            return None

        self._settle_count += 1  # count starts at 1 (set in _handle_in_motion) → fires when == settle_frames

        # Track centroid for temporal stability gating
        _centroid = self._quick_centroid(frame)
        if _centroid is not None:
            self._stability_centroids.append(_centroid)

        if self._settle_count < self.settle_frames:
            return None

        # Check temporal stability before confirming
        if not self._is_position_stable():
            logger.debug("FrameDiff: Position not stable yet, extending settling")
            return None

        # Genug stabile Frames — compute diff first
        detection = self._compute_diff(frame)

        # Update search-mode counter
        if detection is not None:
            self._no_detect_count = 0
        else:
            self._no_detect_count += 1

        # If no dart detected but we had a motion event, check for bounce-out:
        # motion was seen (dart flew) but post-frame matches baseline (dart bounced off)
        if detection is None and self._had_motion_event and self._is_bounce_out(frame):
            logger.info("FrameDiff: Bounce-out detected (post-frame ≈ baseline)")
            self._state = _State.IDLE
            self._settle_count = 0
            self._had_motion_event = False
            return DartDetection(
                center=(0, 0), area=0.0, confidence=0.0,
                frame_count=self.settle_frames, bounce_out=True,
            )

        self._state = _State.IDLE
        self._settle_count = 0
        self._had_motion_event = False
        self._stability_centroids = []
        return detection

    # ------------------------------------------------------------------
    # Bounce-out detection
    # ------------------------------------------------------------------

    def _is_bounce_out(self, post_frame: np.ndarray) -> bool:
        """Check if post-frame is nearly identical to baseline (dart bounced off).

        Uses a lower diff threshold (half of normal) to be more sensitive.
        Computes total changed pixel area and compares against
        bounce_diff_threshold * min_diff_area.
        """
        if self._baseline is None:
            return False
        diff = cv2.absdiff(self._baseline, post_frame)
        bounce_thresh = max(self.diff_threshold // 2, 1)
        _, thresh = cv2.threshold(diff, bounce_thresh, 255, cv2.THRESH_BINARY)
        total_changed = cv2.countNonZero(thresh)
        threshold_area = self.bounce_diff_threshold * self.min_diff_area
        logger.debug(
            "FrameDiff bounce check: total_changed=%d, threshold_area=%.1f",
            total_changed, threshold_area,
        )
        return total_changed < threshold_area

    # ------------------------------------------------------------------
    # Temporal stability gating helpers
    # ------------------------------------------------------------------

    def _quick_centroid(self, frame: np.ndarray) -> tuple[int, int] | None:
        """Compute a quick diff centroid against baseline for stability tracking."""
        if self._baseline is None:
            return None
        diff = self._get_diff(frame)
        _, thresh = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        largest = max(contours, key=cv2.contourArea)
        M = cv2.moments(largest)
        if M["m00"] <= 0:
            return None
        return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

    def _is_position_stable(self) -> bool:
        """Check if the last stability_frames centroids are within drift threshold."""
        import math
        n = self.stability_frames
        pts = self._stability_centroids
        if len(pts) < n:
            return True  # Not enough data, allow detection (backward compat)
        recent = pts[-n:]
        for i in range(1, len(recent)):
            drift = math.hypot(
                recent[i][0] - recent[i - 1][0],
                recent[i][1] - recent[i - 1][1],
            )
            if drift > self.stability_max_drift_px:
                return False
        return True

    # ------------------------------------------------------------------
    # P47: Cached diff helpers
    # ------------------------------------------------------------------

    def _get_diff(self, frame: np.ndarray) -> np.ndarray:
        """Return cv2.absdiff(baseline, frame), cached per frame_id.

        Applies optional GaussianBlur before diffing to reduce sensor noise.
        """
        if self._cached_diff is not None and self._cached_diff_frame_id == self._frame_id:
            return self._cached_diff
        bl = self._baseline
        fr = frame
        if self._pre_blur_ksize > 1:
            k = self._pre_blur_ksize
            bl = cv2.GaussianBlur(bl, (k, k), 0)
            fr = cv2.GaussianBlur(fr, (k, k), 0)
        diff = cv2.absdiff(bl, fr)
        self._cached_diff = diff
        self._cached_diff_frame_id = self._frame_id
        return diff

    # ------------------------------------------------------------------
    # Diff-Berechnung (CPU-konservativ: absdiff + threshold + closing)
    # ------------------------------------------------------------------

    def _compute_diff(self, post_frame: np.ndarray) -> DartDetection | None:
        if self._baseline is None:
            logger.warning("FrameDiff: _compute_diff aufgerufen ohne Baseline — übersprungen")
            return None

        if post_frame.ndim != 2 or self._baseline.ndim != 2:
            raise ValueError("FrameDiffDetector requires single-channel (grayscale) frames")

        diff = self._get_diff(post_frame)

        # Adaptive threshold: Otsu-Bias with search mode
        effective_threshold = self.diff_threshold  # fallback
        if self.adaptive_threshold:
            otsu_val, _ = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            biased = otsu_val * self.otsu_bias_factor
            candidate = max(self.min_threshold, int(biased))
            # Use Otsu-based value only if it's sensible (not wildly off)
            if 0 < candidate < 256:
                effective_threshold = candidate
            else:
                effective_threshold = self.diff_threshold
            logger.debug(
                "Adaptive threshold: otsu=%d, biased=%.1f, effective=%d (fallback=%d)",
                int(otsu_val), biased, effective_threshold, self.diff_threshold,
            )

        # Search mode: lower threshold after prolonged silence
        in_search_mode = self._no_detect_count >= self.search_mode_frames
        if in_search_mode:
            effective_threshold = max(
                self.min_threshold,
                int(effective_threshold * self.search_mode_threshold_factor),
            )
            logger.debug(
                "Search mode active (%d frames w/o detection), threshold=%d",
                self._no_detect_count, effective_threshold,
            )

        _, thresh = cv2.threshold(diff, effective_threshold, 255, cv2.THRESH_BINARY)

        # 1) Opening: entfernt dünne Board-Draht-Artefakte aus dem Diff
        # Use sharpness-adaptive kernel: sharper cameras need larger opening
        sharpness = self._sharpness_tracker.sharpness
        if self._sharpness_adjust_enabled and sharpness > 200:
            wire_ksize = compute_wire_filter_kernel_size(sharpness)
            wire_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (wire_ksize, wire_ksize))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, wire_kernel)
        else:
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, self._opening_kernel)
        # 2) Closing: schließt kleine Konturlücken
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, self._closing_kernel)
        # 3) Elongated closing: verbindet Dart-Schaft-Fragmente entlang der Längsachse
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, self._elongated_kernel)

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

        # Elongation filter: darts are elongated, reject roughly circular blobs
        rect = cv2.minAreaRect(largest)
        rect_w, rect_h = rect[1]
        if rect_w > 0 and rect_h > 0:
            aspect = max(rect_w, rect_h) / min(rect_w, rect_h)
            if aspect < self.min_elongation:
                logger.debug("FrameDiff: Blob not elongated enough (aspect=%.1f)", aspect)
                return None

        # Centroid as fallback position
        M = cv2.moments(largest)
        if M["m00"] <= 0:
            return None
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])

        # Tip detection: find the narrow end of the dart contour
        # Pass post_frame for sub-pixel refinement via cornerSubPix
        tip = find_dart_tip(largest, gray_frame=post_frame)
        if tip is not None:
            # Use tip as primary position — this is where the dart touches the board
            dart_x, dart_y = tip
            logger.info("FrameDiff: Dart tip bei (%d, %d), centroid (%d, %d) area=%.0f", dart_x, dart_y, cx, cy, area)
        else:
            # Fallback to centroid if tip detection fails
            dart_x, dart_y = cx, cy
            logger.info("FrameDiff: Tip-Detection fehlgeschlagen, Fallback auf Centroid (%d, %d) area=%.0f", cx, cy, area)

        confidence = compute_dart_confidence(largest, area)
        quality = self._compute_quality(largest, area, tip, (cx, cy))

        # Diagnostics: save diff mask, contour overlay, and metadata
        if self._diagnostics_dir is not None:
            self._save_diagnostics(
                diff=diff, thresh=thresh, contour=largest,
                baseline=self._baseline, post_frame=post_frame,
                centroid=(cx, cy), area=area, confidence=confidence,
                tip=tip,
            )

        return DartDetection(
            center=(dart_x, dart_y), area=area, confidence=confidence,
            frame_count=self.settle_frames, quality=quality, tip=tip,
        )

    # ------------------------------------------------------------------
    # Quality scoring
    # ------------------------------------------------------------------

    def _compute_quality(self, contour: np.ndarray, area: float, tip: tuple[int, int] | None, centroid: tuple[int, int]) -> float:
        """Compute detection quality score (0.0-1.0) from contour characteristics."""
        import math
        score = 0.0

        # Elongation quality: darts are elongated (>2.0 is good)
        rect = cv2.minAreaRect(contour)
        rect_w, rect_h = rect[1]
        if rect_w > 0 and rect_h > 0:
            aspect = max(rect_w, rect_h) / min(rect_w, rect_h)
            if aspect >= 2.0:
                score += 0.3
            elif aspect >= 1.5:
                score += 0.15

        # Area quality: expected range 100-3000 px²
        if 100 <= area <= 3000:
            score += 0.2
        elif 30 <= area <= 5000:
            score += 0.1

        # Tip detection success
        if tip is not None:
            score += 0.3
            # Distance tip to centroid (larger = more dart-like)
            dist = math.hypot(tip[0] - centroid[0], tip[1] - centroid[1])
            if dist > 10:
                score += 0.2
            elif dist > 5:
                score += 0.1

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Diagnostics (P20 data collection)
    # ------------------------------------------------------------------

    def _save_diagnostics(
        self,
        diff: np.ndarray,
        thresh: np.ndarray,
        contour: np.ndarray,
        baseline: np.ndarray,
        post_frame: np.ndarray,
        centroid: tuple[int, int],
        area: float,
        confidence: float,
        tip: tuple[int, int] | None = None,
    ) -> None:
        """Save diff mask, contour overlay, and metadata for analysis."""
        assert self._diagnostics_dir is not None
        ts = time.strftime("%Y%m%d_%H%M%S")
        prefix = self._diagnostics_dir / ts

        try:
            # 1) Raw diff (grayscale intensity differences)
            cv2.imwrite(str(prefix) + "_diff.png", diff)

            # 2) Thresholded binary mask
            cv2.imwrite(str(prefix) + "_thresh.png", thresh)

            # 3) Contour overlay on post-frame (visual reference)
            overlay = cv2.cvtColor(post_frame, cv2.COLOR_GRAY2BGR)
            cv2.drawContours(overlay, [contour], -1, (0, 255, 0), 2)
            cv2.circle(overlay, centroid, 5, (0, 0, 255), -1)  # Red = centroid
            # Draw tip if detected (cyan circle, larger)
            if tip is not None:
                cv2.circle(overlay, tip, 7, (255, 255, 0), 2)  # Cyan ring = tip
                # Line from centroid to tip to visualize the axis
                cv2.line(overlay, centroid, tip, (0, 255, 255), 1)  # Yellow line
            # Draw bounding rect and min area rect
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (255, 255, 0), 1)
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
            box = np.intp(box)
            cv2.drawContours(overlay, [box], 0, (255, 0, 255), 1)
            cv2.imwrite(str(prefix) + "_contour.png", overlay)

            # 4) Baseline frame for comparison
            cv2.imwrite(str(prefix) + "_baseline.png", baseline)

            # 5) Metadata JSON
            rect_center, rect_size, rect_angle = rect
            meta = {
                "timestamp": ts,
                "centroid": list(centroid),
                "tip": list(tip) if tip is not None else None,
                "tip_detected": tip is not None,
                "area": round(area, 1),
                "confidence": round(confidence, 3),
                "bounding_rect": {"x": x, "y": y, "w": w, "h": h},
                "min_area_rect": {
                    "center": [round(rect_center[0], 1), round(rect_center[1], 1)],
                    "size": [round(rect_size[0], 1), round(rect_size[1], 1)],
                    "angle": round(rect_angle, 1),
                },
                "contour_points": len(contour),
                "camera_quality": self._sharpness_tracker.get_quality_report(),
                "settings": {
                    "settle_frames": self.settle_frames,
                    "diff_threshold": self.diff_threshold,
                    "min_diff_area": self.min_diff_area,
                    "max_diff_area": self.max_diff_area,
                },
            }
            with open(str(prefix) + "_meta.json", "w") as f:
                json.dump(meta, f, indent=2)

            logger.info("Diagnostics saved: %s_*.png/json", prefix)
        except Exception as e:
            logger.warning("Failed to save diagnostics: %s", e)
