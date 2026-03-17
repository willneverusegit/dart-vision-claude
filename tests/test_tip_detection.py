"""Tests for dart tip detection algorithm."""

import numpy as np
import cv2
import pytest

from src.cv.tip_detection import find_dart_tip, _refine_subpixel


class TestFindDartTip:
    """Test tip detection with synthetic dart-shaped contours."""

    def _make_dart_contour(
        self,
        tip_x: int, tip_y: int,
        flight_x: int, flight_y: int,
        tip_width: int = 4,
        flight_width: int = 30,
        num_points: int = 40,
    ) -> np.ndarray:
        """Create a synthetic dart-shaped contour (narrow at tip, wide at flights).

        Generates a tapered polygon from (tip_x, tip_y) to (flight_x, flight_y).
        """
        # Direction vector from tip to flight
        dx = flight_x - tip_x
        dy = flight_y - tip_y
        length = np.sqrt(dx**2 + dy**2)
        if length == 0:
            return np.array([[[tip_x, tip_y]]], dtype=np.int32)

        # Unit vectors along and perpendicular to dart axis
        ax = dx / length
        ay = dy / length
        px = -ay  # perpendicular
        py = ax

        # Build points along one side (tip → flight) then back along the other
        half = num_points // 2
        top_points = []
        bottom_points = []

        for i in range(half):
            t = i / (half - 1)  # 0..1 from tip to flight
            cx = tip_x + t * dx
            cy = tip_y + t * dy
            # Width interpolates from tip_width to flight_width
            w = tip_width + t * (flight_width - tip_width)
            top_points.append([int(cx + px * w / 2), int(cy + py * w / 2)])
            bottom_points.append([int(cx - px * w / 2), int(cy - py * w / 2)])

        # Contour: top side tip→flight, then bottom side flight→tip
        all_points = top_points + bottom_points[::-1]
        return np.array(all_points, dtype=np.int32).reshape(-1, 1, 2)

    def test_horizontal_dart_tip_on_left(self):
        """Dart pointing left: tip at (50,200), flights at (200,200)."""
        contour = self._make_dart_contour(50, 200, 200, 200)
        tip = find_dart_tip(contour)
        assert tip is not None
        # Tip should be near (50, 200), not near (200, 200)
        assert abs(tip[0] - 50) < 20, f"tip x={tip[0]} too far from expected 50"
        assert abs(tip[1] - 200) < 20, f"tip y={tip[1]} too far from expected 200"

    def test_horizontal_dart_tip_on_right(self):
        """Dart pointing right: tip at (300,150), flights at (100,150)."""
        contour = self._make_dart_contour(300, 150, 100, 150)
        tip = find_dart_tip(contour)
        assert tip is not None
        assert abs(tip[0] - 300) < 20, f"tip x={tip[0]} too far from expected 300"

    def test_diagonal_dart(self):
        """Dart at ~45 degrees: tip at (50,50), flights at (200,200)."""
        contour = self._make_dart_contour(50, 50, 200, 200)
        tip = find_dart_tip(contour)
        assert tip is not None
        assert abs(tip[0] - 50) < 25, f"tip x={tip[0]} too far from expected 50"
        assert abs(tip[1] - 50) < 25, f"tip y={tip[1]} too far from expected 50"

    def test_vertical_dart(self):
        """Dart pointing upward: tip at (200,30), flights at (200,180)."""
        contour = self._make_dart_contour(200, 30, 200, 180)
        tip = find_dart_tip(contour)
        assert tip is not None
        assert abs(tip[1] - 30) < 20, f"tip y={tip[1]} too far from expected 30"

    def test_steep_angle_dart(self):
        """Dart at steep angle: tip at (100,50), flights at (150,250)."""
        contour = self._make_dart_contour(100, 50, 150, 250)
        tip = find_dart_tip(contour)
        assert tip is not None
        assert abs(tip[0] - 100) < 25
        assert abs(tip[1] - 50) < 25

    def test_contour_too_small(self):
        """Should return None for tiny contours."""
        small = np.array([[[0, 0]], [[1, 0]], [[1, 1]]], dtype=np.int32)
        assert find_dart_tip(small) is None

    def test_none_contour(self):
        """Should return None for None input."""
        assert find_dart_tip(None) is None

    def test_tip_is_not_centroid(self):
        """Tip should be significantly different from centroid for elongated darts."""
        contour = self._make_dart_contour(50, 200, 250, 200, tip_width=4, flight_width=40)
        tip = find_dart_tip(contour)
        assert tip is not None

        # Centroid would be roughly at the center of mass (~150, 200)
        M = cv2.moments(contour)
        cx = int(M["m10"] / M["m00"])

        # Tip should be much closer to x=50 than centroid
        assert abs(tip[0] - 50) < abs(cx - 50), (
            f"Tip ({tip[0]}) should be closer to 50 than centroid ({cx})"
        )

    def test_subpixel_refinement_with_gray_frame(self):
        """When gray_frame is passed, sub-pixel refinement runs without error."""
        # Create a gray image with a sharp edge feature at the tip location
        gray = np.zeros((400, 400), dtype=np.uint8)
        gray[180:220, 40:60] = 200  # bright region near tip

        contour = self._make_dart_contour(50, 200, 250, 200)
        tip = find_dart_tip(contour, gray_frame=gray)
        assert tip is not None
        # Should still be near the expected tip position
        assert abs(tip[0] - 50) < 25

    def test_subpixel_refinement_without_gray_frame(self):
        """Without gray_frame, function works as before (no refinement)."""
        contour = self._make_dart_contour(50, 200, 250, 200)
        tip_no_gray = find_dart_tip(contour, gray_frame=None)
        tip_default = find_dart_tip(contour)
        assert tip_no_gray == tip_default


class TestRefineSubpixel:
    """Test the sub-pixel refinement helper directly."""

    def test_returns_original_on_blank_image(self):
        """On a uniform image with no corners, returns original position."""
        gray = np.full((100, 100), 128, dtype=np.uint8)
        rx, ry = _refine_subpixel(gray, 50, 50)
        # Should not crash; may return original or nearby
        assert 40 <= rx <= 60
        assert 40 <= ry <= 60

    def test_returns_original_on_edge_position(self):
        """Tip near image border should not crash."""
        gray = np.full((100, 100), 128, dtype=np.uint8)
        rx, ry = _refine_subpixel(gray, 2, 2, win=10)
        assert rx >= 0 and ry >= 0

    def test_refines_near_sharp_corner(self):
        """On an image with a clear corner, refinement should succeed."""
        gray = np.zeros((100, 100), dtype=np.uint8)
        # Create a clear L-shaped corner at (50, 50)
        gray[50:80, 50:80] = 200
        rx, ry = _refine_subpixel(gray, 52, 52, win=10)
        # Should be close to the actual corner
        assert abs(rx - 50) < 5
        assert abs(ry - 50) < 5
