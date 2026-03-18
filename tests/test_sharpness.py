"""Tests for camera sharpness metrics and quality compensation (P26)."""

import numpy as np
import pytest

from src.cv.sharpness import (
    compute_sharpness,
    adjusted_diff_threshold,
    compute_wire_filter_kernel_size,
    SharpnessTracker,
)


class TestComputeSharpness:
    def test_uniform_image_zero_sharpness(self):
        """A uniform gray image has zero Laplacian variance."""
        img = np.full((100, 100), 128, dtype=np.uint8)
        assert compute_sharpness(img) == 0.0

    def test_noisy_image_has_sharpness(self):
        """A noisy image has non-zero sharpness."""
        rng = np.random.RandomState(42)
        img = rng.randint(0, 256, (100, 100), dtype=np.uint8)
        assert compute_sharpness(img) > 0

    def test_sharp_edges_high_sharpness(self):
        """An image with strong edges has high sharpness."""
        img = np.zeros((100, 100), dtype=np.uint8)
        img[40:60, :] = 255  # horizontal stripe
        val = compute_sharpness(img)
        assert val > 50  # Clear edges produce high Laplacian variance

    def test_bgr_input(self):
        """Accepts 3-channel BGR input."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[40:60, :] = 255
        val = compute_sharpness(img)
        assert val > 0

    def test_empty_image(self):
        img = np.array([], dtype=np.uint8)
        assert compute_sharpness(img) == 0.0

    def test_none_input(self):
        assert compute_sharpness(None) == 0.0


class TestAdjustedDiffThreshold:
    def test_reference_sharpness_no_change(self):
        """At reference sharpness, threshold should equal base."""
        result = adjusted_diff_threshold(30, 150.0, reference_sharpness=150.0)
        assert result == 30

    def test_sharp_camera_higher_threshold(self):
        """Sharper camera should produce higher threshold."""
        result = adjusted_diff_threshold(30, 600.0, reference_sharpness=150.0)
        assert result > 30

    def test_blurry_camera_lower_threshold(self):
        """Blurry camera should produce lower threshold."""
        result = adjusted_diff_threshold(30, 50.0, reference_sharpness=150.0)
        assert result < 30

    def test_clamped_to_min(self):
        """Result should not go below min_threshold."""
        result = adjusted_diff_threshold(30, 1.0, reference_sharpness=150.0, min_threshold=15)
        assert result >= 15

    def test_clamped_to_max(self):
        """Result should not exceed max_threshold."""
        result = adjusted_diff_threshold(30, 100000.0, reference_sharpness=150.0, max_threshold=80)
        assert result <= 80

    def test_zero_sharpness_returns_base(self):
        assert adjusted_diff_threshold(30, 0.0) == 30

    def test_zero_reference_returns_base(self):
        assert adjusted_diff_threshold(30, 150.0, reference_sharpness=0.0) == 30


class TestWireFilterKernelSize:
    def test_normal_camera_base_size(self):
        """Normal sharpness gets minimal kernel."""
        size = compute_wire_filter_kernel_size(100.0, base_size=2)
        assert size == 3  # base_size=2, but minimum odd is 3

    def test_sharp_camera_larger_kernel(self):
        size = compute_wire_filter_kernel_size(350.0, base_size=2)
        assert size >= 3  # base+1=3, guaranteed odd

    def test_very_sharp_camera_largest_kernel(self):
        size = compute_wire_filter_kernel_size(500.0, base_size=2)
        assert size >= 5

    def test_result_is_odd(self):
        """Morphological kernels must be odd-sized."""
        for sharpness in [50, 150, 250, 350, 500]:
            size = compute_wire_filter_kernel_size(float(sharpness))
            assert size % 2 == 1


class TestSharpnessTracker:
    def test_initial_sharpness_zero(self):
        tracker = SharpnessTracker()
        assert tracker.sharpness == 0.0

    def test_update_sets_sharpness(self):
        tracker = SharpnessTracker(sample_interval=1)
        img = np.zeros((100, 100), dtype=np.uint8)
        img[40:60, :] = 255
        tracker.update(img)
        assert tracker.sharpness > 0

    def test_ema_smoothing(self):
        """Multiple updates should smooth the estimate."""
        tracker = SharpnessTracker(ema_alpha=0.5, sample_interval=1)
        img1 = np.zeros((100, 100), dtype=np.uint8)
        img1[40:60, :] = 255
        tracker.update(img1)
        first_val = tracker.sharpness

        # Uniform image (sharpness=0) should pull EMA down
        img2 = np.full((100, 100), 128, dtype=np.uint8)
        tracker.update(img2)
        assert tracker.sharpness < first_val

    def test_sample_interval_skips_frames(self):
        tracker = SharpnessTracker(sample_interval=5)
        img = np.zeros((100, 100), dtype=np.uint8)
        img[40:60, :] = 255
        # First 4 updates should not compute
        for _ in range(4):
            tracker.update(img)
        assert tracker.sharpness == 0.0
        # 5th should trigger
        tracker.update(img)
        assert tracker.sharpness > 0

    def test_quality_report(self):
        tracker = SharpnessTracker(sample_interval=1)
        img = np.full((100, 100), 128, dtype=np.uint8)
        tracker.update(img)
        report = tracker.get_quality_report()
        assert "sharpness" in report
        assert "quality_label" in report
        assert "is_sharp" in report
        assert report["quality_label"] == "blurry"  # uniform image

    def test_is_sharp_flag(self):
        tracker = SharpnessTracker(sample_interval=1)
        # Force high sharpness via noisy image
        rng = np.random.RandomState(42)
        img = rng.randint(0, 256, (100, 100), dtype=np.uint8)
        tracker.update(img)
        # Random noise typically has very high Laplacian variance
        assert tracker.sharpness > 0


class TestFrameDiffDetectorSharpnessIntegration:
    """Test that FrameDiffDetector uses sharpness tracking."""

    def test_get_params_includes_sharpness(self):
        from src.cv.diff_detector import FrameDiffDetector
        det = FrameDiffDetector(diff_threshold=30)
        params = det.get_params()
        assert "sharpness" in params
        assert "sharpness_quality" in params

    def test_sharpness_adjusts_threshold(self):
        """After processing sharp frames, threshold should be adjusted."""
        from src.cv.diff_detector import FrameDiffDetector
        det = FrameDiffDetector(diff_threshold=30)
        # Feed frames through update to trigger sharpness tracking
        # Create a sharp-looking frame with strong edges
        frame = np.zeros((100, 100), dtype=np.uint8)
        frame[20:80, 20:80] = 200
        frame[30:70, 30:70] = 50
        # Run enough updates to trigger sample_interval
        for _ in range(15):
            det.update(frame, has_motion=False)
        # The sharpness tracker should have been updated
        assert det._sharpness_tracker.sharpness > 0
