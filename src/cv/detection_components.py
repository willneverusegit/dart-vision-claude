"""Modular detection pipeline components (P43).

Standalone, testable classes extracted from detector.py and diff_detector.py.
Each component has a uniform process/check interface.
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ShapeAnalyzer:
    """Analyzes contours for dart-like shape characteristics.

    Filters contours by area and aspect ratio, computes centroids.
    Extracted from DartImpactDetector._find_dart_shapes.
    """

    def __init__(
        self,
        area_min: int = 10,
        area_max: int = 1000,
        aspect_ratio_range: tuple[float, float] = (0.3, 3.0),
    ) -> None:
        if area_min < 0:
            raise ValueError("area_min must be >= 0")
        if area_min >= area_max:
            raise ValueError("area_min must be less than area_max")
        if aspect_ratio_range[0] <= 0 or aspect_ratio_range[1] <= 0:
            raise ValueError("aspect_ratio_range values must be > 0")
        if aspect_ratio_range[0] >= aspect_ratio_range[1]:
            raise ValueError("aspect_ratio_range[0] must be < aspect_ratio_range[1]")

        self.area_min = area_min
        self.area_max = area_max
        self.aspect_ratio_range = aspect_ratio_range

    def find_dart_shapes(self, mask: np.ndarray) -> list[dict]:
        """Find contours matching dart shape criteria.

        Returns list of dicts with 'center' (x,y) and 'area', sorted by area descending.
        """
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if not (self.area_min <= area <= self.area_max):
                continue

            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                continue
            aspect_ratio = float(w) / h

            if not (self.aspect_ratio_range[0] < aspect_ratio < self.aspect_ratio_range[1]):
                continue

            M = cv2.moments(contour)
            if M["m00"] <= 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            candidates.append({"center": (cx, cy), "area": area})

        candidates.sort(key=lambda d: d["area"], reverse=True)
        return candidates


class CooldownManager:
    """Manages post-detection cooldown to prevent duplicate detections.

    Extracted from DartImpactDetector cooldown logic.
    """

    def __init__(self, cooldown_frames: int = 30) -> None:
        if cooldown_frames < 0:
            raise ValueError("cooldown_frames must be >= 0")
        self.cooldown_frames = cooldown_frames
        self._counter: int = 0

    @property
    def active(self) -> bool:
        """True if currently in cooldown period."""
        return self._counter > 0

    @property
    def remaining(self) -> int:
        """Number of cooldown frames remaining."""
        return self._counter

    def activate(self) -> None:
        """Start a new cooldown period."""
        self._counter = self.cooldown_frames

    def tick(self) -> None:
        """Advance cooldown by one frame."""
        if self._counter > 0:
            self._counter -= 1

    def reset(self) -> None:
        """Reset cooldown to inactive."""
        self._counter = 0


class MotionFilter:
    """Filters and tracks motion events for the detection state machine.

    Tracks consecutive no-motion frames and provides idle detection.
    Extracted from DartPipeline motion tracking logic.
    """

    def __init__(
        self,
        idle_threshold: int = 10,
        scoring_lock_frames: int = 15,
    ) -> None:
        if idle_threshold < 0:
            raise ValueError("idle_threshold must be >= 0")
        if scoring_lock_frames < 0:
            raise ValueError("scoring_lock_frames must be >= 0")

        self.idle_threshold = idle_threshold
        self.scoring_lock_frames = scoring_lock_frames
        self._no_motion_count: int = 0
        self._scoring_lock_counter: int = 0

    @property
    def is_idle(self) -> bool:
        """True if no motion detected for idle_threshold consecutive frames."""
        return self._no_motion_count >= self.idle_threshold

    @property
    def is_locked(self) -> bool:
        """True if scoring lock is active (suppressing motion)."""
        return self._scoring_lock_counter > 0

    def update(self, has_motion: bool) -> bool:
        """Process a motion flag. Returns effective has_motion after lock filtering."""
        # Track consecutive no-motion frames
        if has_motion:
            self._no_motion_count = 0
        else:
            self._no_motion_count += 1

        # Scoring lock suppresses motion
        if self._scoring_lock_counter > 0:
            self._scoring_lock_counter -= 1
            return False

        return has_motion

    def activate_lock(self) -> None:
        """Activate scoring lock after a confirmed detection."""
        self._scoring_lock_counter = self.scoring_lock_frames

    def reset(self) -> None:
        """Reset all state."""
        self._no_motion_count = 0
        self._scoring_lock_counter = 0
