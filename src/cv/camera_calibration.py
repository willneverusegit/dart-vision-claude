"""Lens/intrinsics calibration manager (separate from board pose calibration)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import cv2
import numpy as np

from src.cv.calibration import CalibrationManager
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

    def validate_intrinsics(self, current_image_size: tuple[int, int] | None = None, max_age_days: int = 30) -> dict:
        """Validate that lens intrinsics are present, accurate, and current.

        Args:
            current_image_size: (width, height) of current capture. If provided, checks match.
            max_age_days: Maximum age of calibration in days.

        Returns:
            dict with 'valid' (bool), 'errors' (list[str]), 'warnings' (list[str])
        """
        errors: list[str] = []
        warnings: list[str] = []

        cfg = self._config_io.get_config()

        # Check intrinsics exist
        if not cfg.get("lens_valid", False):
            errors.append("Keine Lens-Kalibrierung vorhanden")
            return {"valid": False, "errors": errors, "warnings": warnings}

        if not cfg.get("camera_matrix") or not cfg.get("dist_coeffs"):
            errors.append("camera_matrix oder dist_coeffs fehlen")
            return {"valid": False, "errors": errors, "warnings": warnings}

        # Check camera_matrix shape
        try:
            cm = np.array(cfg["camera_matrix"])
            if cm.shape != (3, 3):
                errors.append(f"camera_matrix hat falsche Shape: {cm.shape}, erwartet (3, 3)")
        except Exception:
            errors.append("camera_matrix nicht als Array lesbar")

        # Check reprojection error
        rms = cfg.get("lens_reprojection_error")
        if rms is not None and rms > 1.0:
            warnings.append(f"Reprojection Error hoch: {rms:.3f} (Empfehlung: < 1.0)")

        # Check image size match
        if current_image_size is not None:
            stored_size = cfg.get("lens_image_size")
            if stored_size is not None:
                if list(current_image_size) != list(stored_size):
                    errors.append(
                        f"Kalibrierung fuer {stored_size[0]}x{stored_size[1]}, "
                        f"aktuelle Aufloesung {current_image_size[0]}x{current_image_size[1]}"
                    )

        # Check age
        last_update = cfg.get("lens_last_update_utc")
        if last_update:
            try:
                cal_time = datetime.fromisoformat(last_update)
                age_days = (datetime.now(timezone.utc) - cal_time).days
                if age_days > max_age_days:
                    warnings.append(f"Kalibrierung ist {age_days} Tage alt (Empfehlung: < {max_age_days})")
            except Exception:
                warnings.append("Kalibrierungsdatum nicht lesbar")

        valid = len(errors) == 0
        return {"valid": valid, "errors": errors, "warnings": warnings}

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
