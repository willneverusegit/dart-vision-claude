"""Tests for board-centric geometry model and scoring."""

import math
import pytest
from src.cv.geometry import BoardGeometry, BoardHit, BoardPose, PolarCoord


@pytest.fixture
def geometry() -> BoardGeometry:
    """Standard 400x400 ROI with center at (200, 200)."""
    pose = BoardPose(
        homography=None,
        center_px=(200.0, 200.0),
        radii_px=(10.0, 19.0, 106.0, 116.0, 188.0, 200.0),
        rotation_deg=0.0,
        valid=True,
    )
    return BoardGeometry.from_pose(pose, roi_size=(400, 400))


class TestBoardPose:
    def test_from_config(self) -> None:
        pose = BoardPose.from_config(
            {
                "center_px": [200, 200],
                "radii_px": [10, 20, 100, 110, 180, 200],
                "rotation_deg": 5.0,
                "optical_center_roi_px": [202, 198],
                "valid": True,
                "method": "aruco",
            }
        )
        assert pose.valid
        assert pose.optical_center_roi_px == (202.0, 198.0)
        assert pose.radii_px[-1] == 200.0


class TestGeometryBasic:
    def test_normalize_and_polar(self) -> None:
        g = BoardGeometry(
            roi_size=(400, 400),
            center_px=(200.0, 200.0),
            optical_center_px=(200.0, 200.0),
            radii_px=(10.0, 20.0, 100.0, 110.0, 180.0, 200.0),
            rotation_deg=0.0,
            valid=True,
            method="manual",
        )
        nx, ny = g.normalize_point(200.0, 200.0)
        assert round(nx, 4) == 0.0
        assert round(ny, 4) == 0.0

        radius_norm, angle_deg = g.point_to_polar(200.0, 100.0)
        assert 0.49 <= radius_norm <= 0.51
        assert angle_deg == 0.0


class TestPointToScore:
    def test_bullseye(self, geometry: BoardGeometry) -> None:
        hit = geometry.point_to_score(200.0, 200.0)
        assert hit.score == 50
        assert hit.ring == "inner_bull"
        assert hit.multiplier == 1

    def test_outer_bull(self, geometry: BoardGeometry) -> None:
        # Punkt knapp ausserhalb inner bull, aber innerhalb outer bull
        hit = geometry.point_to_score(200.0, 200.0 - 12.0)
        assert hit.score == 25
        assert hit.ring == "outer_bull"

    def test_triple_20(self, geometry: BoardGeometry) -> None:
        # 20 ist oben (12 Uhr), Triple-Ring bei r_norm 0.582-0.629
        # With radius 200px: 0.60 * 200 = 120px from center
        hit = geometry.point_to_score(200.0, 200.0 - 120.0)
        assert hit.sector == 20
        assert hit.multiplier == 3
        assert hit.score == 60
        assert hit.ring == "triple"

    def test_double_20(self, geometry: BoardGeometry) -> None:
        # Double-Ring bei ~195px vom Center
        hit = geometry.point_to_score(200.0, 200.0 - 195.0)
        assert hit.sector == 20
        assert hit.multiplier == 2
        assert hit.score == 40

    def test_miss(self, geometry: BoardGeometry) -> None:
        # Weit ausserhalb
        hit = geometry.point_to_score(200.0, 200.0 - 250.0)
        assert hit.score == 0
        assert hit.ring == "miss"

    def test_single_sector(self, geometry: BoardGeometry) -> None:
        # Rechts vom Center = Sektor 6 (3-Uhr-Position)
        hit = geometry.point_to_score(200.0 + 150.0, 200.0)
        assert hit.sector == 6
        assert hit.multiplier == 1
        assert hit.ring == "single"

    def test_returns_board_hit_type(self, geometry: BoardGeometry) -> None:
        hit = geometry.point_to_score(200.0, 200.0)
        assert isinstance(hit, BoardHit)
        assert isinstance(hit.polar, PolarCoord)

    def test_board_mm_populated(self, geometry: BoardGeometry) -> None:
        hit = geometry.point_to_score(200.0, 100.0)
        assert hit.board_mm[1] < 0  # above center = negative y in mm

    def test_hit_to_dict_keys(self, geometry: BoardGeometry) -> None:
        hit = geometry.point_to_score(200.0, 200.0)
        d = geometry.hit_to_dict(hit)
        required_keys = {"score", "sector", "multiplier", "ring",
                         "normalized_distance", "angle_deg", "roi_x", "roi_y"}
        assert required_keys.issubset(d.keys())

    def test_all_20_sectors_accessible(self, geometry: BoardGeometry) -> None:
        """Each of the 20 sectors should be reachable by angle."""
        found_sectors = set()
        for angle_deg in range(0, 360, 18):
            rad = math.radians(angle_deg)
            r = 0.5  # Single area (normalized)
            x = 200 + 200 * r * math.cos(rad)
            y = 200 + 200 * r * math.sin(rad)
            hit = geometry.point_to_score(x, y)
            if hit.sector > 0:
                found_sectors.add(hit.sector)
        assert len(found_sectors) == 20

    def test_all_rings_reachable(self, geometry: BoardGeometry) -> None:
        """Test that all ring types can be reached."""
        rings_found = set()
        # Center
        rings_found.add(geometry.point_to_score(200, 200).ring)
        # Outer bull (~12px from center)
        rings_found.add(geometry.point_to_score(200 + 12, 200).ring)
        # Single (~100px from center, ~50% radius)
        rings_found.add(geometry.point_to_score(200, 200 - 60).ring)
        # Triple (~120px from center, r_norm ~0.60)
        rings_found.add(geometry.point_to_score(200, 200 - 120).ring)
        # Double (~195px from center)
        rings_found.add(geometry.point_to_score(200, 200 - 195).ring)
        # Miss
        rings_found.add(geometry.point_to_score(200, 200 - 250).ring)
        assert rings_found == {"inner_bull", "outer_bull", "single", "triple", "double", "miss"}

    def test_zero_radius_no_crash(self) -> None:
        """BoardGeometry with zero radius should return miss without crash."""
        g = BoardGeometry(
            roi_size=(400, 400),
            center_px=(200.0, 200.0),
            optical_center_px=(200.0, 200.0),
            radii_px=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            rotation_deg=0.0,
            valid=False,
        )
        hit = g.point_to_score(100, 100)
        assert hit.ring == "miss"

    def test_20_at_twelve_oclock(self, geometry: BoardGeometry) -> None:
        """Verify that sector 20 is at the top (12 o'clock position)."""
        hit = geometry.point_to_score(200, 200 - 80)
        assert hit.sector == 20, f"Expected 20 at 12 o'clock, got {hit.sector}"

    def test_3_at_six_oclock(self, geometry: BoardGeometry) -> None:
        """Verify that sector 3 is at the bottom (6 o'clock)."""
        hit = geometry.point_to_score(200, 200 + 80)
        assert hit.sector == 3, f"Expected 3 at 6 o'clock, got {hit.sector}"
