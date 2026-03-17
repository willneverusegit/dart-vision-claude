"""MOG2-based motion detection with configurable threshold."""

import cv2
import numpy as np


class MotionDetector:
    """MOG2-based motion detection with configurable threshold."""

    def __init__(self, threshold: int = 500, detect_shadows: bool = True,
                 var_threshold: int = 50) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be > 0")
        if var_threshold <= 0:
            raise ValueError("var_threshold must be > 0")
        self.threshold = threshold
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=detect_shadows,
            varThreshold=var_threshold
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, bool]:
        """Returns (cleaned_motion_mask, motion_detected_flag)."""
        fg_mask = self.bg_subtractor.apply(frame)
        # Remove shadow pixels (MOG2 marks shadows as 127)
        fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)[1]
        # Morphological cleanup
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self._kernel)

        motion_pixels = cv2.countNonZero(fg_mask)
        return fg_mask, motion_pixels > self.threshold

    def get_params(self) -> dict:
        """Return current tunable parameters."""
        return {"motion_threshold": self.threshold}

    def set_threshold(self, value: int) -> None:
        """Update motion threshold at runtime."""
        if value <= 0:
            raise ValueError("threshold must be > 0")
        self.threshold = value

    def reset(self) -> None:
        """Reset background model (e.g., after calibration change)."""
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True, varThreshold=50
        )
