"""Integration tests for detection components working together (P49).

Tests ShapeAnalyzer, CooldownManager, and MotionFilter in realistic
multi-dart scenarios including cooldown sequencing, bounce-outs,
shape-reject-then-accept, and dynamic area scaling.
"""

import time

import cv2
import numpy as np
import pytest

from src.cv.detection_components import ShapeAnalyzer, CooldownManager, MotionFilter
from src.cv.detector import DartImpactDetector, DartDetection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mask_with_rect(w: int, h: int, rect: tuple[int, int, int, int]) -> np.ndarray:
    """Create a binary mask with a filled rectangle (x1, y1, x2, y2)."""
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.rectangle(mask, (rect[0], rect[1]), (rect[2], rect[3]), 255, -1)
    return mask


def _make_mask_with_rects(w: int, h: int, rects: list[tuple[int, int, int, int]]) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.uint8)
    for r in rects:
        cv2.rectangle(mask, (r[0], r[1]), (r[2], r[3]), 255, -1)
    return mask


# ---------------------------------------------------------------------------
# Integration: 3 darts in sequence with cooldown
# ---------------------------------------------------------------------------

class TestThreeDartSequence:
    """Simulate detecting 3 darts with cooldown between each."""

    def test_three_darts_with_cooldown(self):
        cooldown_frames = 5
        sa = ShapeAnalyzer(area_min=5, area_max=5000, aspect_ratio_range=(0.1, 10.0))
        cm = CooldownManager(cooldown_frames=cooldown_frames, exclusion_zone_px=50)
        mf = MotionFilter(idle_threshold=3, scoring_lock_frames=3)

        detected_positions = []

        # Three dart positions far apart
        dart_rects = [
            (50, 50, 80, 90),     # dart 1
            (200, 50, 230, 90),   # dart 2
            (50, 200, 80, 240),   # dart 3
        ]

        for dart_idx, rect in enumerate(dart_rects):
            mask = _make_mask_with_rect(400, 400, rect)

            # Simulate motion arriving
            effective = mf.update(True)
            assert effective, f"Dart {dart_idx}: motion should pass through"

            # Shape analysis
            shapes = sa.find_dart_shapes(mask)
            assert len(shapes) >= 1, f"Dart {dart_idx}: should find shape"

            center = shapes[0]["center"]

            # Check cooldown/exclusion
            assert not cm.active, f"Dart {dart_idx}: cooldown should be inactive before detection"
            assert not cm.is_in_exclusion_zone(center[0], center[1]), \
                f"Dart {dart_idx}: should not be in exclusion zone"

            # Confirm detection, activate cooldown + scoring lock
            cm.activate(position=center)
            mf.activate_lock()
            detected_positions.append(center)

            assert cm.active
            assert mf.is_locked

            # Drain cooldown + scoring lock
            for _ in range(cooldown_frames):
                cm.tick()
                mf.update(False)

            assert not cm.active
            assert not mf.is_locked

        assert len(detected_positions) == 3
        # All positions should be distinct
        for i in range(len(detected_positions)):
            for j in range(i + 1, len(detected_positions)):
                dx = detected_positions[i][0] - detected_positions[j][0]
                dy = detected_positions[i][1] - detected_positions[j][1]
                assert (dx * dx + dy * dy) > 50 * 50

    def test_exclusion_zone_prevents_duplicate(self):
        """Second dart at same position is rejected by exclusion zone."""
        sa = ShapeAnalyzer(area_min=5, area_max=5000, aspect_ratio_range=(0.1, 10.0))
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=50)

        mask = _make_mask_with_rect(400, 400, (50, 50, 80, 90))
        shapes = sa.find_dart_shapes(mask)
        center = shapes[0]["center"]

        cm.activate(position=center)

        # Same position again — should be in exclusion zone
        assert cm.is_in_exclusion_zone(center[0], center[1])
        # Slightly offset — still in zone
        assert cm.is_in_exclusion_zone(center[0] + 10, center[1] + 10)


# ---------------------------------------------------------------------------
# Integration: bounce-out during cooldown
# ---------------------------------------------------------------------------

