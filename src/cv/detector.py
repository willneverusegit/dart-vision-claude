"""Detects dart impacts using shape analysis and temporal confirmation."""

import cv2
import numpy as np
import math
import logging
from dataclasses import dataclass

from src.cv.detection_components import ShapeAnalyzer, CooldownManager

logger = logging.getLogger(__name__)


def compute_dart_confidence(contour: np.ndarray, area: float) -> float:
    """Weighted confidence score from contour shape metrics.

    Combines aspect ratio, solidity, and area into a 0.0-1.0 score.
    Tuned for typical dart contour characteristics.
    """
    # --- Aspect score (minAreaRect aspect ratio) ---
    rect = cv2.minAreaRect(contour)
    rect_w, rect_h = rect[1]
    if rect_w > 0 and rect_h > 0:
        ratio = max(rect_w, rect_h) / min(rect_w, rect_h)
    else:
        ratio = 1.0

    # Ideal range [3, 8] for darts
    if 3.0 <= ratio <= 8.0:
        aspect_score = 1.0
    elif ratio < 3.0:
        aspect_score = max(0.0, ratio / 3.0)
    else:
        # ratio > 8: decay from 1.0 towards 0 over range 8-16
        aspect_score = max(0.0, 1.0 - (ratio - 8.0) / 8.0)

    # --- Solidity score (contourArea / convexHullArea) ---
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    solidity = (area / hull_area) if hull_area > 0 else 0.0

    if solidity >= 0.7:
        solidity_score = 1.0
    elif solidity >= 0.4:
        solidity_score = (solidity - 0.4) / 0.3
    else:
        solidity_score = 0.0

    # --- Area score ---
    if 80.0 <= area <= 2500.0:
        area_score = 1.0
    elif area < 80.0:
        area_score = max(0.0, area / 80.0)
    else:
        # area > 2500: decay towards 0 over range 2500-6000
        area_score = max(0.0, 1.0 - (area - 2500.0) / 3500.0)

    confidence = 0.4 * aspect_score + 0.3 * solidity_score + 0.3 * area_score
    return min(max(confidence, 0.0), 1.0)


@dataclass
class DartDetection:
    """Represents a confirmed dart detection."""
    center: tuple[int, int]     # (x, y) in ROI coordinates
    area: float                 # Contour area in pixels
    confidence: float           # 0.0-1.0
    frame_count: int            # Number of confirmation frames
    quality: float = 0.0                # Detection quality score 0.0-1.0
    tip: tuple[int, int] | None = None  # Dart tip position (x, y), None if detection failed
    bounce_out: bool = False            # True if dart bounced off board (no stick)
    raw_center: tuple[float, float] | None = None  # (x, y) in original camera frame coords
    raw_tip: tuple[float, float] | None = None     # tip in original camera frame coords


