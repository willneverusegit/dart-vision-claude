"""Tests for modular detection components (P43)."""

import numpy as np
import cv2
import pytest

from src.cv.detection_components import ShapeAnalyzer, CooldownManager, MotionFilter


# ---------------------------------------------------------------------------
# ShapeAnalyzer
# ---------------------------------------------------------------------------

class TestShapeAnalyzer:
    def test_init_defaults(self):
        sa = ShapeAnalyzer()
        assert sa.area_min == 10
        assert sa.area_max == 1000

    def test_init_validation(self):
        with pytest.raises(ValueError):
            ShapeAnalyzer(area_min=-1)
        with pytest.raises(ValueError):
            ShapeAnalyzer(area_min=100, area_max=50)
        with pytest.raises(ValueError):
            ShapeAnalyzer(aspect_ratio_range=(0, 1.0))
        with pytest.raises(ValueError):
            ShapeAnalyzer(aspect_ratio_range=(3.0, 1.0))

    def test_empty_mask(self):
        sa = ShapeAnalyzer()
        mask = np.zeros((100, 100), dtype=np.uint8)
        assert sa.find_dart_shapes(mask) == []

    def test_finds_valid_contour(self):
        sa = ShapeAnalyzer(area_min=5, area_max=5000, aspect_ratio_range=(0.1, 10.0))
        mask = np.zeros((200, 200), dtype=np.uint8)
        # Draw a rectangle that will pass filters
        cv2.rectangle(mask, (50, 80), (80, 120), 255, -1)
        results = sa.find_dart_shapes(mask)
        assert len(results) >= 1
        assert "center" in results[0]
        assert "area" in results[0]
        assert results[0]["area"] > 0

    def test_filters_too_small(self):
        sa = ShapeAnalyzer(area_min=10000, area_max=20000)
        mask = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(mask, (50, 80), (80, 120), 255, -1)
        assert sa.find_dart_shapes(mask) == []

    def test_filters_too_large(self):
        sa = ShapeAnalyzer(area_min=1, area_max=10)
        mask = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(mask, (10, 10), (190, 190), 255, -1)
        assert sa.find_dart_shapes(mask) == []

    def test_sorted_by_area_descending(self):
        sa = ShapeAnalyzer(area_min=5, area_max=50000, aspect_ratio_range=(0.1, 10.0))
        mask = np.zeros((300, 300), dtype=np.uint8)
        cv2.rectangle(mask, (10, 10), (30, 30), 255, -1)    # small
        cv2.rectangle(mask, (100, 100), (180, 180), 255, -1)  # large
        results = sa.find_dart_shapes(mask)
        if len(results) >= 2:
            assert results[0]["area"] >= results[1]["area"]


# ---------------------------------------------------------------------------
# CooldownManager
# ---------------------------------------------------------------------------

class TestCooldownManager:
    def test_init_defaults(self):
        cm = CooldownManager()
        assert not cm.active
        assert cm.remaining == 0

    def test_init_validation(self):
        with pytest.raises(ValueError):
            CooldownManager(cooldown_frames=-1)

    def test_activate_and_tick(self):
        cm = CooldownManager(cooldown_frames=3)
        cm.activate()
        assert cm.active
        assert cm.remaining == 3

        cm.tick()
        assert cm.remaining == 2
        cm.tick()
        assert cm.remaining == 1
        cm.tick()
        assert cm.remaining == 0
        assert not cm.active

    def test_tick_does_not_go_negative(self):
        cm = CooldownManager(cooldown_frames=1)
        cm.tick()  # already 0
        assert cm.remaining == 0

    def test_reset(self):
        cm = CooldownManager(cooldown_frames=10)
        cm.activate()
        assert cm.active
        cm.reset()
        assert not cm.active
        assert cm.remaining == 0

    def test_zero_cooldown(self):
        cm = CooldownManager(cooldown_frames=0)
        cm.activate()
        assert not cm.active  # 0 frames = immediately inactive

    # --- P42: Spatial exclusion zone tests ---

    def test_exclusion_zone_rejects_nearby(self):
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=50)
        cm.activate(position=(100, 100))
        assert cm.is_in_exclusion_zone(110, 110)  # within 50px
        assert cm.is_in_exclusion_zone(100, 100)  # exact same point

    def test_exclusion_zone_allows_far(self):
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=50)
        cm.activate(position=(100, 100))
        assert not cm.is_in_exclusion_zone(200, 200)  # ~141px away

    def test_exclusion_zone_expires_after_ticks(self):
        cm = CooldownManager(cooldown_frames=3, exclusion_zone_px=50)
        cm.activate(position=(100, 100))
        assert cm.is_in_exclusion_zone(100, 100)
        cm.tick()
        cm.tick()
        cm.tick()
        assert not cm.is_in_exclusion_zone(100, 100)  # expired
        assert cm.zone_count == 0

    def test_exclusion_zone_cleared_on_reset(self):
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=50)
        cm.activate(position=(100, 100))
        cm.activate(position=(200, 200))
        assert cm.zone_count == 2
        cm.reset()
        assert cm.zone_count == 0
        assert not cm.is_in_exclusion_zone(100, 100)

    def test_multiple_zones(self):
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=50)
        cm.activate(position=(100, 100))
        cm.activate(position=(300, 300))
        assert cm.is_in_exclusion_zone(105, 105)
        assert cm.is_in_exclusion_zone(305, 305)
        assert not cm.is_in_exclusion_zone(200, 200)

    def test_activate_without_position_no_zone(self):
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=50)
        cm.activate()  # no position
        assert cm.active
        assert cm.zone_count == 0

    def test_exclusion_zone_zero_radius(self):
        cm = CooldownManager(cooldown_frames=30, exclusion_zone_px=0)
        cm.activate(position=(100, 100))
        assert cm.zone_count == 0  # no zone added when radius is 0


# ---------------------------------------------------------------------------
# MotionFilter
# ---------------------------------------------------------------------------

class TestMotionFilter:
    def test_init_defaults(self):
        mf = MotionFilter()
        assert not mf.is_idle
        assert not mf.is_locked

    def test_init_validation(self):
        with pytest.raises(ValueError):
            MotionFilter(idle_threshold=-1)
        with pytest.raises(ValueError):
            MotionFilter(scoring_lock_frames=-1)

    def test_idle_detection(self):
        mf = MotionFilter(idle_threshold=3)
        assert not mf.is_idle
        mf.update(False)
        mf.update(False)
        assert not mf.is_idle
        mf.update(False)
        assert mf.is_idle

    def test_motion_resets_idle(self):
        mf = MotionFilter(idle_threshold=2)
        mf.update(False)
        mf.update(False)
        assert mf.is_idle
        mf.update(True)
        assert not mf.is_idle

    def test_scoring_lock(self):
        mf = MotionFilter(scoring_lock_frames=2)
        mf.activate_lock()
        assert mf.is_locked

        # Lock suppresses motion
        result = mf.update(True)
        assert result is False
        assert mf.is_locked

        result = mf.update(True)
        assert result is False
        assert not mf.is_locked

        # After lock expires, motion passes through
        result = mf.update(True)
        assert result is True

    def test_update_returns_motion_when_no_lock(self):
        mf = MotionFilter()
        assert mf.update(True) is True
        assert mf.update(False) is False

    def test_reset(self):
        mf = MotionFilter(idle_threshold=1, scoring_lock_frames=5)
        mf.update(False)
        mf.update(False)
        mf.activate_lock()
        assert mf.is_idle
        assert mf.is_locked
        mf.reset()
        assert not mf.is_idle
        assert not mf.is_locked
