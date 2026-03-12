"""Shared geometry models and coordinate transforms for board-centric scoring."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, NamedTuple

import numpy as np


_DEFAULT_RADII_PX = (10.0, 19.0, 106.0, 116.0, 188.0, 200.0)


# ---------------------------------------------------------------------------
# New types for unified scoring (Release 0.3)
# ---------------------------------------------------------------------------

class PolarCoord(NamedTuple):
    """Normalized polar coordinate on the dartboard."""
    r_norm: float   # 0.0 = center, 1.0 = double-ring outer edge
    theta_deg: float  # 0-360, 0 deg = 12 o'clock, clockwise


@dataclass(frozen=True)
class BoardHit:
    """Complete result of mapping a point to a dartboard score."""
    score: int          # Total points (e.g. 60 for T20, 50 for Bull)
    sector: int         # Base sector value (1-20, or 25 for Bull)
    multiplier: int     # 1, 2, 3 (0 for miss)
    ring: str           # "inner_bull", "outer_bull", "single", "triple", "double", "miss"
    polar: PolarCoord   # Normalized polar position
    board_mm: tuple[float, float]  # (x_mm, y_mm) from board center
    roi_x: float        # Original ROI pixel x
    roi_y: float        # Original ROI pixel y


# Physical dimensions in mm (from center) — WDF/BDO/PDC Standard
BULL_INNER_MM = 6.35
BULL_OUTER_MM = 15.9
TRIPLE_INNER_MM = 99.0
TRIPLE_OUTER_MM = 107.0
DOUBLE_INNER_MM = 162.0
DOUBLE_OUTER_MM = 170.0
BOARD_RADIUS_MM = DOUBLE_OUTER_MM  # 170mm

# Normalized ring boundaries (relative to BOARD_RADIUS_MM)
RING_BOUNDARIES: tuple[tuple[float, float, str, int, int | None], ...] = (
    # (inner_norm, outer_norm, name, multiplier, flat_score_or_None)
    (0.0, BULL_INNER_MM / BOARD_RADIUS_MM, "inner_bull", 1, 50),
    (BULL_INNER_MM / BOARD_RADIUS_MM, BULL_OUTER_MM / BOARD_RADIUS_MM, "outer_bull", 1, 25),
    (BULL_OUTER_MM / BOARD_RADIUS_MM, TRIPLE_INNER_MM / BOARD_RADIUS_MM, "single", 1, None),
    (TRIPLE_INNER_MM / BOARD_RADIUS_MM, TRIPLE_OUTER_MM / BOARD_RADIUS_MM, "triple", 3, None),
    (TRIPLE_OUTER_MM / BOARD_RADIUS_MM, DOUBLE_INNER_MM / BOARD_RADIUS_MM, "single", 1, None),
    (DOUBLE_INNER_MM / BOARD_RADIUS_MM, DOUBLE_OUTER_MM / BOARD_RADIUS_MM, "double", 2, None),
)

SECTOR_ORDER: tuple[int, ...] = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                                  3, 19, 7, 16, 8, 11, 14, 9, 12, 5)
SECTOR_COUNT = 20
SECTOR_ANGLE_DEG = 360.0 / SECTOR_COUNT  # 18 deg
SECTOR_HALF_WIDTH_DEG = SECTOR_ANGLE_DEG / 2.0  # 9 deg


@dataclass
class CameraIntrinsics:
    """Intrinsic camera model used by combined remapping."""

    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    valid: bool = False
    method: str | None = None
    image_size: tuple[int, int] | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "CameraIntrinsics | None":
        """Build intrinsics from persisted config if available."""
        matrix = config.get("camera_matrix")
        dist = config.get("dist_coeffs")
        valid = bool(config.get("lens_valid", False))
        if matrix is None or dist is None:
            return None
        try:
            return cls(
                camera_matrix=np.array(matrix, dtype=np.float64).reshape(3, 3),
                dist_coeffs=np.array(dist, dtype=np.float64).reshape(-1, 1),
                valid=valid,
                method=config.get("lens_method"),
                image_size=tuple(config.get("lens_image_size", ())) or None,
            )
        except Exception:
            return None

    def to_config_fragment(self) -> dict[str, Any]:
        """Serialize camera model back into config-compatible values."""
        return {
            "camera_matrix": self.camera_matrix.tolist(),
            "dist_coeffs": self.dist_coeffs.reshape(-1).tolist(),
            "lens_valid": bool(self.valid),
            "lens_method": self.method,
            "lens_image_size": list(self.image_size) if self.image_size else None,
        }


@dataclass
class BoardPose:
    """Board-to-ROI pose and dimensions persisted by board calibration."""

    homography: np.ndarray | None
    center_px: tuple[float, float]
    radii_px: tuple[float, float, float, float, float, float]
    rotation_deg: float = 0.0
    optical_center_roi_px: tuple[float, float] | None = None
    valid: bool = False
    method: str | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "BoardPose":
        """Build board pose from calibration config."""
        center = config.get("center_px", [200.0, 200.0])
        radii = config.get("radii_px", list(_DEFAULT_RADII_PX))
        optical = config.get("optical_center_roi_px")
        homography_raw = config.get("homography")
        homography = None
        if homography_raw is not None:
            try:
                homography = np.array(homography_raw, dtype=np.float64).reshape(3, 3)
            except Exception:
                homography = None
        return cls(
            homography=homography,
            center_px=(float(center[0]), float(center[1])),
            radii_px=tuple(float(r) for r in radii[:6]) if len(radii) >= 6 else _DEFAULT_RADII_PX,
            rotation_deg=float(config.get("rotation_deg", 0.0)),
            optical_center_roi_px=(
                (float(optical[0]), float(optical[1]))
                if isinstance(optical, (list, tuple)) and len(optical) == 2
                else None
            ),
            valid=bool(config.get("valid", False)),
            method=config.get("method"),
        )

    def to_config_fragment(self) -> dict[str, Any]:
        """Serialize board pose for config persistence."""
        payload: dict[str, Any] = {
            "center_px": [self.center_px[0], self.center_px[1]],
            "radii_px": list(self.radii_px),
            "rotation_deg": float(self.rotation_deg),
            "valid": bool(self.valid),
            "method": self.method,
        }
        if self.homography is not None:
            payload["homography"] = self.homography.tolist()
        if self.optical_center_roi_px is not None:
            payload["optical_center_roi_px"] = [
                self.optical_center_roi_px[0],
                self.optical_center_roi_px[1],
            ]
        return payload


@dataclass
class BoardGeometry:
    """Canonical geometry used by scoring, overlays, APIs and UI rendering."""

    roi_size: tuple[int, int]
    center_px: tuple[float, float]
    optical_center_px: tuple[float, float]
    radii_px: tuple[float, float, float, float, float, float]
    rotation_deg: float = 0.0
    valid: bool = False
    method: str | None = None

    @classmethod
    def from_pose(cls, pose: BoardPose, roi_size: tuple[int, int]) -> "BoardGeometry":
        """Promote persisted board pose to runtime geometry."""
        optical = pose.optical_center_roi_px or pose.center_px
        return cls(
            roi_size=roi_size,
            center_px=pose.center_px,
            optical_center_px=optical,
            radii_px=pose.radii_px,
            rotation_deg=pose.rotation_deg,
            valid=pose.valid,
            method=pose.method,
        )

    @property
    def double_outer_radius_px(self) -> float:
        """Radius of the board scoring boundary in ROI pixels."""
        return float(self.radii_px[5]) if len(self.radii_px) >= 6 else 1.0

    def normalize_point(self, x_px: float, y_px: float) -> tuple[float, float]:
        """Convert ROI pixel coordinates to board-normalized XY coordinates."""
        radius = self.double_outer_radius_px
        if radius <= 0:
            return (0.0, 0.0)
        ox, oy = self.optical_center_px
        return ((x_px - ox) / radius, (y_px - oy) / radius)

    def point_to_polar(self, x_px: float, y_px: float) -> tuple[float, float]:
        """Return (radius_norm, angle_deg) in board space.

        Angle convention:
        - 0 deg at 12 o'clock
        - clockwise positive
        - includes configured board rotation offset
        """
        nx, ny = self.normalize_point(x_px, y_px)
        radius_norm = math.hypot(nx, ny)
        angle_deg = (math.degrees(math.atan2(ny, nx)) + 90.0 + self.rotation_deg) % 360.0
        return (radius_norm, angle_deg)

    def point_to_score(self, x_px: float, y_px: float) -> BoardHit:
        """Convert ROI pixel coordinates to a BoardHit.

        This is the ONLY function external modules should call for scoring.
        """
        radius = self.double_outer_radius_px
        if radius <= 0:
            return BoardHit(
                score=0, sector=0, multiplier=0, ring="miss",
                polar=PolarCoord(0.0, 0.0), board_mm=(0.0, 0.0),
                roi_x=x_px, roi_y=y_px,
            )

        ox, oy = self.optical_center_px
        dx = x_px - ox
        dy = y_px - oy
        distance_px = math.hypot(dx, dy)
        r_norm = distance_px / radius

        # Angle: 0 deg at 12 o'clock, clockwise
        angle_deg = (math.degrees(math.atan2(dy, dx)) + 90.0 + self.rotation_deg) % 360.0
        polar = PolarCoord(r_norm=r_norm, theta_deg=angle_deg)

        # mm calculation (use physical proportions)
        mm_per_px = BOARD_RADIUS_MM / radius
        board_mm = (dx * mm_per_px, dy * mm_per_px)

        # Ring classification
        ring_name = "miss"
        multiplier = 0
        flat_score: int | None = None
        for inner, outer, name, mult, flat in RING_BOUNDARIES:
            if inner <= r_norm < outer:
                ring_name = name
                multiplier = mult
                flat_score = flat
                break

        if multiplier == 0:
            return BoardHit(
                score=0, sector=0, multiplier=0, ring="miss",
                polar=polar, board_mm=board_mm, roi_x=x_px, roi_y=y_px,
            )

        if flat_score is not None:
            return BoardHit(
                score=flat_score, sector=25, multiplier=1, ring=ring_name,
                polar=polar, board_mm=board_mm, roi_x=x_px, roi_y=y_px,
            )

        # Sector classification
        adjusted = (angle_deg + SECTOR_HALF_WIDTH_DEG) % 360.0
        sector_index = int(adjusted / SECTOR_ANGLE_DEG) % SECTOR_COUNT
        sector_value = SECTOR_ORDER[sector_index]

        return BoardHit(
            score=sector_value * multiplier,
            sector=sector_value,
            multiplier=multiplier,
            ring=ring_name,
            polar=polar,
            board_mm=board_mm,
            roi_x=x_px,
            roi_y=y_px,
        )

    def hit_to_dict(self, hit: BoardHit) -> dict:
        """Convert BoardHit to legacy dict format for API/WebSocket compatibility."""
        return {
            "score": hit.score,
            "sector": hit.sector,
            "multiplier": hit.multiplier,
            "ring": hit.ring,
            "normalized_distance": round(hit.polar.r_norm, 4),
            "angle_deg": round(hit.polar.theta_deg, 2),
            "roi_x": hit.roi_x,
            "roi_y": hit.roi_y,
            "board_x_norm": round(hit.board_mm[0] / BOARD_RADIUS_MM, 4) if BOARD_RADIUS_MM > 0 else 0.0,
            "board_y_norm": round(hit.board_mm[1] / BOARD_RADIUS_MM, 4) if BOARD_RADIUS_MM > 0 else 0.0,
            "polar_radius_norm": round(hit.polar.r_norm, 4),
            "polar_angle_deg": round(hit.polar.theta_deg, 2),
        }

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize geometry for web clients."""
        return {
            "valid": bool(self.valid),
            "method": self.method,
            "roi_size": [self.roi_size[0], self.roi_size[1]],
            "center_px": [self.center_px[0], self.center_px[1]],
            "optical_center_px": [self.optical_center_px[0], self.optical_center_px[1]],
            "rotation_deg": float(self.rotation_deg),
            "radii_px": list(self.radii_px),
            "double_outer_radius_px": self.double_outer_radius_px,
        }
