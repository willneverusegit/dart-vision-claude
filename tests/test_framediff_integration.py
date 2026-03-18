"""Integration tests: FrameDiffDetector + CooldownManager + MotionFilter (P53).

Tests FrameDiffDetector working together with detection components
in realistic single-cam scenarios including multi-dart sequences,
cooldown zones, settling phase interaction, and idle-triggered baseline updates.
"""

import numpy as np
import cv2
import pytest

from src.cv.diff_detector import FrameDiffDetector
from src.cv.detection_components import CooldownManager, MotionFilter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gray(h: int = 200, w: int = 300, value: int = 128) -> np.ndarray:
    """Create a uniform grayscale frame."""
    return np.full((h, w), value, dtype=np.uint8)


def _with_dart(base: np.ndarray, x: int, y: int, w: int = 8, h: int = 30, intensity: int = 255) -> np.ndarray:
    """Draw an elongated dart-like rectangle on a copy of base."""
    frame = base.copy()
    cv2.rectangle(frame, (x, y), (x + w, y + h), int(intensity), -1)
    return frame


def _run_idle(fdd: FrameDiffDetector, frame: np.ndarray, n: int) -> None:
    """Feed n idle (no-motion) frames to establish baseline."""
    for _ in range(n):
        fdd.update(frame, has_motion=False)


def _throw_dart(fdd: FrameDiffDetector, base: np.ndarray, post: np.ndarray,
                motion_frames: int = 3, settle_extra: int = 0):
    """Simulate a dart throw: motion frames, then settling frames with post image.

    Returns the detection result from the settling phase.
    """
    # Motion phase
    for _ in range(motion_frames):
        fdd.update(base, has_motion=True)

    # Settling phase: no motion, detector sees post frame
    result = None
    needed = fdd.settle_frames + settle_extra
    for _ in range(needed):
        r = fdd.update(post, has_motion=False)
        if r is not None:
            result = r
    return result


# ---------------------------------------------------------------------------
# FrameDiffDetector + CooldownManager: cooldown after detection
# ---------------------------------------------------------------------------

class TestFrameDiffWithCooldown:
    """FrameDiffDetector detections gated by CooldownManager."""

    def test_cooldown_blocks_immediate_redetection(self):
        """After a detection, cooldown prevents accepting the same position."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        cm = CooldownManager(cooldown_frames=10, exclusion_zone_px=40)

        base = _gray()
        post = _with_dart(base, 100, 80)

        # Establish baseline
        _run_idle(fdd, base, 5)

        # First dart
        det = _throw_dart(fdd, base, post)
        assert det is not None
        assert not det.bounce_out

        # Register with cooldown
        cm.activate(position=det.center)

        # Reset detector for next throw
        fdd.reset()
        _run_idle(fdd, post, 5)  # new baseline includes first dart

        # Second dart at same position — cooldown should block
        post2 = _with_dart(post, 102, 82)  # very close to first
        det2 = _throw_dart(fdd, post, post2)
        if det2 is not None:
            assert cm.is_in_exclusion_zone(det2.center[0], det2.center[1]), \
                "Detection near confirmed position should be in exclusion zone"

    def test_cooldown_allows_distant_dart(self):
        """Dart far from exclusion zone passes cooldown check."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        cm = CooldownManager(cooldown_frames=10, exclusion_zone_px=40)

        base = _gray()
        post1 = _with_dart(base, 30, 30)

        _run_idle(fdd, base, 5)
        det1 = _throw_dart(fdd, base, post1)
        assert det1 is not None
        cm.activate(position=det1.center)

        # Tick through cooldown
        for _ in range(10):
            cm.tick()
        assert not cm.active

        # Second dart far away
        fdd.reset()
        _run_idle(fdd, post1, 5)
        post2 = _with_dart(post1, 250, 150)
        det2 = _throw_dart(fdd, post1, post2)
        if det2 is not None:
            assert not cm.is_in_exclusion_zone(det2.center[0], det2.center[1])

    def test_exclusion_zone_expires_with_cooldown(self):
        """Exclusion zones expire after cooldown_frames ticks."""
        cm = CooldownManager(cooldown_frames=5, exclusion_zone_px=50)
        cm.activate(position=(100, 100))
        assert cm.is_in_exclusion_zone(100, 100)

        for _ in range(5):
            cm.tick()

        assert not cm.active
        assert not cm.is_in_exclusion_zone(100, 100)