class TestBounceOutDuringCooldown:
    """A bounce-out event during cooldown should be suppressed."""

    def test_motion_during_cooldown_suppressed(self):
        cm = CooldownManager(cooldown_frames=10, exclusion_zone_px=50)
        mf = MotionFilter(idle_threshold=5, scoring_lock_frames=5)

        # Dart detected, activate cooldown + lock
        cm.activate(position=(100, 100))
        mf.activate_lock()

        # Bounce-out creates motion during cooldown — should be suppressed
        for _ in range(3):
            effective = mf.update(True)
            assert not effective, "Motion during scoring lock should be suppressed"
            cm.tick()

        assert cm.active  # Still in cooldown
        assert mf.is_locked  # Lock still active (2 frames left after 3 ticks)

    def test_bounce_out_near_confirmed_rejected(self):
        """Bounce-out motion near confirmed position rejected by exclusion zone."""
        sa = ShapeAnalyzer(area_min=5, area_max=5000, aspect_ratio_range=(0.1, 10.0))
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=50)

        # First dart confirmed
        cm.activate(position=(100, 100))

        # Bounce-out creates shape near same position
        mask = _make_mask_with_rect(400, 400, (95, 95, 115, 115))
        shapes = sa.find_dart_shapes(mask)
        assert len(shapes) >= 1

        center = shapes[0]["center"]
        # Should be rejected by exclusion zone
        assert cm.is_in_exclusion_zone(center[0], center[1])


# ---------------------------------------------------------------------------
# Integration: shape-reject followed by valid dart
# ---------------------------------------------------------------------------

class TestShapeRejectThenValid:
    """Invalid shape is rejected, then a valid dart shape is accepted."""

    def test_reject_then_accept(self):
        sa = ShapeAnalyzer(area_min=100, area_max=5000, aspect_ratio_range=(0.3, 3.0))
        cm = CooldownManager(cooldown_frames=5, exclusion_zone_px=50)
        mf = MotionFilter(idle_threshold=3, scoring_lock_frames=3)

        # Frame 1: tiny contour — rejected by area_min
        tiny_mask = _make_mask_with_rect(400, 400, (100, 100, 103, 103))
        rejected = sa.find_dart_shapes(tiny_mask)
        assert len(rejected) == 0, "Tiny contour should be rejected"

        effective = mf.update(True)
        assert effective  # Motion passes, but no shape found

        # Frame 2: valid contour
        valid_mask = _make_mask_with_rect(400, 400, (100, 100, 130, 140))
        accepted = sa.find_dart_shapes(valid_mask)
        assert len(accepted) >= 1, "Valid contour should be accepted"

        center = accepted[0]["center"]
        assert not cm.is_in_exclusion_zone(center[0], center[1])

        cm.activate(position=center)
        mf.activate_lock()
        assert cm.active
        assert mf.is_locked

    def test_extreme_aspect_ratio_rejected(self):
        """Very elongated shape is rejected, normal shape passes."""
        sa = ShapeAnalyzer(area_min=10, area_max=10000, aspect_ratio_range=(0.3, 3.0))

        # Very wide, thin shape (aspect ratio ~20:1)
        wide_mask = _make_mask_with_rect(400, 400, (10, 100, 200, 105))
        assert sa.find_dart_shapes(wide_mask) == []

        # Normal shape
        normal_mask = _make_mask_with_rect(400, 400, (100, 100, 130, 140))
        results = sa.find_dart_shapes(normal_mask)
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Integration: ShapeAnalyzer with dynamic area scaling (P12)
# ---------------------------------------------------------------------------

class TestDynamicAreaScaling:
    """Test ShapeAnalyzer works correctly after DartImpactDetector scales area."""

    def test_scale_area_to_roi(self):
        det = DartImpactDetector(
            area_min=10, area_max=1000,
            confirmation_frames=1,
        )
        # Scale to 800x800 ROI (4x reference area)
        det.scale_area_to_roi(800, 800, reference_size=400)
        assert det.area_min == 40   # 10 * 4
        assert det.area_max == 4000  # 1000 * 4
        # Internal ShapeAnalyzer should be updated too
        assert det._shape_analyzer.area_min == 40
        assert det._shape_analyzer.area_max == 4000

    def test_scaled_analyzer_finds_larger_contours(self):
        """After scaling, larger contours that would have been rejected now pass."""
        det = DartImpactDetector(
            area_min=10, area_max=500,
            confirmation_frames=1,
        )
        # Contour ~30x40 = 1200 area — rejected at default scale (max 500)
        mask = _make_mask_with_rect(800, 800, (100, 100, 130, 140))
        shapes_before = det._shape_analyzer.find_dart_shapes(mask)
        assert len(shapes_before) == 0, "Should be rejected before scaling"

        # After scaling 4x, area_max becomes 2000 — contour (1200) now fits
        det.scale_area_to_roi(800, 800, reference_size=400)
        shapes_after = det._shape_analyzer.find_dart_shapes(mask)
        assert len(shapes_after) >= 1, "Should be accepted after scaling"


# ---------------------------------------------------------------------------
# Integration: MotionFilter scoring-lock + idle in pipeline context
# ---------------------------------------------------------------------------

