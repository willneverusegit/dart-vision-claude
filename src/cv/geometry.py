"""Shared geometry models and coordinate transforms for board-centric scoring."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import numpy as np


_DEFAULT_RADII_PX = (10.0, 19.0, 106.0, 116.0, 188.0, 200.0)


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
