"""Unit tests for FieldMapper: sector/ring scoring logic."""

import math
import pytest
from src.cv.field_mapper import FieldMapper


@pytest.fixture
def mapper():
    return FieldMapper()


class TestFieldMapper:
    """Test dartboard sector and ring mapping."""

    def test_inner_bull(self, mapper):
        """Point at exact center should be Inner Bull (50)."""
        result = mapper.point_to_score(200, 200, 200, 200, 200)
        assert result["score"] == 50
        assert result["ring"] == "inner_bull"

    def test_outer_bull(self, mapper):
        """Point just outside inner bull should be Outer Bull (25)."""
        # bull_outer fraction = 15.9/170 ≈ 0.0935, so 0.06 is inside
        x = 200 + 200 * 0.06  # 6% of radius — between bull_inner and bull_outer
        result = mapper.point_to_score(x, 200, 200, 200, 200)
        assert result["score"] == 25
        assert result["ring"] == "outer_bull"

    def test_single_20_top(self, mapper):
        """Point at 12 o'clock in single area should be 20."""
        y = 200 - 200 * 0.3  # 30% radius, straight up
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["sector"] == 20
        assert result["multiplier"] == 1
        assert result["score"] == 20

    def test_triple_20(self, mapper):
        """Point in triple ring at 12 o'clock should be T20 (60)."""
        # Triple zone: 99-107mm / 170mm = 0.582-0.629 fraction
        y = 200 - 200 * 0.60  # 60% radius (inside triple zone)
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["sector"] == 20
        assert result["multiplier"] == 3
        assert result["score"] == 60

    def test_double_20(self, mapper):
        """Point in double ring at 12 o'clock should be D20 (40)."""
        # Double zone: 162-170mm / 170mm = 0.953-1.0 fraction
        y = 200 - 200 * 0.97  # 97% radius (inside double zone)
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["sector"] == 20
        assert result["multiplier"] == 2
        assert result["score"] == 40

    def test_miss_outside_board(self, mapper):
        """Point outside board should be miss (0)."""
        y = 200 - 200 * 1.05  # 105% radius
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["score"] == 0
        assert result["ring"] == "miss"

    def test_all_20_sectors_accessible(self, mapper):
        """Each of the 20 sectors should be reachable by angle."""
        found_sectors = set()
        for angle_deg in range(0, 360, 18):
            rad = math.radians(angle_deg)
            r = 0.3  # Single area
            x = 200 + 200 * r * math.cos(rad)
            y = 200 + 200 * r * math.sin(rad)
            result = mapper.point_to_score(x, y, 200, 200, 200)
            found_sectors.add(result["sector"])
        assert len(found_sectors) == 20

    def test_sector_order(self, mapper):
        """Verify sector order matches standard dartboard layout."""
        expected = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                    3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
        assert mapper.SECTOR_ORDER == expected

    def test_zero_radius_no_crash(self, mapper):
        """Passing zero radius should not crash."""
        result = mapper.point_to_score(100, 100, 100, 100, 0)
        assert result["ring"] == "miss"

    def test_all_rings_reachable(self, mapper):
        """Test that all ring types can be reached."""
        rings_found = set()
        # Center
        r = mapper.point_to_score(200, 200, 200, 200, 200)
        rings_found.add(r["ring"])
        # Outer bull (6% radius — inside bull_outer=0.0935)
        r = mapper.point_to_score(200 + 200 * 0.06, 200, 200, 200, 200)
        rings_found.add(r["ring"])
        # Single (30% radius)
        r = mapper.point_to_score(200, 200 - 200 * 0.3, 200, 200, 200)
        rings_found.add(r["ring"])
        # Triple (60% radius — inside triple=0.582-0.629)
        r = mapper.point_to_score(200, 200 - 200 * 0.60, 200, 200, 200)
        rings_found.add(r["ring"])
        # Double (97% radius — inside double=0.953-1.0)
        r = mapper.point_to_score(200, 200 - 200 * 0.97, 200, 200, 200)
        rings_found.add(r["ring"])
        # Miss
        r = mapper.point_to_score(200, 200 - 200 * 1.05, 200, 200, 200)
        rings_found.add(r["ring"])
        assert rings_found == {"inner_bull", "outer_bull", "single", "triple", "double", "miss"}

    def test_20_at_twelve_oclock(self, mapper):
        """Verify that sector 20 is at the top (12 o'clock position)."""
        # Straight up = negative y direction
        y = 200 - 200 * 0.4  # 40% radius, directly above center
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["sector"] == 20, f"Expected 20 at 12 o'clock, got {result['sector']}"

    def test_6_at_six_oclock(self, mapper):
        """Verify that sector 6 is at the bottom (6 o'clock area)."""
        # Going clockwise from 20: 20,1,18,4,13,6 → 6 is roughly at ~170°
        # At exact 6 o'clock (180° from top), the sector is 3 (index 10)
        y = 200 + 200 * 0.4  # straight down
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["sector"] == 3, f"Expected 3 at 6 o'clock, got {result['sector']}"

    def test_set_ring_radii_px(self, mapper):
        """Test custom ring radii from pixel values."""
        # Set ring radii matching standard proportions but in px
        radii_px = [6.35, 15.9, 99.0, 107.0, 162.0, 170.0]
        mapper.set_ring_radii_px(radii_px, 170.0)
        # Triple at 60% of 170 = 102px from center → inside triple (99-107)
        result = mapper.point_to_score(200, 200 - 102, 200, 200, 170)
        assert result["ring"] == "triple"