class TestMotionFilterPipelineContext:
    """MotionFilter scoring-lock and idle tracking in a pipeline-like flow."""

    def test_lock_then_idle_then_next_dart(self):
        mf = MotionFilter(idle_threshold=5, scoring_lock_frames=3)

        # Dart detected — activate lock
        mf.activate_lock()

        # 3 frames of lock (motion suppressed)
        for _ in range(3):
            assert mf.update(True) is False

        # Lock expired
        assert not mf.is_locked

        # 5 frames of no motion — idle
        for _ in range(5):
            mf.update(False)
        assert mf.is_idle

        # Next dart arrives — breaks idle
        assert mf.update(True) is True
        assert not mf.is_idle

    def test_scoring_lock_does_not_affect_idle_counter(self):
        """Idle counter should still increment during scoring lock (no motion)."""
        mf = MotionFilter(idle_threshold=3, scoring_lock_frames=5)
        mf.activate_lock()

        # Feed no-motion during lock
        for _ in range(3):
            mf.update(False)

        # Even though locked, idle should be reached since no_motion_count incremented
        assert mf.is_idle

    def test_motion_during_lock_resets_idle(self):
        """Motion events during lock reset idle counter even though suppressed."""
        mf = MotionFilter(idle_threshold=3, scoring_lock_frames=10)
        mf.activate_lock()

        # No motion for 3 frames -> idle
        for _ in range(3):
            mf.update(False)
        assert mf.is_idle

        # Motion arrives (suppressed by lock, but resets idle counter)
        mf.update(True)
        assert not mf.is_idle


# ---------------------------------------------------------------------------
# Integration: DartImpactDetector register + cooldown cycle
# ---------------------------------------------------------------------------

class TestDetectorCooldownCycle:
    """Full register_confirmed + cooldown cycle on DartImpactDetector."""

    def test_register_three_darts_with_cooldown(self):
        det = DartImpactDetector(
            confirmation_frames=1, cooldown_frames=5,
            exclusion_zone_px=50,
        )

        positions = [(100, 100), (250, 100), (100, 250)]
        for pos in positions:
            d = DartDetection(center=pos, area=200, confidence=0.8, frame_count=3)
            assert det.register_confirmed(d), f"Should accept dart at {pos}"
            # Drain cooldown
            for _ in range(5):
                det.tick()

        confirmed = det.get_all_confirmed()
        assert len(confirmed) == 3

    def test_register_rejected_during_cooldown(self):
        det = DartImpactDetector(
            confirmation_frames=1, cooldown_frames=10,
            exclusion_zone_px=50,
        )
        d1 = DartDetection(center=(100, 100), area=200, confidence=0.8, frame_count=3)
        assert det.register_confirmed(d1)

        # Immediately try another — rejected by cooldown
        d2 = DartDetection(center=(300, 300), area=200, confidence=0.8, frame_count=3)
        assert not det.register_confirmed(d2)

        assert len(det.get_all_confirmed()) == 1

    def test_reset_clears_all_state(self):
        det = DartImpactDetector(
            confirmation_frames=1, cooldown_frames=10,
            exclusion_zone_px=50,
        )
        d = DartDetection(center=(100, 100), area=200, confidence=0.8, frame_count=3)
        det.register_confirmed(d)
        assert det.is_in_cooldown()

        det.reset()
        assert not det.is_in_cooldown()
        assert len(det.get_all_confirmed()) == 0


# ---------------------------------------------------------------------------
# Performance: delegation overhead
# ---------------------------------------------------------------------------

class TestDelegationOverhead:
    """Ensure ShapeAnalyzer delegation adds no measurable overhead."""

    def test_shape_analyzer_delegation_speed(self):
        sa = ShapeAnalyzer(area_min=5, area_max=50000, aspect_ratio_range=(0.1, 10.0))
        mask = _make_mask_with_rects(400, 400, [
            (50, 50, 80, 90),
            (150, 150, 190, 200),
            (250, 50, 280, 90),
        ])

        # Warm up
        for _ in range(10):
            sa.find_dart_shapes(mask)

        iterations = 500
        start = time.perf_counter()
        for _ in range(iterations):
            sa.find_dart_shapes(mask)
        elapsed = time.perf_counter() - start

        per_call_ms = (elapsed / iterations) * 1000
        # Should be well under 1ms per call for a 400x400 mask
        assert per_call_ms < 2.0, f"ShapeAnalyzer too slow: {per_call_ms:.3f}ms/call"

    def test_cooldown_manager_overhead(self):
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=50)
        # Add several zones
        for i in range(10):
            cm.activate(position=(i * 30, i * 30))

        iterations = 10000
        start = time.perf_counter()
        for _ in range(iterations):
            cm.is_in_exclusion_zone(150, 150)
            cm.tick()
            cm.activate(position=(150, 150))
        elapsed = time.perf_counter() - start

        per_call_us = (elapsed / iterations) * 1_000_000
        assert per_call_us < 100, f"CooldownManager too slow: {per_call_us:.1f}us/iteration"
