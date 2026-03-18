"""Tests for bounce-out detection in FrameDiffDetector."""

import numpy as np

from src.cv.diff_detector import FrameDiffDetector
from src.cv.detector import DartDetection


def _gray(val: int, size: int = 100) -> np.ndarray:
    return np.full((size, size), val, dtype=np.uint8)


def _draw_dart(frame: np.ndarray, x: int = 50, y: int = 30, length: int = 40, width: int = 4) -> np.ndarray:
    """Draw a bright elongated dart-like shape on a dark frame."""
    out = frame.copy()
    out[y : y + length, x : x + width] = 255
    return out


class TestBounceOutDetection:
    """Bounce-out: motion detected, but post-frame returns to baseline."""

    def _run_throw_cycle(self, detector, baseline_frame, post_frame, settle_frames=3):
        """Simulate a throw: idle -> motion -> settling -> detection."""
        # Establish baseline
        detector.update(baseline_frame, has_motion=False)
        # Motion starts
        detector.update(baseline_frame, has_motion=True)
        assert detector.state == "in_motion"
        # Motion stops, settling begins
        detector.update(post_frame, has_motion=False)
        assert detector.state == "settling"
        # Feed settle_frames - 1 more (settling starts at count=1, needs settle_frames total)
        result = None
        for _ in range(settle_frames - 1):
            result = detector.update(post_frame, has_motion=False)
            if result is not None:
                return result
        return result

    def test_bounce_out_same_frame(self):
        """Post-frame identical to baseline -> bounce-out."""
        d = FrameDiffDetector(settle_frames=2, bounce_diff_threshold=0.2)
        baseline = _gray(100)
        # Post-frame is same as baseline (dart bounced off)
        result = self._run_throw_cycle(d, baseline, baseline, settle_frames=2)
        assert result is not None
        assert result.bounce_out is True
        assert result.confidence == 0.0

    def test_bounce_out_near_identical_frame(self):
        """Post-frame almost identical to baseline (minor noise) -> bounce-out."""
        d = FrameDiffDetector(settle_frames=2, diff_threshold=50, bounce_diff_threshold=0.2)
        baseline = _gray(100)
        # Add tiny noise that won't survive thresholding
        post = baseline.copy()
        post[10:12, 10:12] = 110  # small change, below diff_threshold of 50
        result = self._run_throw_cycle(d, baseline, post, settle_frames=2)
        assert result is not None
        assert result.bounce_out is True

    def test_landed_dart_not_bounce_out(self):
        """Post-frame has large dart-shaped diff -> NOT a bounce-out."""
        d = FrameDiffDetector(
            settle_frames=2, diff_threshold=50,
            min_diff_area=30, bounce_diff_threshold=0.2,
            min_elongation=1.0,  # relax for synthetic shapes
        )
        baseline = _gray(100)
        post = _draw_dart(baseline, x=45, y=20, length=50, width=6)
        result = self._run_throw_cycle(d, baseline, post, settle_frames=2)
        assert result is not None
        assert result.bounce_out is False
        assert result.area > 0

    def test_bounce_out_resets_to_idle(self):
        """After bounce-out, detector returns to IDLE state."""
        d = FrameDiffDetector(settle_frames=2, bounce_diff_threshold=0.2)
        baseline = _gray(100)
        self._run_throw_cycle(d, baseline, baseline, settle_frames=2)
        assert d.state == "idle"

    def test_bounce_diff_threshold_tuning(self):
        """Higher bounce_diff_threshold catches more borderline cases."""
        baseline = _gray(100)
        # Create a medium diff blob (large enough to survive morphology)
        post = baseline.copy()
        post[40:55, 48:55] = 200  # 15x7 = 105px area, diff=100

        # With low threshold 0.1 * 30 = 3 -> 105 >> 3, NOT bounce-out
        d1 = FrameDiffDetector(
            settle_frames=2, diff_threshold=50,
            min_diff_area=200, bounce_diff_threshold=0.1,
            min_elongation=1.0,
        )
        r1 = self._run_throw_cycle(d1, baseline, post, settle_frames=2)
        # Area ~105 > threshold 3, so not bounce-out, goes to _compute_diff
        # But area < min_diff_area (200), so _compute_diff returns None
        assert r1 is None

        # With very high threshold: 5.0 * 200 = 1000 -> 105 < 1000 -> bounce-out
        d2 = FrameDiffDetector(
            settle_frames=2, diff_threshold=50,
            min_diff_area=200, bounce_diff_threshold=5.0,
        )
        r2 = self._run_throw_cycle(d2, baseline, post, settle_frames=2)
        assert r2 is not None
        assert r2.bounce_out is True


class TestDartDetectionBounceOutField:
    """Test the bounce_out field on DartDetection dataclass."""

    def test_default_false(self):
        d = DartDetection(center=(10, 10), area=100.0, confidence=0.5, frame_count=3)
        assert d.bounce_out is False

    def test_explicit_true(self):
        d = DartDetection(center=(0, 0), area=0.0, confidence=0.0, frame_count=1, bounce_out=True)
        assert d.bounce_out is True
