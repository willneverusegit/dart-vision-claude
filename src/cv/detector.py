"""Detects dart impacts using shape analysis and temporal confirmation."""

import cv2
import numpy as np
import math
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DartDetection:
    """Represents a confirmed dart detection."""
    center: tuple[int, int]     # (x, y) in ROI coordinates
    area: float                 # Contour area in pixels
    confidence: float           # 0.0-1.0
    frame_count: int            # Number of confirmation frames
    tip: tuple[int, int] | None = None  # Dart tip position (x, y), None if detection failed


class DartImpactDetector:
    """Detects dart impacts using shape analysis and temporal confirmation."""

    def __init__(self, confirmation_frames: int = 3,
                 position_tolerance_px: int = 20,
                 area_min: int = 10, area_max: int = 1000,
                 aspect_ratio_range: tuple[float, float] = (0.3, 3.0),
                 max_candidates: int = 50) -> None:
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

        self.confirmation_frames = confirmation_frames
        self.position_tolerance_px = position_tolerance_px
        self.area_min = area_min
        self.area_max = area_max
        self.aspect_ratio_range = aspect_ratio_range
        self.max_candidates = max_candidates

        # Temporal state
        self._candidates: list[dict] = []
        self._confirmed: list[DartDetection] = []

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
        """Find contours matching dart shape criteria."""
        contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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
        """Check if a detection is too close to an already confirmed dart."""
        for confirmed in self._confirmed:
            dist = math.hypot(
                detection.center[0] - confirmed.center[0],
                detection.center[1] - confirmed.center[1]
            )
            if dist < self.position_tolerance_px:
                return True
        return False

    def _decay_candidates(self) -> None:
        """Remove stale candidates that weren't seen this frame."""
        self._candidates = [c for c in self._candidates if c["count"] > 1]
        for c in self._candidates:
            c["count"] -= 1

    def reset(self) -> None:
        """Reset temporal state (e.g., after dart removal)."""
        self._candidates.clear()
        self._confirmed.clear()

    def get_all_confirmed(self) -> list[DartDetection]:
        """Return all currently confirmed dart positions (up to 3 per turn)."""
        return list(self._confirmed)

    def register_confirmed(self, detection: "DartDetection") -> bool:
        """Add an externally confirmed detection.

        Returns True if added, False if position already known (deduplication).
        """
        if self._is_already_confirmed(detection):
            return False
        self._confirmed.append(detection)
        return True
