"""CalibrationManager: manual 4-point, ArUco marker, and frame-based calibration."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging

import cv2
import numpy as np

from src.cv.calibration_board import (
    aruco_calibration_result,
    find_optical_center as find_optical_center_in_roi,
    manual_calibration_result,
    verify_rings_result,
)
from src.cv.calibration_common import (
    ARUCO_EXPECTED_IDS,
    ARUCO_MARKER_SIZE_MM,
    BOARD_CROP_MM,
    BOARD_DIAMETER_MM,
    BOARD_RADIUS_MM,
    FRAME_INNER_MM,
    FRAME_OUTER_MM,
    MANUAL_MIN_POINT_DISTANCE_PX,
    MARKER_SPACING_MM,
    MM_PER_PX_MAX,
    MM_PER_PX_MIN,
    RING_RADII_MM,
)
from src.cv.calibration_store import load_calibration_config, save_calibration_config_atomic
from src.cv.charuco_detection import collect_charuco_frame_observations
from src.cv.stereo_calibration import resolve_charuco_board_spec

logger = logging.getLogger(__name__)


class CalibrationManager:
    """Manages board calibration: manual 4-point, ArUco, and frame-based."""

    def __init__(self, config_path: str = "config/calibration_config.yaml", camera_id: str = "default") -> None:
        self.config_path = config_path
        self.camera_id = camera_id
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load config from YAML or return defaults."""
        return load_calibration_config(self.config_path, self.camera_id)

    def manual_calibration(
        self,
        board_points: list[list[float]],
        roi_size: tuple[int, int] = (400, 400),
    ) -> dict:
        """Perform manual 4-point calibration."""
        try:
            result = manual_calibration_result(board_points, roi_size=roi_size)
            if result.get("ok"):
                self._config.update(result.pop("config_updates"))
                self._atomic_save()
                logger.info("Manual calibration complete (mm/px=%.3f)", result["mm_per_px"])
            return result
        except Exception as exc:
            logger.error("Manual calibration failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def aruco_calibration(
        self,
        frame: np.ndarray,
        expected_ids: list[int] | None = None,
        marker_spacing_mm: float = MARKER_SPACING_MM,
        roi_size: tuple[int, int] = (400, 400),
    ) -> dict:
        """Detect ArUco markers and derive calibration."""
        try:
            result = aruco_calibration_result(
                frame,
                expected_ids=expected_ids,
                marker_spacing_mm=marker_spacing_mm,
                roi_size=roi_size,
            )
            if result.get("ok"):
                self._config.update(result.pop("config_updates"))
                self._atomic_save()
                logger.info(
                    "ArUco calibration complete (mm/px=%.3f, markers=%s, method=%s)",
                    result["mm_per_px"],
                    result["detected_ids"],
                    result["detection_method"],
                )
            return result
        except Exception as exc:
            logger.error("ArUco calibration failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def verify_rings(self, frame: np.ndarray) -> dict:
        """Verify calibrated ring radii against expected values."""
        return verify_rings_result(self._config, frame)

    def find_optical_center(
        self,
        roi_frame: np.ndarray,
        search_radius_mm: float = 10.0,
    ) -> tuple[float, float]:
        """Find the true optical center (bullseye) in the warped ROI frame."""
        return find_optical_center_in_roi(self._config, roi_frame, search_radius_mm=search_radius_mm)

    def charuco_calibration(
        self,
        frames: list[np.ndarray],
        squares_x: int | None = None,
        squares_y: int | None = None,
        square_length: float | None = None,
        marker_length: float | None = None,
    ) -> dict:
        """ChArUco-based calibration from multiple frames."""
        try:
            if len(frames) < 3:
                return {"ok": False, "error": f"Need at least 3 frames, got {len(frames)}"}

            board_spec = resolve_charuco_board_spec(
                config=self._config,
                squares_x=squares_x,
                squares_y=squares_y,
                square_length_m=square_length,
                marker_length_m=marker_length,
            )
            dictionary = board_spec.create_dictionary()
            board = board_spec.create_board(dictionary)
            detector = cv2.aruco.ArucoDetector(dictionary)
            all_charuco_corners, all_charuco_ids, image_size = collect_charuco_frame_observations(
                frames,
                board,
                detector,
                logger=logger,
                skip_log_level="warning",
            )
            if len(all_charuco_corners) < 3 or image_size is None:
                return {"ok": False, "error": f"Only {len(all_charuco_corners)} usable frames (need 3+)"}

            ret, camera_matrix, dist_coeffs, _rvecs, _tvecs = cv2.aruco.calibrateCameraCharuco(
                all_charuco_corners,
                all_charuco_ids,
                board,
                image_size,
                None,
                None,
            )
            if not ret:
                return {"ok": False, "error": "Camera calibration failed"}

            height, width = frames[0].shape[:2]
            homography = np.eye(3)
            mm_per_px = float(board_spec.square_length_m * 1000 / (width / board_spec.squares_x))
            self._config.update(
                {
                    "center_px": [width / 2.0, height / 2.0],
                    "mm_per_px": mm_per_px,
                    "homography": homography.tolist(),
                    "camera_matrix": camera_matrix.tolist(),
                    "dist_coeffs": dist_coeffs.tolist(),
                    "last_update_utc": datetime.now(timezone.utc).isoformat(),
                    "valid": True,
                    "method": "charuco",
                    "reprojection_error": float(ret),
                    **board_spec.to_config_fragment(),
                }
            )
            self._atomic_save()
            logger.info("ChArUco calibration complete (RMS=%.4f)", ret)
            return {
                "ok": True,
                "homography": homography.tolist(),
                "mm_per_px": mm_per_px,
                "reprojection_error": float(ret),
                "charuco_board": board_spec.to_api_payload(),
            }
        except Exception as exc:
            logger.error("ChArUco calibration failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def get_homography(self) -> np.ndarray | None:
        """Get current homography matrix, or None if not calibrated."""
        if self._config.get("valid", False):
            return np.array(self._config["homography"], dtype=np.float64)
        return None

    def get_config(self) -> dict:
        """Get current calibration config."""
        return dict(self._config)

    def is_valid(self) -> bool:
        """Check if calibration is valid."""
        return self._config.get("valid", False)

    def get_center(self) -> tuple[float, float]:
        """Get board center in original image pixel coordinates."""
        center = self._config.get("center_px", [200, 200])
        return (float(center[0]), float(center[1]))

    def get_optical_center(self) -> tuple[float, float] | None:
        """Get refined optical center in ROI pixel coordinates, if available."""
        center = self._config.get("optical_center_roi_px")
        if center and len(center) == 2:
            return (float(center[0]), float(center[1]))
        return None

    def get_mm_per_px(self) -> float:
        """Get scale factor (mm per pixel)."""
        return float(self._config.get("mm_per_px", 1.0))

    def get_radii_px(self) -> list[float]:
        """Get ring radii in pixels (for ROI-warped image)."""
        return self._config.get("radii_px", [10, 19, 106, 116, 188, 200])

    def _atomic_save(self) -> None:
        """Persist current config atomically in shared multi-camera YAML."""
        save_calibration_config_atomic(self.config_path, self.camera_id, self._config)


def _run_manual_cli(source: int) -> None:
    """Interactive CLI: click 4 board corners in an OpenCV window."""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error("Cannot open camera source: %d", source)
        return
    ret, frame = cap.read()
    cap.release()
    if not ret:
        logger.error("Failed to capture frame")
        return
    points: list[list[float]] = []
    display = frame.copy()
    window_name = "Calibration: Click 4 corners (TL, TR, BR, BL), then Enter"

    def on_mouse(event: int, x: int, y: int, flags: int, param: object) -> None:
        nonlocal display
        if event == cv2.EVENT_LBUTTONDOWN and len(points) < 4:
            points.append([float(x), float(y)])
            cv2.circle(display, (x, y), 5, (0, 255, 0), -1)
            if len(points) > 1:
                cv2.line(display, (int(points[-2][0]), int(points[-2][1])), (x, y), (0, 255, 0), 2)
            if len(points) == 4:
                cv2.line(
                    display,
                    (int(points[3][0]), int(points[3][1])),
                    (int(points[0][0]), int(points[0][1])),
                    (0, 255, 0),
                    2,
                )
            cv2.imshow(window_name, display)
            logger.info("Point %d: [%.1f, %.1f]", len(points), x, y)

    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_mouse)
    cv2.imshow(window_name, display)
    logger.info("Click 4 board corners (TL -> TR -> BR -> BL), then press Enter.")
    while True:
        key = cv2.waitKey(100) & 0xFF
        if key == 13 and len(points) == 4:
            break
        if key == 27:
            logger.info("Calibration cancelled")
            cv2.destroyAllWindows()
            return
        if key == ord("r"):
            points.clear()
            display = frame.copy()
            cv2.imshow(window_name, display)
            logger.info("Points reset")
    cv2.destroyAllWindows()
    manager = CalibrationManager()
    result = manager.manual_calibration(points)
    if result["ok"]:
        logger.info("Calibration saved! mm/px = %.3f", result["mm_per_px"])
    else:
        logger.error("Calibration failed: %s", result["error"])


def _run_charuco_cli(source: int) -> None:
    """Capture multiple frames with ChArUco board for calibration."""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error("Cannot open camera source: %d", source)
        return
    frames: list[np.ndarray] = []
    logger.info("Show ChArUco board. SPACE=capture, ENTER=done (need 3+).")
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        display = frame.copy()
        cv2.putText(
            display,
            f"Captured: {len(frames)} (SPACE=capture, ENTER=done)",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
        cv2.imshow("ChArUco Calibration", display)
        key = cv2.waitKey(30) & 0xFF
        if key == ord(" "):
            frames.append(frame.copy())
            logger.info("Frame %d captured", len(frames))
        elif key == 13 and len(frames) >= 3:
            break
        elif key == 27:
            logger.info("Calibration cancelled")
            cap.release()
            cv2.destroyAllWindows()
            return
    cap.release()
    cv2.destroyAllWindows()
    manager = CalibrationManager()
    result = manager.charuco_calibration(frames)
    if result["ok"]:
        logger.info(
            "ChArUco calibration saved! RMS=%.4f, mm/px=%.3f",
            result["reprojection_error"],
            result["mm_per_px"],
        )
    else:
        logger.error("ChArUco calibration failed: %s", result["error"])


def main() -> None:
    """CLI entry point for calibration."""
    from src.utils.logger import setup_logging

    setup_logging()
    parser = argparse.ArgumentParser(description="Dart Board Calibration")
    parser.add_argument("--mode", choices=["manual", "charuco"], default="manual", help="Calibration method")
    parser.add_argument("--source", type=int, default=0, help="Camera source index")
    args = parser.parse_args()
    if args.mode == "manual":
        _run_manual_cli(args.source)
    else:
        _run_charuco_cli(args.source)


if __name__ == "__main__":
    main()
