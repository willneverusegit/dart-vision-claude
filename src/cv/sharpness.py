"""Camera image sharpness metrics and quality compensation.

Provides Laplacian-variance-based sharpness measurement and per-camera
threshold adjustment to compensate for different image quality between cameras.
"""

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


def compute_brightness(frame: np.ndarray) -> float:
    """Compute mean brightness (intensity) of a frame.

    Args:
        frame: Grayscale (2D) or BGR (3D) image.

    Returns:
        Mean pixel intensity as float (0.0-255.0).
    """
    if frame is None or frame.size == 0:
        return 0.0
    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    return float(gray.mean())


def compute_sharpness(frame: np.ndarray) -> float:
    """Compute sharpness metric using Laplacian variance.

    Higher values indicate sharper images. Typical ranges:
    - Blurry/out-of-focus: < 50
    - Normal webcam: 50-300
    - Sharp/high-quality: > 300

    Args:
        frame: Grayscale (2D) or BGR (3D) image.

    Returns:
        Laplacian variance as float (>= 0.0).
    """
    if frame is None or frame.size == 0:
        return 0.0
    if frame.ndim == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())


def adjusted_diff_threshold(
    base_threshold: int,
    sharpness: float,
    reference_sharpness: float = 150.0,
    min_threshold: int = 15,
    max_threshold: int = 80,
    scale_factor: float = 0.5,
) -> int:
    """Compute a sharpness-adjusted diff threshold.

    Sharper cameras produce stronger edges and more visible board wires in
    diffs, so they benefit from a *higher* threshold to suppress wire artifacts.
    Blurry cameras need a *lower* threshold to catch subtle dart silhouettes.

    The adjustment is: threshold * (1 + scale_factor * log2(sharpness / reference))
    clamped to [min_threshold, max_threshold].

    Args:
        base_threshold: The configured diff_threshold (e.g. 30).
        sharpness: Current Laplacian variance of the camera.
        reference_sharpness: Expected "normal" sharpness level.
        min_threshold: Floor for the adjusted threshold.
        max_threshold: Ceiling for the adjusted threshold.
        scale_factor: How aggressively to scale with sharpness ratio.

    Returns:
        Adjusted threshold as int.
    """
    if sharpness <= 0 or reference_sharpness <= 0:
        return base_threshold

    import math
    ratio = sharpness / reference_sharpness
    # log2 scaling: double sharpness → +scale_factor * base_threshold
    adjustment = 1.0 + scale_factor * math.log2(ratio)
    adjusted = int(base_threshold * adjustment)
    return max(min_threshold, min(adjusted, max_threshold))


def compute_wire_filter_kernel_size(sharpness: float, base_size: int = 2) -> int:
    """Compute morphological opening kernel size for wire artifact removal.

    Sharper cameras show thinner board wires more prominently in diffs.
    Returns a larger kernel for sharper images to suppress these artifacts.

    Args:
        sharpness: Laplacian variance of the camera.
        base_size: Minimum kernel size (for normal/blurry cameras).

    Returns:
        Odd kernel size >= base_size.
    """
    if sharpness > 400:
        size = base_size + 2  # Very sharp: aggressive wire removal
    elif sharpness > 200:
        size = base_size + 1  # Moderately sharp
    else:
        size = base_size      # Normal/blurry: minimal filtering

    # Ensure odd kernel size for morphology
    if size % 2 == 0:
        size += 1
    return max(3, size)


def adjusted_clahe_clip_limit(
    brightness: float,
    base_clip: float = 2.0,
    min_clip: float = 1.0,
    max_clip: float = 4.0,
    reference_brightness: float = 128.0,
) -> float:
    """Compute brightness-adjusted CLAHE clipLimit.

    Brighter images need lower clipLimit (less contrast enhancement),
    darker images need higher clipLimit (more enhancement).

    Args:
        brightness: Current mean brightness (0-255).
        base_clip: Default CLAHE clipLimit.
        min_clip: Floor for clipLimit.
        max_clip: Ceiling for clipLimit.
        reference_brightness: Expected "normal" brightness.

    Returns:
        Adjusted clipLimit as float.
    """
    if brightness <= 0 or reference_brightness <= 0:
        return base_clip
    ratio = reference_brightness / brightness  # darker → ratio > 1 → higher clip
    adjusted = base_clip * ratio
    return max(min_clip, min(adjusted, max_clip))


class SharpnessTracker:
    """Tracks per-camera sharpness over a rolling window.

    Call update() with each frame to maintain a running sharpness estimate.
    Uses exponential moving average for CPU efficiency.
    """

    def __init__(self, ema_alpha: float = 0.1, sample_interval: int = 10):
        """
        Args:
            ema_alpha: Smoothing factor for exponential moving average (0-1).
                Smaller = smoother, larger = more responsive.
            sample_interval: Only compute sharpness every N frames (CPU savings).
        """
        self._ema_alpha = ema_alpha
        self._sample_interval = max(1, sample_interval)
        self._sharpness: float = 0.0
        self._brightness: float = 0.0
        self._frame_count: int = 0
        self._initialized: bool = False
        self._brightness_initialized: bool = False

    def update(self, frame: np.ndarray) -> None:
        """Update sharpness estimate with a new frame.

        Only computes Laplacian every sample_interval frames.
        """
        self._frame_count += 1
        if self._frame_count % self._sample_interval != 0:
            return

        val = compute_sharpness(frame)
        bri = compute_brightness(frame)
        if not self._initialized:
            self._sharpness = val
            self._initialized = True
        else:
            self._sharpness = (1 - self._ema_alpha) * self._sharpness + self._ema_alpha * val
        if not self._brightness_initialized:
            self._brightness = bri
            self._brightness_initialized = True
        else:
            self._brightness = (1 - self._ema_alpha) * self._brightness + self._ema_alpha * bri

    @property
    def sharpness(self) -> float:
        """Current smoothed sharpness estimate."""
        return self._sharpness

    @property
    def brightness(self) -> float:
        """Current smoothed brightness estimate (0-255)."""
        return self._brightness

    @property
    def is_sharp(self) -> bool:
        """True if camera produces notably sharp images (likely shows wire artifacts)."""
        return self._sharpness > 300.0

    def get_quality_report(self) -> dict:
        """Return quality metrics for diagnostics."""
        if self._sharpness > 300:
            label = "sharp"
        elif self._sharpness > 100:
            label = "normal"
        elif self._sharpness > 30:
            label = "soft"
        else:
            label = "blurry"

        if self._brightness > 180:
            brightness_label = "bright"
        elif self._brightness > 80:
            brightness_label = "normal"
        elif self._brightness > 30:
            brightness_label = "dark"
        else:
            brightness_label = "very_dark"

        return {
            "sharpness": round(self._sharpness, 1),
            "brightness": round(self._brightness, 1),
            "quality_label": label,
            "brightness_label": brightness_label,
            "is_sharp": self.is_sharp,
            "frames_sampled": self._frame_count // self._sample_interval,
        }
