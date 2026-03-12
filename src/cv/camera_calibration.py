"""Lens/intrinsics calibration manager (separate from board pose calibration)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import cv2
import numpy as np

from src.cv.calibration import CalibrationManager
from src.cv.geometry import CameraIntrinsics

logger = logging.getLogger(__name__)


class CameraCalibrationManager:
    """Manage lens calibration (camera matrix + distortion coefficients)."""

    def __init__(self, config_path: str = "config/calibration_config.yaml") -> None:
        # Reuse the existing atomic config loader/saver so both managers share one file.
        self._config_io = CalibrationManager(config_path=config_path)
        self.config_path = config_path

    def get_config(self) -> dict:
        return self._config_io.get_config()

    def has_intrinsics(self) -> bool:
        cfg = self._config_io.get_config()
        return bool(cfg.get("lens_valid", False) and cfg.get("camera_matrix") and cfg.get("dist_coeffs"))

    def get_intrinsics(self) -> CameraIntrinsics | None:
        return CameraIntrinsics.from_config(self._config_io.get_config())

    def charuco_calibration(
        self,
        frames: list[np.ndarray],
        squares_x: int = 7,
        squares_y: int = 5,
        square_length: float = 0.04,
        marker_length: float = 0.02,
    ) -> dict:
        """Estimate camera intrinsics from multiple ChArUco board frames."""
        try:
            if len(frames) < 3:
                return {"ok": False, "error": f"Need at least 3 frames, got {len(frames)}"}

            dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
            board = cv2.aruco.CharucoBoard(
                (squares_x, squares_y), square_length, marker_length, dictionary
            )
            detector = cv2.aruco.ArucoDetector(dictionary)

            all_charuco_corners: list = []
            all_charuco_ids: list = []
            image_size = None

            for i, frame in enumerate(frames):
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
                if image_size is None:
                    image_size = gray.shape[::-1]
                corners, ids, _ = detector.detectMarkers(gray)
                if ids is None or len(ids) < 4:
                    logger.debug("Lens calibration frame %d ignored (markers=%d)", i, 0 if ids is None else len(ids))
                    continue

                ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
                    corners, ids, gray, board
                )
                if ret >= 4:
                    all_charuco_corners.append(charuco_corners)
                    all_charuco_ids.append(charuco_ids)

            if len(all_charuco_corners) < 3 or image_size is None:
                return {
                    "ok": False,
                    "error": f"Only {len(all_charuco_corners)} usable frames (need 3+)",
                }

            rms, camera_matrix, dist_coeffs, _rvecs, _tvecs = cv2.aruco.calibrateCameraCharuco(
                all_charuco_corners,
                all_charuco_ids,
                board,
                image_size,
                None,
                None,
            )
            if not np.isfinite(rms):
                return {"ok": False, "error": "Invalid calibration RMS"}

            cfg = self._config_io._config
            cfg.update(
                {
                    "camera_matrix": camera_matrix.tolist(),
                    "dist_coeffs": dist_coeffs.reshape(-1).tolist(),
                    "lens_valid": True,
                    "lens_method": "charuco",
                    "lens_image_size": [int(image_size[0]), int(image_size[1])],
                    "lens_last_update_utc": datetime.now(timezone.utc).isoformat(),
                    "lens_reprojection_error": float(rms),
                    "schema_version": int(cfg.get("schema_version", 1)) if cfg.get("schema_version") else 2,
                }
            )
            self._config_io._atomic_save()
            logger.info("Lens calibration complete (RMS=%.4f)", rms)
            return {
                "ok": True,
                "camera_matrix": camera_matrix.tolist(),
                "dist_coeffs": dist_coeffs.reshape(-1).tolist(),
                "reprojection_error": float(rms),
                "image_size": [int(image_size[0]), int(image_size[1])],
            }
        except Exception as exc:
            logger.error("Lens calibration failed: %s", exc)
            return {"ok": False, "error": str(exc)}
