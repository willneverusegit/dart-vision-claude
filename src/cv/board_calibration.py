"""Board pose calibration manager (separate from lens/intrinsics calibration)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np

from src.cv.calibration import CalibrationManager
from src.cv.geometry import BoardGeometry, BoardPose

logger = logging.getLogger(__name__)


class BoardCalibrationManager:
    """Manage board alignment (homography, radii, optical center, rotation)."""

    def __init__(self, config_path: str = "config/calibration_config.yaml",
                 roi_size: tuple[int, int] = (400, 400),
                 camera_id: str = "default") -> None:
        self._legacy = CalibrationManager(config_path=config_path, camera_id=camera_id)
        self.config_path = config_path
        self.roi_size = roi_size
        self.camera_id = camera_id

    def get_config(self) -> dict:
        return self._legacy.get_config()

    def get_pose(self) -> BoardPose:
        return BoardPose.from_config(self._legacy.get_config())

    def get_geometry(self) -> BoardGeometry:
        return BoardGeometry.from_pose(self.get_pose(), self.roi_size)

    def is_valid(self) -> bool:
        return self.get_pose().valid

    def get_homography(self) -> np.ndarray | None:
        return self._legacy.get_homography()

    def get_radii_px(self) -> list[float]:
        return self._legacy.get_radii_px()

    def get_optical_center(self) -> tuple[float, float] | None:
        return self._legacy.get_optical_center()

    def manual_calibration(self, board_points: list[list[float]], roi_size: tuple[int, int] | None = None) -> dict:
        size = roi_size or self.roi_size
        result = self._legacy.manual_calibration(board_points, roi_size=size)
        if result.get("ok"):
            cfg = self._legacy._config
            cfg["schema_version"] = int(cfg.get("schema_version", 1)) if cfg.get("schema_version") else 2
            self._legacy._atomic_save()
        return result

    def aruco_calibration(
        self,
        frame: np.ndarray,
        expected_ids: list[int] | None = None,
        marker_spacing_mm: float | None = None,
        roi_size: tuple[int, int] | None = None,
        marker_size_mm: float | None = None,
    ) -> dict:
        kwargs = {}
        if expected_ids is not None:
            kwargs["expected_ids"] = expected_ids
        if marker_spacing_mm is not None:
            kwargs["marker_spacing_mm"] = marker_spacing_mm
        if marker_size_mm is not None:
            kwargs["marker_size_mm"] = marker_size_mm
        size = roi_size or self.roi_size
        result = self._legacy.aruco_calibration(frame, roi_size=size, **kwargs)
        if result.get("ok"):
            cfg = self._legacy._config
            cfg["schema_version"] = int(cfg.get("schema_version", 1)) if cfg.get("schema_version") else 2
            self._legacy._atomic_save()
        return result

    def verify_rings(self, frame: np.ndarray) -> dict:
        return self._legacy.verify_rings(frame)

    def find_optical_center(self, roi_frame: np.ndarray, search_radius_mm: float = 10.0) -> tuple[float, float]:
        return self._legacy.find_optical_center(roi_frame, search_radius_mm=search_radius_mm)

    def store_optical_center(self, optical_center: tuple[float, float]) -> None:
        cfg = self._legacy._config
        cfg["optical_center_roi_px"] = [float(optical_center[0]), float(optical_center[1])]
        cfg["last_update_utc"] = datetime.now(timezone.utc).isoformat()
        cfg["schema_version"] = int(cfg.get("schema_version", 1)) if cfg.get("schema_version") else 2
        self._legacy._atomic_save()
        logger.info("Board optical center persisted: (%.2f, %.2f)", optical_center[0], optical_center[1])

    def get_viewing_angle_quality(self) -> float:
        """Compute viewing angle quality from homography determinant.

        Frontal view = 1.0, steep angle = 0.3-0.7.
        Returns 0.0 if no valid calibration.
        """
        import math
        H = self.get_homography()
        if H is None:
            return 0.0
        det = abs(np.linalg.det(H))
        if det <= 0:
            return 0.0
        log_det = math.log10(det)
        # Map log_det from [-2, 2] to [0.3, 1.0]
        quality = 0.3 + 0.7 * max(0.0, min(1.0, (log_det + 2.0) / 4.0))
        return round(quality, 3)

    def has_valid_intrinsics(self) -> bool:
        """Check if this camera has valid lens intrinsics (camera_matrix)."""
        from src.cv.camera_calibration import CameraCalibrationManager
        cam_cal = CameraCalibrationManager(camera_id=self.camera_id)
        intr = cam_cal.get_intrinsics()
        if intr is None:
            return False
        if not hasattr(intr, 'camera_matrix') or intr.camera_matrix is None:
            return False
        if intr.camera_matrix.shape != (3, 3):
            return False
        return True
