"""MOG2-based motion detection with configurable threshold."""

import cv2
import numpy as np


class MotionDetector:
    """MOG2-based motion detection with configurable threshold."""

    def __init__(self, threshold: int = 500, detect_shadows: bool = False,
                 var_threshold: int = 50,
                 learning_rate: float = 0.002,
                 downscale_factor: int = 1) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be > 0")
        if var_threshold <= 0:
            raise ValueError("var_threshold must be > 0")
        if not 0.0 < learning_rate <= 1.0:
            raise ValueError("learning_rate must be in (0, 1]")
        if downscale_factor < 1:
            raise ValueError("downscale_factor must be >= 1")
        self.threshold = threshold
        self._detect_shadows = detect_shadows
        self._var_threshold = var_threshold
        self._learning_rate = learning_rate
        self._downscale_factor = downscale_factor
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=detect_shadows,
            varThreshold=var_threshold
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, bool]:
        """Returns (cleaned_motion_mask, motion_detected_flag).

        When downscale_factor > 1, the frame is downscaled before MOG2
        processing and the mask is upscaled back to original size.
        This saves ~75% CPU in idle at factor=4.
        """
        orig_h, orig_w = frame.shape[:2]
        ds = self._downscale_factor

        if ds > 1:
            small = cv2.resize(
                frame,
                (max(orig_w // ds, 1), max(orig_h // ds, 1)),
                interpolation=cv2.INTER_AREA,
            )
            fg_mask_small = self.bg_subtractor.apply(small, learningRate=self._learning_rate)
            fg_mask_small = cv2.threshold(fg_mask_small, 200, 255, cv2.THRESH_BINARY)[1]
            fg_mask_small = cv2.morphologyEx(fg_mask_small, cv2.MORPH_OPEN, self._kernel)
            fg_mask_small = cv2.morphologyEx(fg_mask_small, cv2.MORPH_CLOSE, self._kernel)
            # Check motion on small mask (threshold scaled by area ratio)
            motion_pixels = cv2.countNonZero(fg_mask_small)
            scale_ratio = ds * ds
            has_motion = motion_pixels * scale_ratio > self.threshold
            # Upscale mask to original size
            fg_mask = cv2.resize(fg_mask_small, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
            return fg_mask, has_motion

        fg_mask = self.bg_subtractor.apply(frame, learningRate=self._learning_rate)
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
            detectShadows=self._detect_shadows,
            varThreshold=self._var_threshold,
        )
