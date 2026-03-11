"""Maps pixel coordinates to dartboard sector and score."""

import math


class FieldMapper:
    """Maps pixel coordinates to dartboard sector and score.

    The standard dartboard has 20 at the top (12 o'clock position).
    Sectors are numbered clockwise starting from 20.
    """

    # Standard dartboard sector order, clockwise starting at 12 o'clock (20)
    SECTOR_ORDER: list[int] = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                                3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

    # Default ring radii as fractions of outer double radius
    # Based on official BDO/WDF dimensions:
    #   Bull inner: 6.35mm, Bull outer: 15.9mm
    #   Triple inner: 99mm, Triple outer: 107mm
    #   Double inner: 162mm, Double outer: 170mm
    RING_RADII_FRACTIONS: dict[str, float] = {
        "bull_inner": 6.35 / 170.0,     # 0.0374
        "bull_outer": 15.9 / 170.0,     # 0.0935
        "triple_inner": 99.0 / 170.0,   # 0.5824
        "triple_outer": 107.0 / 170.0,  # 0.6294
        "double_inner": 162.0 / 170.0,  # 0.9529
        "double_outer": 1.0,            # 1.0000
    }

    def __init__(self, sector_offset_deg: float = 9.0,
                 ring_radii: dict[str, float] | None = None) -> None:
        """
        Args:
            sector_offset_deg: Half-sector angular offset. 9 degrees means
                each sector spans 18 degrees, and the sector boundary sits
                at +/- 9 degrees from the sector center line.
            ring_radii: Optional custom ring radii (fractions of outer radius).
                If None, uses standard BDO/WDF proportions.
        """
        self.sector_offset_deg = sector_offset_deg
        self.sector_angle_deg = 18.0  # 360 / 20
        self.ring_radii = ring_radii or dict(self.RING_RADII_FRACTIONS)

    def set_ring_radii_px(self, radii_px: list[float], outer_radius_px: float) -> None:
        """Set ring radii from pixel values (e.g., from calibration).

        Args:
            radii_px: [bull_inner, bull_outer, triple_inner, triple_outer,
                       double_inner, double_outer] in pixels.
            outer_radius_px: Pixel radius of the outer double ring.
        """
        if len(radii_px) != 6 or outer_radius_px <= 0:
            return
        keys = ["bull_inner", "bull_outer", "triple_inner",
                "triple_outer", "double_inner", "double_outer"]
        for key, r_px in zip(keys, radii_px):
            self.ring_radii[key] = r_px / outer_radius_px

    def point_to_score(self, x: float, y: float,
                       center_x: float, center_y: float,
                       radius_px: float) -> dict:
        """
        Convert pixel coords to score.

        The coordinate system assumes:
        - (center_x, center_y) is the bullseye
        - radius_px is the outer double ring radius
        - 20 is at the top (12 o'clock, i.e. negative y direction)

        Returns:
            {
                "score": int,           # Total points (e.g., 60 for T20)
                "sector": int,          # Base sector value (e.g., 20)
                "multiplier": int,      # 1, 2, or 3 (or 0 for miss)
                "ring": str,            # "inner_bull", "outer_bull", "single",
                                        # "triple", "double", "miss"
                "normalized_distance": float,  # 0.0-1.0+
                "angle_deg": float      # 0-360
            }
        """
        dx = x - center_x
        dy = y - center_y
        distance = math.hypot(dx, dy)
        norm_dist = distance / radius_px if radius_px > 0 else 999.0

        # atan2(dy, dx) gives 0° at 3 o'clock.
        # We want 0° at 12 o'clock (top), clockwise positive.
        # Rotation: subtract 90° (or add 270°), then add sector_offset
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        # +90 rotates so 0° is at top (12 o'clock), sector_offset shifts
        # to align with sector boundaries (20 sector centered at top)
        adjusted_angle = (angle_deg + 90 + self.sector_offset_deg) % 360

        sector_index = int(adjusted_angle / self.sector_angle_deg) % 20
        sector_value = self.SECTOR_ORDER[sector_index]

        # Determine ring using calibrated radii
        r = self.ring_radii
        if norm_dist <= r["bull_inner"]:
            return self._result(50, 50, 1, "inner_bull", norm_dist, adjusted_angle)
        elif norm_dist <= r["bull_outer"]:
            return self._result(25, 25, 1, "outer_bull", norm_dist, adjusted_angle)
        elif norm_dist <= r["triple_inner"]:
            return self._result(sector_value, sector_value, 1, "single", norm_dist, adjusted_angle)
        elif norm_dist <= r["triple_outer"]:
            return self._result(sector_value * 3, sector_value, 3, "triple", norm_dist, adjusted_angle)
        elif norm_dist <= r["double_inner"]:
            return self._result(sector_value, sector_value, 1, "single", norm_dist, adjusted_angle)
        elif norm_dist <= r["double_outer"]:
            return self._result(sector_value * 2, sector_value, 2, "double", norm_dist, adjusted_angle)
        else:
            return self._result(0, 0, 0, "miss", norm_dist, adjusted_angle)

    def _result(self, score: int, sector: int, multiplier: int, ring: str,
                norm_dist: float, angle: float) -> dict:
        return {
            "score": score,
            "sector": sector,
            "multiplier": multiplier,
            "ring": ring,
            "normalized_distance": round(norm_dist, 4),
            "angle_deg": round(angle, 2),
        }