class DartImpactDetector:
    """Detects dart impacts using shape analysis and temporal confirmation."""

    def __init__(self, confirmation_frames: int = 3,
                 position_tolerance_px: int = 20,
                 area_min: int = 10, area_max: int = 2000,
                 aspect_ratio_range: tuple[float, float] = (0.3, 3.0),
                 max_candidates: int = 50,
                 exclusion_zone_px: int = 50,
                 cooldown_frames: int = 30) -> None:
        if area_min < 0:
            raise ValueError("area_min must be >= 0")
        if area_min >= area_max:
            raise ValueError("area_min must be less than area_max")
        if confirmation_frames < 1:
            raise ValueError("confirmation_frames must be >= 1")
        if position_tolerance_px <= 0:
            raise ValueError("position_tolerance_px must be > 0")
        if aspect_ratio_range[0] <= 0 or aspect_ratio_range[1] <= 0:
            raise ValueError("aspect_ratio_range values must be > 0")
        if aspect_ratio_range[0] >= aspect_ratio_range[1]:
            raise ValueError("aspect_ratio_range[0] must be less than aspect_ratio_range[1]")
        if exclusion_zone_px < 0:
            raise ValueError("exclusion_zone_px must be >= 0")
        if cooldown_frames < 0:
            raise ValueError("cooldown_frames must be >= 0")

        self.confirmation_frames = confirmation_frames
        self.position_tolerance_px = position_tolerance_px
        self.area_min = area_min
        self.area_max = area_max
        self.aspect_ratio_range = aspect_ratio_range
        self.max_candidates = max_candidates
        self.exclusion_zone_px = exclusion_zone_px
        self.cooldown_frames = cooldown_frames

        self._base_area_max = area_max

        # Modular components (P43)
        self._shape_analyzer = ShapeAnalyzer(
            area_min=area_min, area_max=area_max,
            aspect_ratio_range=aspect_ratio_range,
        )
        self._cooldown = CooldownManager(cooldown_frames=cooldown_frames,
                                         exclusion_zone_px=exclusion_zone_px)

        # Temporal state
        self._candidates: list[dict] = []
        self._confirmed: list[DartDetection] = []

    def scale_area_to_roi(self, roi_width: int, roi_height: int,
                          reference_size: int = 400) -> None:
        """Scale area_min/area_max based on ROI size relative to a reference.

        Larger ROIs produce larger contours, so we scale proportionally
        by the ratio of ROI area to reference area (default 400x400).
        """
        roi_area = roi_width * roi_height
        ref_area = reference_size * reference_size
        scale = roi_area / ref_area
        self.area_min = max(1, int(self.area_min * scale))
        self.area_max = max(self.area_min + 1, int(self._base_area_max * scale))
        # Update shape analyzer too
        self._shape_analyzer.area_min = self.area_min
        self._shape_analyzer.area_max = self.area_max
        logger.debug("Area range scaled to [%d, %d] for ROI %dx%d (scale=%.2f)",
                     self.area_min, self.area_max, roi_width, roi_height, scale)

    def detect(self, roi_frame: np.ndarray, motion_mask: np.ndarray) -> DartDetection | None:
        """Analyze motion mask for dart-shaped objects. Returns confirmed detection or None.

        Note: Not called by the single-camera pipeline since P19 (which uses FrameDiffDetector).
        Kept for multi-camera paths and direct testing.
        """
        shapes = self._find_dart_shapes(motion_mask)
        if not shapes:
            self._decay_candidates()
            return None

        best = shapes[0]
        matched = self._match_candidate(best)

        if matched is not None:
            matched["count"] += 1
            matched["center"] = best["center"]
            matched["area"] = best["area"]

            if matched["count"] >= self.confirmation_frames:
                detection = DartDetection(
                    center=matched["center"],
                    area=matched["area"],
                    confidence=min(matched["area"] / 200.0, 1.0),
                    frame_count=matched["count"]
                )
                if not self._is_already_confirmed(detection):
                    self._confirmed.append(detection)
                    self._cooldown.activate(position=detection.center)
                    logger.info("Dart confirmed at %s (area=%.0f, frames=%d)",
                                detection.center, detection.area, detection.frame_count)
                    return detection
        else:
            self._candidates.append({
                "center": best["center"],
                "area": best["area"],
                "count": 1
            })
            # Enforce max_candidates limit by removing oldest entries
            while len(self._candidates) > self.max_candidates:
                self._candidates.pop(0)

        return None

    def _find_dart_shapes(self, motion_mask: np.ndarray) -> list[dict]:
        """Find contours matching dart shape criteria. Delegates to ShapeAnalyzer."""
        return self._shape_analyzer.find_dart_shapes(motion_mask)

    def _match_candidate(self, shape: dict) -> dict | None:
        """Find an existing candidate near the given shape."""
        for candidate in self._candidates:
            dist = math.hypot(
                shape["center"][0] - candidate["center"][0],
                shape["center"][1] - candidate["center"][1]
            )
            if dist < self.position_tolerance_px:
                return candidate
        return None

    def _is_already_confirmed(self, detection: DartDetection) -> bool:
        """Check if a detection is too close to an already confirmed dart (exclusion zone).

        Delegates to CooldownManager.is_in_exclusion_zone() which maintains
        the spatial exclusion zones (P51 deduplication consolidation).
        """
        return self._cooldown.is_in_exclusion_zone(
            detection.center[0], detection.center[1]
        )

    def _decay_candidates(self) -> None:
        """Remove stale candidates that weren't seen this frame."""
        self._candidates = [c for c in self._candidates if c["count"] > 1]
        for c in self._candidates:
            c["count"] -= 1

    def reset(self) -> None:
        """Reset temporal state (e.g., after dart removal)."""
        self._candidates.clear()
        self._confirmed.clear()
        self._cooldown.reset()

    def get_all_confirmed(self) -> list[DartDetection]:
        """Return all currently confirmed dart positions (up to 3 per turn)."""
        return list(self._confirmed)

    def is_in_cooldown(self) -> bool:
        """Return True if the detector is in post-confirmation cooldown."""
        return self._cooldown.active

    def tick(self) -> None:
        """Advance cooldown counter by one frame. Call once per frame."""
        self._cooldown.tick()

    def register_confirmed(self, detection: "DartDetection") -> bool:
        """Add an externally confirmed detection.

        Returns True if added, False if position already known (deduplication)
        or if detector is in cooldown.
        """
        if self._cooldown.active:
            logger.debug("register_confirmed rejected: cooldown active (%d frames left)",
                         self._cooldown.remaining)
            return False
        if self._is_already_confirmed(detection):
            return False
        self._confirmed.append(detection)
        self._cooldown.activate(position=detection.center)
        logger.debug("Cooldown activated for %d frames at %s", self.cooldown_frames, detection.center)
        return True
