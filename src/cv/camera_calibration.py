"""Lens/intrinsics calibration manager (separate from board pose calibration)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import cv2
import numpy as np

from src.cv.calibration import CalibrationManager
from src.cv.geometry import CameraIntrinsics
from src.cv.stereo_calibration import (
    CharucoBoardSpec,
    detect_charuco_board,
    resolve_charuco_board_candidates,
    resolve_charuco_board_spec,
)

logger = logging.getLogger(__name__)


class CameraCalibrationManager:
    """Manage lens calibration (camera matrix + distortion coefficients)."""

    def __init__(
        self,
        config_path: str = "config/calibration_config.yaml",
        camera_id: str = "default",
    ) -> None:
        # Reuse the existing atomic config loader/saver so both managers share one file.
        self._config_io = CalibrationManager(config_path=config_path, camera_id=camera_id)
        self.config_path = config_path
        self.camera_id = camera_id

    def get_config(self) -> dict:
        return self._config_io.get_config()

    def validate_intrinsics(
        self,
        current_image_size: tuple[int, int] | None = None,
        max_age_days: int = 30,
    ) -> dict:
        """Validate that lens intrinsics are present, accurate, and current."""
        errors: list[str] = []
        warnings: list[str] = []

        cfg = self._config_io.get_config()

        if not cfg.get("lens_valid", False):
            errors.append("Keine Lens-Kalibrierung vorhanden")
            return {"valid": False, "errors": errors, "warnings": warnings}

        if not cfg.get("camera_matrix") or not cfg.get("dist_coeffs"):
            errors.append("camera_matrix oder dist_coeffs fehlen")
            return {"valid": False, "errors": errors, "warnings": warnings}

        try:
            cm = np.array(cfg["camera_matrix"])
            if cm.shape != (3, 3):
                errors.append(f"camera_matrix hat falsche Shape: {cm.shape}, erwartet (3, 3)")
        except Exception:
            errors.append("camera_matrix nicht als Array lesbar")

        rms = cfg.get("lens_reprojection_error")
        if rms is not None and rms > 1.0:
            warnings.append(f"Reprojection Error hoch: {rms:.3f} (Empfehlung: < 1.0)")

        if current_image_size is not None:
            stored_size = cfg.get("lens_image_size")
            if stored_size is not None and list(current_image_size) != list(stored_size):
                errors.append(
                    f"Kalibrierung fuer {stored_size[0]}x{stored_size[1]}, "
                    f"aktuelle Aufloesung {current_image_size[0]}x{current_image_size[1]}"
                )

        last_update = cfg.get("lens_last_update_utc")
        if last_update:
            try:
                cal_time = datetime.fromisoformat(last_update)
                age_days = (datetime.now(timezone.utc) - cal_time).days
                if age_days > max_age_days:
                    warnings.append(
                        f"Kalibrierung ist {age_days} Tage alt (Empfehlung: < {max_age_days})"
                    )
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

    def get_charuco_board_candidates(
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
    ) -> list[CharucoBoardSpec]:
        """Resolve one or more ChArUco board candidates from config plus overrides."""
        return resolve_charuco_board_candidates(
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

    def store_charuco_board_spec(self, board_spec: CharucoBoardSpec) -> None:
        """Persist the resolved ChArUco board geometry without touching intrinsics."""
        cfg = self._config_io._config
        cfg.update(
            {
                "schema_version": int(cfg.get("schema_version", 1)) if cfg.get("schema_version") else 2,
                **board_spec.to_config_fragment(),
            }
        )
        self._config_io._atomic_save()

    def charuco_calibration(
        self,
        frames: list[np.ndarray],
        preset: str | None = None,
        squares_x: int | None = None,
        squares_y: int | None = None,
        square_length: float | None = None,
        marker_length: float | None = None,
        square_length_mm: float | None = None,
        marker_length_mm: float | None = None,
        board_spec: CharucoBoardSpec | None = None,
        candidate_specs: list[CharucoBoardSpec] | None = None,
    ) -> dict:
        """Estimate camera intrinsics from multiple ChArUco board frames."""
        try:
            if len(frames) < 3:
                return {"ok": False, "error": f"Need at least 3 frames, got {len(frames)}"}

            candidate_specs = list(candidate_specs or self.get_charuco_board_candidates(
                preset=preset,
                squares_x=squares_x,
                squares_y=squares_y,
                square_length=square_length,
                marker_length=marker_length,
                square_length_mm=square_length_mm,
                marker_length_mm=marker_length_mm,
                board_spec=board_spec,
            ))
            if not candidate_specs:
                return {"ok": False, "error": "Keine ChArUco-Boards konfiguriert"}

            image_size = None
            detections: list[dict] = []
            stats: dict[str, dict] = {}

            for i, frame in enumerate(frames):
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
                if image_size is None:
                    image_size = gray.shape[::-1]

                detection = detect_charuco_board(
                    frame,
                    board_specs=candidate_specs,
                )
                if (
                    detection.board_spec is None
                    or not detection.interpolation_ok
                    or detection.charuco_corners is None
                    or detection.charuco_ids is None
                ):
                    logger.debug(
                        "Lens calibration frame %d ignored (preset=%s, markers=%d, charuco=%d, warning=%s)",
                        i,
                        None if detection.board_spec is None else detection.board_spec.preset_name,
                        detection.markers_found,
                        detection.charuco_corners_found,
                        detection.warning,
                    )
                    continue

                detections.append(
                    {
                        "spec": detection.board_spec,
                        "charuco_corners": detection.charuco_corners,
                        "charuco_ids": detection.charuco_ids,
                        "corner_count": detection.charuco_corners_found,
                    }
                )
                spec_stats = stats.setdefault(
                    detection.board_spec.preset_name,
                    {
                        "spec": detection.board_spec,
                        "usable_frames": 0,
                        "corner_sum": 0,
                    },
                )
                spec_stats["usable_frames"] += 1
                spec_stats["corner_sum"] += detection.charuco_corners_found

            if image_size is None or not stats:
                return {
                    "ok": False,
                    "error": "Only 0 usable frames (need 3+)",
                }

            selected_stats = max(
                stats.values(),
                key=lambda item: (item["usable_frames"], item["corner_sum"]),
            )
            resolved_board_spec = selected_stats["spec"]
            all_charuco_corners = [
                item["charuco_corners"]
                for item in detections
                if item["spec"] == resolved_board_spec
            ]
            all_charuco_ids = [
                item["charuco_ids"]
                for item in detections
                if item["spec"] == resolved_board_spec
            ]
            usable_frames = len(all_charuco_corners)
            if usable_frames < 3:
                return {
                    "ok": False,
                    "error": f"Only {usable_frames} usable frames (need 3+)",
                    "charuco_board": resolved_board_spec.to_api_payload(),
                }

            dictionary = resolved_board_spec.create_dictionary()
            board = resolved_board_spec.create_board(dictionary)
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
                    **resolved_board_spec.to_config_fragment(),
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
                "charuco_board": resolved_board_spec.to_api_payload(),
                "usable_frames": usable_frames,
            }
        except Exception as exc:
            logger.error("Lens calibration failed: %s", exc)
            return {"ok": False, "error": str(exc)}


class CharucoFrameCollector:
    """Collect diverse, interpolation-valid ChArUco frames for calibration."""

    def __init__(
        self,
        frames_needed: int = 15,
        min_position_diff: float = 0.15,
        min_rotation_diff_deg: float = 10.0,
        board_specs: list[CharucoBoardSpec] | None = None,
    ):
        self.frames_needed = frames_needed
        self._min_pos_diff = min_position_diff
        self._min_rot_diff = min_rotation_diff_deg
        self._frames: list[np.ndarray] = []
        self._corner_sets: list[np.ndarray] = []
        self._frame_board_specs: list[CharucoBoardSpec | None] = []
        self._frame_corner_counts: list[int] = []
        self._board_specs = list(board_specs or [])
        self._last_board_spec: CharucoBoardSpec | None = None
        self._last_markers_found = 0
        self._last_charuco_corners_found = 0
        self._last_interpolation_ok = False
        self._last_warning: str | None = None

    @staticmethod
    def _normalize_corners(corners: np.ndarray | None) -> np.ndarray | None:
        if corners is None:
            return None
        normalized = np.asarray(corners, dtype=np.float32)
        if normalized.size == 0:
            return None
        return normalized.reshape(-1, 2)

    @property
    def candidate_specs(self) -> list[CharucoBoardSpec]:
        return list(self._board_specs)

    @property
    def frames_captured(self) -> int:
        return len(self._frames)

    @property
    def resolved_board_spec(self) -> CharucoBoardSpec | None:
        stats: dict[str, dict] = {}
        for spec, corner_count in zip(self._frame_board_specs, self._frame_corner_counts):
            if spec is None:
                continue
            entry = stats.setdefault(
                spec.preset_name,
                {"spec": spec, "frames": 0, "corner_sum": 0},
            )
            entry["frames"] += 1
            entry["corner_sum"] += corner_count
        if not stats:
            return self._last_board_spec
        best = max(stats.values(), key=lambda item: (item["frames"], item["corner_sum"]))
        return best["spec"]

    @property
    def resolved_preset(self) -> str | None:
        spec = self.resolved_board_spec
        return None if spec is None else spec.preset_name

    @property
    def usable_frames(self) -> int:
        resolved = self.resolved_board_spec
        if resolved is None:
            return 0
        return sum(1 for spec in self._frame_board_specs if spec == resolved)

    @property
    def ready_to_calibrate(self) -> bool:
        return self.usable_frames >= self.frames_needed

    @property
    def last_markers_found(self) -> int:
        return self._last_markers_found

    @property
    def last_charuco_corners_found(self) -> int:
        return self._last_charuco_corners_found

    @property
    def last_interpolation_ok(self) -> bool:
        return self._last_interpolation_ok

    @property
    def last_warning(self) -> str | None:
        return self._last_warning

    def update_detection(
        self,
        *,
        board_spec: CharucoBoardSpec | None = None,
        markers_found: int = 0,
        charuco_corners_found: int = 0,
        interpolation_ok: bool = False,
        warning: str | None = None,
    ) -> None:
        self._last_board_spec = board_spec
        self._last_markers_found = int(markers_found)
        self._last_charuco_corners_found = int(charuco_corners_found)
        self._last_interpolation_ok = bool(interpolation_ok)
        self._last_warning = warning

    def add_frame_if_diverse(
        self,
        corners: np.ndarray,
        frame: np.ndarray,
        *,
        board_spec: CharucoBoardSpec | None = None,
        markers_found: int = 0,
        charuco_corners_found: int = 0,
        interpolation_ok: bool = True,
        warning: str | None = None,
    ) -> bool:
        """Add a frame only after successful ChArUco interpolation."""
        normalized = self._normalize_corners(corners)
        self.update_detection(
            board_spec=board_spec,
            markers_found=markers_found,
            charuco_corners_found=charuco_corners_found,
            interpolation_ok=interpolation_ok,
            warning=warning,
        )
        if (
            normalized is None
            or board_spec is None
            or not interpolation_ok
            or charuco_corners_found < 4
        ):
            return False

        if len(self._corner_sets) == 0:
            self._corner_sets.append(normalized.copy())
            self._frames.append(frame.copy())
            self._frame_board_specs.append(board_spec)
            self._frame_corner_counts.append(int(charuco_corners_found))
            return True

        new_centroid = normalized.mean(axis=0)
        for existing in self._corner_sets:
            old_centroid = existing.mean(axis=0)
            ref = max(frame.shape[1] if frame.ndim >= 2 else 640, 1)
            dist = np.linalg.norm(new_centroid - old_centroid) / ref
            if dist < self._min_pos_diff:
                return False

        self._corner_sets.append(normalized.copy())
        self._frames.append(frame.copy())
        self._frame_board_specs.append(board_spec)
        self._frame_corner_counts.append(int(charuco_corners_found))
        return True

    def get_frames(self, board_spec: CharucoBoardSpec | None = None) -> list[np.ndarray]:
        if board_spec is None:
            return list(self._frames)
        return [
            frame
            for frame, spec in zip(self._frames, self._frame_board_specs)
            if spec == board_spec
        ]

    def get_resolved_board_payload(self) -> dict | None:
        spec = self.resolved_board_spec
        return None if spec is None else spec.to_api_payload()

    def get_tips(self, image_shape: tuple[int, ...] = (480, 640)) -> list[str]:
        """Return guidance tips based on collected frames."""
        tips = []
        usable_frames = self.usable_frames
        if self._last_warning:
            tips.append(self._last_warning)
        if self.resolved_board_spec is not None:
            tips.append(f"Erkanntes Layout: {self.resolved_board_spec.preset_name}")
        if usable_frames < self.frames_needed:
            tips.append(f"{self.frames_needed - usable_frames} weitere Frames noetig")

        resolved = self.resolved_board_spec
        selected_corners = [
            corners
            for corners, spec in zip(self._corner_sets, self._frame_board_specs)
            if resolved is None or spec == resolved
        ]
        if len(selected_corners) >= 2:
            centroids = np.array([c.mean(axis=0) for c in selected_corners])
            spread_x = centroids[:, 0].std() / image_shape[1] if image_shape[1] else 0
            if spread_x < 0.15:
                tips.append("Mehr Winkel-Variation noetig")

            sizes = []
            for corners in selected_corners:
                if len(corners) >= 2:
                    span = np.linalg.norm(corners.max(axis=0) - corners.min(axis=0))
                    sizes.append(span)
            if sizes:
                avg_size = np.mean(sizes)
                img_diag = np.sqrt(image_shape[0] ** 2 + image_shape[1] ** 2)
                ratio = avg_size / img_diag if img_diag else 0
                if ratio < 0.2:
                    tips.append("Board naeher halten")
                elif ratio > 0.7:
                    tips.append("Board weiter halten")

        if not tips and usable_frames < self.frames_needed:
            tips.append("Weiter so - Board langsam bewegen")

        return tips

    def reset(self):
        self._frames.clear()
        self._corner_sets.clear()
        self._frame_board_specs.clear()
        self._frame_corner_counts.clear()
        self._last_board_spec = None
        self._last_markers_found = 0
        self._last_charuco_corners_found = 0
        self._last_interpolation_ok = False
        self._last_warning = None