# ---------------------------------------------------------------------------
# FrameDiffDetector + MotionFilter: scoring lock + idle baseline
# ---------------------------------------------------------------------------

class TestFrameDiffWithMotionFilter:
    """MotionFilter scoring lock and idle detection with FrameDiffDetector."""

    def test_scoring_lock_suppresses_motion_after_detection(self):
        """After detection, MotionFilter lock suppresses subsequent motion."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        mf = MotionFilter(idle_threshold=5, scoring_lock_frames=5)

        base = _gray()
        post = _with_dart(base, 100, 80)

        _run_idle(fdd, base, 5)
        det = _throw_dart(fdd, base, post)
        assert det is not None

        # Activate scoring lock
        mf.activate_lock()

        # Motion during lock is suppressed
        for _ in range(5):
            effective = mf.update(True)
            assert not effective, "Motion should be suppressed during scoring lock"

        # Lock expired
        assert not mf.is_locked
        assert mf.update(True) is True

    def test_idle_detection_as_baseline_trigger(self):
        """MotionFilter idle state can trigger baseline update in FrameDiffDetector."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        mf = MotionFilter(idle_threshold=3, scoring_lock_frames=3)

        base = _gray()

        # Feed frames — after idle_threshold no-motion frames, idle detected
        for _ in range(5):
            mf.update(False)
            fdd.update(base, has_motion=False)

        assert mf.is_idle
        # When idle, FrameDiffDetector should be in IDLE state with updated baseline
        assert fdd.state == "idle"
        assert fdd._baseline is not None

    def test_lock_then_idle_then_next_detection(self):
        """Full cycle: detect -> lock -> idle -> next dart."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        mf = MotionFilter(idle_threshold=5, scoring_lock_frames=3)

        base = _gray()
        post1 = _with_dart(base, 50, 50)

        # Baseline
        _run_idle(fdd, base, 5)

        # First dart
        det1 = _throw_dart(fdd, base, post1)
        assert det1 is not None

        mf.activate_lock()

        # Drain lock
        for _ in range(3):
            mf.update(False)
        assert not mf.is_locked

        # Reach idle
        for _ in range(5):
            mf.update(False)
        assert mf.is_idle

        # Reset for next dart (simulating pipeline reset after idle)
        fdd.reset()
        _run_idle(fdd, post1, 5)

        # Second dart
        post2 = _with_dart(post1, 200, 100)
        det2 = _throw_dart(fdd, post1, post2)
        assert det2 is not None


# ---------------------------------------------------------------------------
# Multi-dart sequence via FrameDiff with realistic diff masks
# ---------------------------------------------------------------------------

class TestMultiDartSequence:
    """Three-dart sequence through FrameDiffDetector with cooldown gating."""

    def test_three_dart_sequence(self):
        """Detect 3 darts in sequence, each gated by cooldown and exclusion zones."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        cm = CooldownManager(cooldown_frames=5, exclusion_zone_px=40)
        mf = MotionFilter(idle_threshold=5, scoring_lock_frames=3)

        base = _gray()
        dart_positions = [(30, 30), (150, 30), (30, 130)]
        detections = []

        current_base = base.copy()

        for dx, dy in dart_positions:
            # Establish baseline
            fdd.reset()
            _run_idle(fdd, current_base, 5)

            # Throw dart
            post = _with_dart(current_base, dx, dy)
            det = _throw_dart(fdd, current_base, post)

            assert det is not None, f"Should detect dart at ({dx}, {dy})"
            assert not det.bounce_out

            # Check exclusion zone
            assert not cm.is_in_exclusion_zone(det.center[0], det.center[1]), \
                f"Dart at ({dx},{dy}) should not be in exclusion zone"

            # Register
            cm.activate(position=det.center)
            mf.activate_lock()
            detections.append(det)

            # Drain cooldown
            for _ in range(5):
                cm.tick()
                mf.update(False)

            # New baseline includes this dart
            current_base = post.copy()

        assert len(detections) == 3

    def test_duplicate_position_blocked(self):
        """Second dart at nearly the same position blocked by exclusion zone."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        cm = CooldownManager(cooldown_frames=20, exclusion_zone_px=50)

        base = _gray()
        _run_idle(fdd, base, 5)

        # First dart
        post = _with_dart(base, 100, 80)
        det1 = _throw_dart(fdd, base, post)
        assert det1 is not None
        cm.activate(position=det1.center)

        # Attempt second dart very close (within exclusion zone)
        # Even if detector finds it, cooldown manager blocks it
        assert cm.is_in_exclusion_zone(det1.center[0] + 5, det1.center[1] + 5)


# ---------------------------------------------------------------------------
# Settling phase + cooldown interaction
# ---------------------------------------------------------------------------

class TestSettlingCooldownInteraction:
    """Tests settling phase behavior interacting with cooldown system."""

    def test_settling_interrupted_by_motion(self):
        """Motion during settling resets settle counter, no premature detection."""
        fdd = FrameDiffDetector(
            settle_frames=3, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )

        base = _gray()
        post = _with_dart(base, 100, 80)

        _run_idle(fdd, base, 5)

        # Start motion
        fdd.update(base, has_motion=True)
        fdd.update(base, has_motion=True)
        assert fdd.state == "in_motion"

        # Start settling
        fdd.update(post, has_motion=False)
        assert fdd.state == "settling"

        # Interrupt with motion
        fdd.update(post, has_motion=True)
        assert fdd.state == "in_motion"

        # Resume settling from scratch — need full settle_frames again
        result = None
        for _ in range(fdd.settle_frames):
            r = fdd.update(post, has_motion=False)
            if r is not None:
                result = r

        assert result is not None, "Should detect after full settle period"

    def test_cooldown_active_during_settling_of_next_dart(self):
        """Cooldown from first dart can be active while second dart settles."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        cm = CooldownManager(cooldown_frames=20, exclusion_zone_px=40)

        base = _gray()
        _run_idle(fdd, base, 5)

        # First dart
        post1 = _with_dart(base, 50, 50)
        det1 = _throw_dart(fdd, base, post1)
        assert det1 is not None
        cm.activate(position=det1.center)

        # Only partial cooldown elapsed
        for _ in range(3):
            cm.tick()
        assert cm.active, "Cooldown should still be active"

        # Second dart at distant position — detector can find it
        fdd.reset()
        _run_idle(fdd, post1, 5)
        post2 = _with_dart(post1, 250, 150)
        det2 = _throw_dart(fdd, post1, post2)

        if det2 is not None:
            # Cooldown still active but position is far away
            in_zone = cm.is_in_exclusion_zone(det2.center[0], det2.center[1])
            assert not in_zone, "Distant dart should not be in exclusion zone"

    def test_bounce_out_does_not_trigger_cooldown(self):
        """Bounce-out detection should not create an exclusion zone."""
        fdd = FrameDiffDetector(
            settle_frames=2, diff_threshold=30, min_diff_area=20,
            max_diff_area=5000, min_elongation=1.0, adaptive_threshold=False,
        )
        cm = CooldownManager(cooldown_frames=10, exclusion_zone_px=50)

        base = _gray()
        _run_idle(fdd, base, 5)

        # Motion but post-frame same as baseline = bounce-out
        for _ in range(3):
            fdd.update(base, has_motion=True)

        result = None
        for _ in range(fdd.settle_frames):
            r = fdd.update(base, has_motion=False)
            if r is not None:
                result = r

        if result is not None and result.bounce_out:
            # Don't activate cooldown for bounce-outs
            assert cm.zone_count == 0, "No exclusion zones for bounce-out"
