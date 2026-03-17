"""Lens/intrinsics calibration manager (separate from board pose calibration)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import cv2
import numpy as np

from src.cv.calibration import CalibrationManager
from src.cv.charuco_detection import collect_charuco_frame_observations
from src.cv.geometry import CameraIntrinsics
from src.cv.stereo_calibration import CharucoBoardSpec, resolve_charuco_board_spec

logger = logging.getLogger(__name__)


class CameraCalibrationManager:
    """Manage lens calibration (camera matrix + distortion coefficients)."""

    def __init__(self, config_path: str = "config/calibration_config.yaml",
                 camera_id: str = "default") -> None:
        # Reuse the existing atomic config loader/saver so both managers share one file.
        self._config_io = CalibrationManager(config_path=config_path, camera_id=camera_id)
        self.config_path = config_path
        self.camera_id = camera_id

    def get_config(self) -> dict:
        return self._config_io.get_config()

    def has_intrinsics(self) -> bool:
        cfg = self._config_io.get_config()
        return bool(cfg.get("lens_valid", False) and cfg.get("camera_matrix") and cfg.get("dist_coeffs"))

    def get_charuco_board_spec(
        self,
        *,
        preset: str | None = None,
        squares_x: int | None = None,
        squares_y: int | None = None,
        square_length: float | None = None,
        marker_length: float | None = None,
        square_length_mm: float | None = None,
        marker_length_mm: float | None = None,
        board_spec: CharucoBoardSpec | None = None,
    ) -> CharucoBoardSpec:
        """Resolve the ChArUco board geometry from config plus optional overrides."""
        return resolve_charuco_board_spec(
            config=self._config_io.get_config(),
            preset=preset,
            squares_x=squares_x,
            squares_y=squares_y,
            square_length_m=square_length,
            marker_length_m=marker_length,
            square_length_mm=square_length_mm,
            marker_length_mm=marker_length_mm,
            board_spec=board_spec,
        )

    def get_intrinsics(self) -> CameraIntrinsics | None:
        return CameraIntrinsics.from_config(self._config_io.get_config())

    def charuco_calibration(
        self,
        frames: list[np.ndarray],
        squares_x: int | None = None,
        squares_y: int | None = None,
        square_length: float | None = None,
        marker_length: float | None = None,
        board_spec: CharucoBoardSpec | None = None,
    ) -> dict:
        """Estimate camera intrinsics from multiple ChArUco board frames."""
        try:
            if len(frames) < 3:
                return {"ok": False, "error": f"Need at least 3 frames, got {len(frames)}"}

            board_spec = self.get_charuco_board_spec(
                preset=None,
                squares_x=squares_x,
                squares_y=squares_y,
                square_length=square_length,
                marker_length=marker_length,
                board_spec=board_spec,
            )
            dictionary = board_spec.create_dictionary()
            board = board_spec.create_board(dictionary)
            detector = cv2.aruco.ArucoDetector(dictionary)

            all_charuco_corners, all_charuco_ids, image_size = collect_charuco_frame_observations(
                frames,
                board,
                detector,
                logger=logger,
                skip_log_level="debug",
                skip_log_template="Lens calibration frame %d ignored (markers=%d)",
            )

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
                    **board_spec.to_config_fragment(),
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
                "charuco_board": board_spec.to_api_payload(),
            }
        except Exception as exc:
            logger.error("Lens calibration failed: %s", exc)
            return {"ok": False, "error": str(exc)}
