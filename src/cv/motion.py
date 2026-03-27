"""MOG2-based motion detection with frame-diff fallback for short videos."""

import cv2
import numpy as np
from collections import deque


class MotionDetector:
    """MOG2-based motion detection with frame-diff fallback.

    The frame-diff fallback detects motion by comparing consecutive frames,
    which works even when MOG2's background model hasn't stabilized (e.g.
    short video clips with subtle dart motion).
    """

    def __init__(self, threshold: int = 500, detect_shadows: bool = False,
                 var_threshold: int = 50,
                 learning_rate: float = 0.002,
                 downscale_factor: int = 1,
                 framediff_fallback: bool = True,
                 framediff_threshold: int = 25,
                 temporal_median_frames: int = 3) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be > 0")
        if var_threshold <= 0:
            raise ValueError("var_threshold must be > 0")
        if not 0.0 < learning_rate <= 1.0:
            raise ValueError("learning_rate must be in (0, 1]")
        if downscale_factor < 1:
            raise ValueError("downscale_factor must be >= 1")
        if temporal_median_frames < 1:
            raise ValueError("temporal_median_frames must be >= 1")
        self.threshold = threshold
        self._temporal_median_frames = temporal_median_frames
        self._mask_history: deque[np.ndarray] = deque(maxlen=temporal_median_frames)
        self._detect_shadows = detect_shadows
        self._var_threshold = var_threshold
        self._learning_rate = learning_rate
        self._downscale_factor = downscale_factor
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=detect_shadows,
            varThreshold=var_threshold
        )
        # Use smaller kernel when downscaling — 3x3 on a 100x100 image
        # removes too many subtle motion pixels (P59 fix)
        ksize = (2, 2) if downscale_factor >= 4 else (3, 3)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, ksize)

        # Frame-diff fallback: compare consecutive frames directly
        self._framediff_fallback = framediff_fallback
        self._framediff_threshold = framediff_threshold
        self._prev_frame: np.ndarray | None = None

    def _adaptive_threshold(self) -> int:
        """Return motion pixel threshold scaled for downscale_factor.

        When downscaling by factor N, the image has N^2 fewer pixels,
        so motion blobs shrink proportionally. We scale the threshold
        down to compensate, ensuring subtle motion is still detected.
        """
        ds = self._downscale_factor
        if ds <= 1:
            return self.threshold
        # The caller already multiplies motion_pixels by ds*ds,
        # so the effective threshold is self.threshold.
        # But we return the raw threshold here — scaling happens at comparison.
        return self.threshold

    def _framediff_detect(self, frame: np.ndarray) -> bool:
        """Detect motion via frame-to-frame absolute difference.

        Works independently of MOG2's background model — useful for
        short clips where MOG2 hasn't stabilized.
        """
        if not self._framediff_fallback:
            return False

        # Work on downscaled frame for consistency
        ds = self._downscale_factor
        if ds > 1:
            h, w = frame.shape[:2]
            small = cv2.resize(
                frame,
                (max(w // ds, 1), max(h // ds, 1)),
                interpolation=cv2.INTER_AREA,
            )
        else:
            small = frame

        # Convert to grayscale if needed
        if small.ndim == 3:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        else:
            gray = small

        if self._prev_frame is None:
            self._prev_frame = gray.copy()
            return False

        diff = cv2.absdiff(self._prev_frame, gray)
        self._prev_frame = gray.copy()

        _, thresh = cv2.threshold(diff, self._framediff_threshold, 255, cv2.THRESH_BINARY)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, self._kernel)
        motion_pixels = cv2.countNonZero(thresh)

        # Scale comparison: same logic as MOG2 path
        if ds > 1:
            return motion_pixels * (ds * ds) > self.threshold
        return motion_pixels > self.threshold

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, bool]:
        """Returns (cleaned_motion_mask, motion_detected_flag).

        When downscale_factor > 1, the frame is downscaled before MOG2
        processing and the mask is upscaled back to original size.
        This saves ~75% CPU in idle at factor=4.

        Frame-diff fallback is OR'd with MOG2 result to catch motion
        that MOG2 misses during background model warmup.
        """
        orig_h, orig_w = frame.shape[:2]
        ds = self._downscale_factor

        # Frame-diff fallback (evaluated regardless of MOG2 result)
        framediff_motion = self._framediff_detect(frame)

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
            # Temporal median: suppress 1-2 frame vibration spikes
            fg_mask_small = self._apply_temporal_median(fg_mask_small)
            # Check motion on small mask (threshold scaled by area ratio)
            motion_pixels = cv2.countNonZero(fg_mask_small)
            scale_ratio = ds * ds
            mog2_motion = motion_pixels * scale_ratio > self.threshold
            # Upscale mask to original size
            fg_mask = cv2.resize(fg_mask_small, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
            return fg_mask, mog2_motion or framediff_motion

        fg_mask = self.bg_subtractor.apply(frame, learningRate=self._learning_rate)
        # Remove shadow pixels (MOG2 marks shadows as 127)
        fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)[1]
        # Morphological cleanup
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self._kernel)
        # Temporal median: suppress 1-2 frame vibration spikes
        fg_mask = self._apply_temporal_median(fg_mask)

        motion_pixels = cv2.countNonZero(fg_mask)
        mog2_motion = motion_pixels > self.threshold
        return fg_mask, mog2_motion or framediff_motion

    def _apply_temporal_median(self, mask: np.ndarray) -> np.ndarray:
        """Apply temporal median filter over recent masks to suppress vibration spikes.

        A pixel is only considered motion if it appears in the majority of
        recent frames. Single-frame spikes from tripod vibration are filtered out.
        """
        if self._temporal_median_frames <= 1:
            return mask
        self._mask_history.append(mask)
        if len(self._mask_history) < self._temporal_median_frames:
            return mask
        stacked = np.stack(self._mask_history, axis=0)
        median = np.median(stacked, axis=0).astype(np.uint8)
        return median

    def get_params(self) -> dict:
        """Return current tunable parameters."""
        return {
            "motion_threshold": self.threshold,
            "framediff_fallback": self._framediff_fallback,
            "framediff_threshold": self._framediff_threshold,
        }

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
        self._prev_frame = None
        self._mask_history.clear()
