"""P25 — Validate that tip-based scoring beats centroid-based scoring.

A dart contour is widest at flights, narrowest at tip. The centroid sits
~28-40px toward the flights from the tip. Near segment boundaries this
offset is enough to land in the wrong segment. Tip detection should
produce the correct score more often.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from src.cv.geometry import BoardGeometry
from src.cv.tip_detection import find_dart_tip


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def geo() -> BoardGeometry:
    return BoardGeometry(
        roi_size=(400, 400),
        center_px=(200.0, 200.0),
        optical_center_px=(200.0, 200.0),
        radii_px=(10.0, 19.0, 106.0, 116.0, 188.0, 200.0),
        rotation_deg=0.0,
        valid=True,
    )


def _make_dart_contour(
    tip_x: float,
    tip_y: float,
    flight_x: float,
    flight_y: float,
    tip_width: int = 4,
    flight_width: int = 30,
    num_points: int = 40,
) -> np.ndarray:
    dx, dy = flight_x - tip_x, flight_y - tip_y
    length = math.hypot(dx, dy)
    ax, ay = dx / length, dy / length
    px, py = -ay, ax
    half = num_points // 2
    top, bottom = [], []
    for i in range(half):
        t = i / (half - 1)
        cx = tip_x + t * dx
        cy = tip_y + t * dy
        w = tip_width + t * (flight_width - tip_width)
        top.append([int(cx + px * w / 2), int(cy + py * w / 2)])
        bottom.append([int(cx - px * w / 2), int(cy - py * w / 2)])
    return np.array(top + bottom[::-1], dtype=np.int32).reshape(-1, 1, 2)


def _centroid(contour: np.ndarray) -> tuple[float, float]:
    m = cv2.moments(contour)
    if m["m00"] == 0:
        pts = contour.reshape(-1, 2)
        return float(pts[:, 0].mean()), float(pts[:, 1].mean())
    return m["m10"] / m["m00"], m["m01"] / m["m00"]


def _pos_from_angle_radius(angle_deg: float, radius_px: float, cx: float = 200.0, cy: float = 200.0):
    """Convert board angle (0=up, clockwise) + radius to pixel coords."""
    # Board angle 0 = up (-Y). Convert to math angle.
    math_angle = math.radians(angle_deg - 90.0)
    x = cx + radius_px * math.cos(math_angle)
    y = cy + radius_px * math.sin(math_angle)
    return x, y


def _flight_pos(tip_x, tip_y, angle_deg, dart_length=100.0, cx=200.0, cy=200.0):
    """Return flight position: flights point AWAY from tip along the radial direction outward."""
    # Direction from center to tip
    dx, dy = tip_x - cx, tip_y - cy
    dist = math.hypot(dx, dy)
    if dist < 1:
        # For bull, use angle to determine direction
        math_angle = math.radians(angle_deg - 90.0)
        dx, dy = math.cos(math_angle), math.sin(math_angle)
        dist = 1.0
    # Flights point outward (away from center) by default
    ux, uy = dx / dist, dy / dist
    return tip_x + ux * dart_length, tip_y + uy * dart_length


def _flight_pos_inward(tip_x, tip_y, dart_length=100.0, cx=200.0, cy=200.0):
    """Flights pointing toward center (inward)."""
    dx, dy = cx - tip_x, cy - tip_y
    dist = math.hypot(dx, dy)
    ux, uy = dx / dist, dy / dist
    return tip_x + ux * dart_length, tip_y + uy * dart_length


# ---------------------------------------------------------------------------
# Individual test cases
# ---------------------------------------------------------------------------

class TestTipVsCentroidScoring:
    """Each test places a dart near a segment boundary where the centroid
    offset causes a mis-score but the tip stays correct."""

    def test_triple20_flights_outward(self, geo: BoardGeometry):
        """Tip in Triple-20, flights outward → centroid lands in Single-20."""
        # Scoring uses mm-based normalization: triple = 99-107mm / 170mm * 200px = 116.5-125.9px.
        # Place tip at inner edge of triple (r=118).
        # Angle 0° = sector 20.
        tip_x, tip_y = _pos_from_angle_radius(0.0, 118.0)
        fx, fy = _flight_pos(tip_x, tip_y, 0.0, dart_length=100)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.ring == "triple", f"tip should be triple, got {tip_hit.ring}"
        assert tip_hit.sector == 20
        # Centroid should have drifted out of triple
        assert cent_hit.ring != "triple", f"centroid unexpectedly still in triple"

    def test_double16_flights_inward(self, geo: BoardGeometry):
        """Tip in Double-16, flights inward → centroid lands in Single-16."""
        # Double ring: 188-200px. Sector 16 is at index 13 → angle = 13*18 = 234°.
        tip_x, tip_y = _pos_from_angle_radius(234.0, 194.0)
        fx, fy = _flight_pos_inward(tip_x, tip_y, dart_length=100)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.ring == "double", f"tip should be double, got {tip_hit.ring}"
        assert tip_hit.sector == 16
        assert cent_hit.ring != "double", f"centroid unexpectedly still in double"

    def test_bull_flights_outward(self, geo: BoardGeometry):
        """Tip near outer bull, flights pointing away → centroid misses bull."""
        # Outer bull: 10-19px from center. Place tip at r=15.
        tip_x, tip_y = _pos_from_angle_radius(45.0, 15.0)
        fx, fy = _flight_pos(tip_x, tip_y, 45.0, dart_length=100)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.ring in ("outer_bull", "inner_bull"), f"tip should be bull, got {tip_hit.ring}"
        assert cent_hit.ring not in ("outer_bull", "inner_bull"), f"centroid unexpectedly in bull"

    def test_sector_boundary_20_1(self, geo: BoardGeometry):
        """Tip on 20-side of 20/1 boundary, centroid drifts into sector 1."""
        # Boundary between 20 and 1 is at 9°. Place tip at 7° (just inside 20).
        # Flights pointing tangentially clockwise so centroid drifts past 9°.
        r = 150.0  # single area
        tip_x, tip_y = _pos_from_angle_radius(7.0, r)
        # Point flights tangentially clockwise (increasing angle)
        fx, fy = _pos_from_angle_radius(35.0, r + 30)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.sector == 20, f"tip sector should be 20, got {tip_hit.sector}"
        assert cent_hit.sector == 1, f"centroid sector should be 1, got {cent_hit.sector}"

    def test_triple19_flights_outward(self, geo: BoardGeometry):
        """Tip in Triple-19, flights outward → centroid in Single-19."""
        # Sector 19 at index 11 → angle = 11*18 = 198°.
        tip_x, tip_y = _pos_from_angle_radius(198.0, 118.0)
        fx, fy = _flight_pos(tip_x, tip_y, 198.0, dart_length=100)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.ring == "triple"
        assert tip_hit.sector == 19
        assert cent_hit.ring != "triple"

    def test_double3_flights_inward(self, geo: BoardGeometry):
        """Tip in Double-3, flights inward → centroid in Single-3."""
        # Sector 3 at index 10 → angle = 10*18 = 180°.
        tip_x, tip_y = _pos_from_angle_radius(180.0, 194.0)
        fx, fy = _flight_pos_inward(tip_x, tip_y, dart_length=100)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.ring == "double"
        assert tip_hit.sector == 3
        assert cent_hit.ring != "double"

    def test_sector_boundary_6_13(self, geo: BoardGeometry):
        """Tip on 6-side of 6/13 boundary, centroid drifts into 13."""
        # Sector 6: index 5, center 90°, spans 81°-99°.
        # Sector 13: index 4, center 72°, spans 63°-81°.
        # Boundary at 81°. Place tip at 83° (just inside 6), flights toward ~55°.
        r = 150.0
        tip_x, tip_y = _pos_from_angle_radius(83.0, r)
        fx, fy = _pos_from_angle_radius(55.0, r + 30)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.sector == 6, f"tip sector should be 6, got {tip_hit.sector}"
        assert cent_hit.sector == 13, f"centroid sector should be 13, got {cent_hit.sector}"

    def test_triple6_flights_outward(self, geo: BoardGeometry):
        """Tip in Triple-6, flights outward."""
        tip_x, tip_y = _pos_from_angle_radius(90.0, 118.0)
        fx, fy = _flight_pos(tip_x, tip_y, 90.0, dart_length=100)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.ring == "triple"
        assert tip_hit.sector == 6
        assert cent_hit.ring != "triple"

    def test_inner_bull_flights_outward(self, geo: BoardGeometry):
        """Tip near inner bull (r=5), flights outward → centroid outside bull entirely."""
        tip_x, tip_y = _pos_from_angle_radius(270.0, 5.0)
        fx, fy = _flight_pos(tip_x, tip_y, 270.0, dart_length=100)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.ring == "inner_bull"
        assert cent_hit.ring not in ("inner_bull", "outer_bull")

    def test_double11_flights_inward(self, geo: BoardGeometry):
        """Tip in Double-11, flights inward."""
        # Sector 11 at index 15 → angle = 15*18 = 270°.
        tip_x, tip_y = _pos_from_angle_radius(270.0, 194.0)
        fx, fy = _flight_pos_inward(tip_x, tip_y, dart_length=100)
        contour = _make_dart_contour(tip_x, tip_y, fx, fy)

        tip = find_dart_tip(contour)
        assert tip is not None
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        assert tip_hit.ring == "double"
        assert tip_hit.sector == 11
        assert cent_hit.ring != "double"


# ---------------------------------------------------------------------------
# Parametrized summary: tip accuracy >= centroid accuracy
# ---------------------------------------------------------------------------

_SCENARIOS = [
    # (angle_deg, radius_px, dart_direction, expected_ring, expected_sector)
    # "outward" = flights point away from center, "inward" = toward center
    # "tangent_cw" = flights tangent clockwise
    (0.0, 118.0, "outward", "triple", 20),
    (198.0, 118.0, "outward", "triple", 19),
    (90.0, 118.0, "outward", "triple", 6),
    (342.0, 118.0, "outward", "triple", 5),
    (234.0, 194.0, "inward", "double", 16),
    (180.0, 194.0, "inward", "double", 3),
    (270.0, 194.0, "inward", "double", 11),
    (36.0, 194.0, "inward", "double", 18),
    (45.0, 15.0, "outward", "outer_bull", 25),
    (270.0, 5.0, "outward", "inner_bull", 25),
]


@pytest.mark.parametrize("angle,radius,direction,exp_ring,exp_sector", _SCENARIOS)
def test_tip_scores_correctly(geo, angle, radius, direction, exp_ring, exp_sector):
    """Each scenario: tip-based score matches expected segment."""
    tip_x, tip_y = _pos_from_angle_radius(angle, radius)
    if direction == "outward":
        fx, fy = _flight_pos(tip_x, tip_y, angle, dart_length=100)
    elif direction == "inward":
        fx, fy = _flight_pos_inward(tip_x, tip_y, dart_length=100)
    else:
        raise ValueError(direction)

    contour = _make_dart_contour(tip_x, tip_y, fx, fy)
    tip = find_dart_tip(contour)
    assert tip is not None, "tip detection failed"

    hit = geo.point_to_score(float(tip[0]), float(tip[1]))
    assert hit.ring == exp_ring, f"expected ring {exp_ring}, got {hit.ring}"
    if exp_sector != 25:
        assert hit.sector == exp_sector, f"expected sector {exp_sector}, got {hit.sector}"


def test_tip_accuracy_beats_centroid(geo):
    """Aggregate: tip-based scoring is more accurate than centroid across all scenarios."""
    tip_correct = 0
    cent_correct = 0

    for angle, radius, direction, exp_ring, exp_sector in _SCENARIOS:
        tip_x, tip_y = _pos_from_angle_radius(angle, radius)
        if direction == "outward":
            fx, fy = _flight_pos(tip_x, tip_y, angle, dart_length=100)
        elif direction == "inward":
            fx, fy = _flight_pos_inward(tip_x, tip_y, dart_length=100)
        else:
            continue

        contour = _make_dart_contour(tip_x, tip_y, fx, fy)
        tip = find_dart_tip(contour)
        if tip is None:
            continue
        cx, cy = _centroid(contour)

        tip_hit = geo.point_to_score(float(tip[0]), float(tip[1]))
        cent_hit = geo.point_to_score(cx, cy)

        if tip_hit.ring == exp_ring and (exp_sector == 25 or tip_hit.sector == exp_sector):
            tip_correct += 1
        if cent_hit.ring == exp_ring and (exp_sector == 25 or cent_hit.sector == exp_sector):
            cent_correct += 1

    assert tip_correct >= cent_correct, (
        f"tip accuracy ({tip_correct}/{len(_SCENARIOS)}) should be >= "
        f"centroid accuracy ({cent_correct}/{len(_SCENARIOS)})"
    )
    # Tip should get at least 80% right
    assert tip_correct >= len(_SCENARIOS) * 0.8, (
        f"tip accuracy too low: {tip_correct}/{len(_SCENARIOS)}"
    )
