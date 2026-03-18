"""Orchestrates the full CV pipeline: capture -> remap -> detect -> score."""

from __future__ import annotations

import argparse
import logging
import math
import os
import time
from typing import Callable

import cv2
import numpy as np

from src.cv.board_calibration import BoardCalibrationManager
from src.cv.camera_calibration import CameraCalibrationManager
from src.cv.capture import ThreadedCamera
from src.cv.detector import DartImpactDetector
from src.cv.geometry import BoardGeometry, BoardHit, RING_BOUNDARIES
from src.cv.diff_detector import FrameDiffDetector
from src.cv.motion import MotionDetector
from src.cv.remapping import CombinedRemapper
from src.cv.replay import ReplayCamera
from src.cv.stereo_calibration import DEFAULT_CHARUCO_BOARD_SPEC
from src.cv.roi import ROIProcessor
from src.utils.fps import FPSCounter
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)

# C1: Frame-drop constants — skip expensive analysis when pipeline is overloaded
_TARGET_FPS = 30
_FRAME_INTERVAL_S = 1.0 / _TARGET_FPS          # ~0.0333 s per frame
FRAME_STALE_THRESHOLD_S = _FRAME_INTERVAL_S * 1.5  # ~0.05 s tolerance


class DartPipeline:
    """Orchestrates the full CV pipeline and exposes web-safe helper methods."""

    def __init__(
        self,
        camera_src: int | str = 0,
        on_dart_detected: Callable | None = None,
        on_dart_removed: Callable[[], None] | None = None,
        debug: bool = False,
        capture_width: int | None = None,
        capture_height: int | None = None,
        capture_fps: int | None = None,
        marker_size_mm: float | None = None,
        marker_spacing_mm: float | None = None,
        diff_threshold: int | None = None,
    ) -> None:
        self.camera_src = camera_src
        self.marker_size_mm = marker_size_mm
        self.marker_spacing_mm = marker_spacing_mm
        self.on_dart_detected = on_dart_detected
        self.on_dart_removed = on_dart_removed
        self.debug = debug
        self._capture_width = capture_width
        self._capture_height = capture_height
        self._capture_fps = capture_fps

        # Modules
        self.camera: ThreadedCamera | ReplayCamera | None = None
        self.roi_processor = ROIProcessor(roi_size=(400, 400))
        self.motion_detector = MotionDetector(threshold=200)
        self.dart_detector = DartImpactDetector(confirmation_frames=3)
        self.frame_diff_detector = FrameDiffDetector(
            settle_frames=5,
            diff_threshold=diff_threshold if diff_threshold is not None else 50,
            min_diff_area=30,
            max_diff_area=8000,
            diagnostics_dir=os.environ.get("DARTVISION_DIAGNOSTICS_DIR"),
        )
        self.fps_counter = FPSCounter()
        self.camera_calibration = CameraCalibrationManager()
        self.board_calibration = BoardCalibrationManager(roi_size=self.roi_processor.roi_size)
        self.remapper = CombinedRemapper(roi_size=self.roi_processor.roi_size)
        self.geometry: BoardGeometry | None = None

        # Backward compatibility aliases used by routes/tests
        self.roi = self.roi_processor
        self.detector = self.dart_detector
        self.calibration = self.board_calibration

        # CLAHE for contrast enhancement
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        # Frame storage
        self._last_raw_frame: np.ndarray | None = None
        self._last_annotated_frame: np.ndarray | None = None
        self._last_score: dict | None = None
        self._last_roi: np.ndarray | None = None
        self._last_motion_mask: np.ndarray | None = None

        # C1: Frame-drop counter for monitoring
        self._dropped_frames: int = 0

        # Optical center override (ROI pixel space)
        self._optical_center: tuple[float, float] | None = None

        # Motion overlay toggle
        self.show_overlay_motion = False

        # Marker detection overlay toggle (ArUco + ChArUco)
        self.show_overlay_markers = False

    def start(self) -> None:
        """Initialize modules and start capture source."""
        self.camera = self._build_camera_source()
        self.camera.start()

        pose = self.board_calibration.get_pose()
        if pose.homography is not None:
            self.roi_processor.set_homography_matrix(pose.homography)
        oc = self.board_calibration.get_optical_center()
        if oc is not None:
            self._optical_center = oc

        self.refresh_remapper()
        logger.info("DartPipeline started (src=%s, debug=%s)", self.camera_src, self.debug)

    def stop(self) -> None:
        """Stop processing and release resources."""
        if self.camera is not None:
            self.camera.stop()
        if self.debug:
            cv2.destroyAllWindows()
        logger.info("DartPipeline stopped")

    def _build_camera_source(self) -> ThreadedCamera | ReplayCamera:
        """Create camera source adapter (live webcam or replay clip)."""
        if isinstance(self.camera_src, str) and os.path.isfile(self.camera_src):
            logger.info("Using replay source: %s", self.camera_src)
            return ReplayCamera(self.camera_src, loop=True)
        return ThreadedCamera(
            src=self.camera_src,
            width=self._capture_width,
            height=self._capture_height,
            fps=self._capture_fps,
        )

    def refresh_remapper(self) -> None:
        """Refresh combined remap tables after lens/board calibration changes."""
        homography = self.board_calibration.get_homography()
        intrinsics = self.camera_calibration.get_intrinsics()
        self.remapper.configure(homography=homography, intrinsics=intrinsics)
        self._refresh_geometry()

    def _refresh_geometry(self) -> None:
        geometry = self.board_calibration.get_geometry()
        if self._optical_center is not None:
            geometry.optical_center_px = self._optical_center
        self.geometry = geometry

    def process_frame(self) -> dict | None:
        """Process one frame. Returns score dict if dart detected, else None."""
        if self.camera is None:
            return None

        t_capture = time.monotonic()
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return None
        self._last_raw_frame = frame
        self.fps_counter.update()

        # C1: Skip expensive analysis when pipeline is falling behind schedule.
        # If more than FRAME_STALE_THRESHOLD_S has elapsed since we started
        # capturing (e.g. due to prior processing overhead), discard this frame.
        if time.monotonic() - t_capture > FRAME_STALE_THRESHOLD_S:
            self._dropped_frames += 1
            return None

        # 1) Combined remap to ROI board space
        roi_source = self.remapper.remap(frame)
        if roi_source.shape[:2] != (self.roi_processor.roi_size[1], self.roi_processor.roi_size[0]):
            roi_source = cv2.resize(roi_source, self.roi_processor.roi_size)

        # 2) Grayscale + local contrast enhancement
        gray = cv2.cvtColor(roi_source, cv2.COLOR_BGR2GRAY) if len(roi_source.shape) == 3 else roi_source
        enhanced = self.clahe.apply(gray)
        self._last_roi = enhanced

        # 3) Motion detection
        motion_mask, has_motion = self.motion_detector.detect(enhanced)
        self._last_motion_mask = motion_mask

        # 4) Frame-Diff detection — receives every frame (SETTLING needs motion-free frames)
        detection = self.frame_diff_detector.update(enhanced, has_motion)
        if detection is not None:
            self.dart_detector.register_confirmed(detection)
        else:
            self._update_annotated_frame(frame, enhanced, motion_mask if has_motion else None)
            return None

        # 5) Scoring via BoardGeometry
        geometry = self.geometry or self.board_calibration.get_geometry()
        hit = geometry.point_to_score(detection.center[0], detection.center[1])
        score_result = geometry.hit_to_dict(hit)

        if self.on_dart_detected:
            self.on_dart_detected(score_result, detection)

        self._last_score = score_result
        self._update_annotated_frame(frame, enhanced, motion_mask, detection, score_result)
        return score_result

    def detect_optical_center(self) -> tuple[float, float] | None:
        """Detect the optical center on the latest frame and persist it."""
        frame = self._last_raw_frame
        if frame is None and self.camera is not None:
            ok, frame = self.camera.read()
            if not ok or frame is None:
                return None
            self._last_raw_frame = frame
        if frame is None:
            return None

        roi_color = self.remapper.remap(frame)
        if roi_color.shape[:2] != (self.roi_processor.roi_size[1], self.roi_processor.roi_size[0]):
            roi_color = cv2.resize(roi_color, self.roi_processor.roi_size)
        if len(roi_color.shape) == 2:
            roi_color = cv2.cvtColor(roi_color, cv2.COLOR_GRAY2BGR)

        cx, cy = self.board_calibration.find_optical_center(roi_color)
        self._optical_center = (cx, cy)
        self.board_calibration.store_optical_center(self._optical_center)
        self._refresh_geometry()
        logger.info("Optical center detected and saved: (%.1f, %.1f)", cx, cy)
        return (cx, cy)

    def reset_turn(self) -> None:
        """Reset detector state for new turn (after darts removed)."""
        self.dart_detector.reset()
        self.frame_diff_detector.reset()
        self.motion_detector.reset()
        if self.on_dart_removed:
            self.on_dart_removed()
        logger.info("Turn reset - dart detector cleared")

    def get_annotated_frame(self) -> np.ndarray | None:
        return self._last_annotated_frame

    def get_latest_raw_frame(self) -> np.ndarray | None:
        return self._last_raw_frame

    def get_roi_preview(self) -> np.ndarray | None:
        frame = self._last_raw_frame
        if frame is None:
            return None
        roi = self.remapper.remap(frame)
        if roi.shape[:2] != (self.roi_processor.roi_size[1], self.roi_processor.roi_size[0]):
            roi = cv2.resize(roi, self.roi_processor.roi_size)
        if len(roi.shape) == 2:
            return cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        return roi

    def get_field_overlay(self) -> np.ndarray | None:
        roi = self.get_roi_preview()
        if roi is None:
            return None
        overlay = roi.copy()
        self._draw_field_overlay(overlay)
        return overlay

    def get_geometry_info(self) -> dict:
        geometry = self.geometry or self.board_calibration.get_geometry()
        payload = geometry.to_api_dict()
        payload["lens_valid"] = self.camera_calibration.has_intrinsics()
        intrinsics = self.camera_calibration.get_intrinsics()
        payload["lens_method"] = intrinsics.method if intrinsics else None
        return payload

    def _draw_field_overlay(self, overlay: np.ndarray) -> None:
        h, w = overlay.shape[:2]
        if self._optical_center is not None:
            cx, cy = int(self._optical_center[0]), int(self._optical_center[1])
        else:
            cx, cy = w // 2, h // 2

        radii_px = self.board_calibration.get_radii_px()
        if radii_px and len(radii_px) == 6 and radii_px[-1] > 0:
            radius = radii_px[-1]
        else:
            radius = min(cx, cy)

        ring_fractions = [b[1] for b in RING_BOUNDARIES]  # outer boundaries
        ring_colors = [
            (0, 0, 255),
            (0, 255, 0),
            (255, 255, 0),
            (255, 255, 0),
            (0, 165, 255),
            (0, 165, 255),
        ]
        for frac, color in zip(ring_fractions, ring_colors):
            r = int(frac * radius)
            cv2.circle(overlay, (cx, cy), r, color, 1)

        sector_angle = 18.0
        offset = 9.0 + (self.geometry.rotation_deg if self.geometry else 0.0)
        for i in range(20):
            angle_deg = -90 - offset + i * sector_angle
            angle_rad = math.radians(angle_deg)
            outer_r = radius
            inner_r = int(ring_fractions[1] * radius)
            x_end = int(cx + outer_r * math.cos(angle_rad))
            y_end = int(cy + outer_r * math.sin(angle_rad))
            x_start = int(cx + inner_r * math.cos(angle_rad))
            y_start = int(cy + inner_r * math.sin(angle_rad))
            cv2.line(overlay, (x_start, y_start), (x_end, y_end), (100, 100, 255), 1)

        sectors = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
        for i in range(20):
            angle_deg = -90 - offset + (i + 0.5) * sector_angle
            angle_rad = math.radians(angle_deg)
            label_r = 0.85 * radius
            lx = int(cx + label_r * math.cos(angle_rad))
            ly = int(cy + label_r * math.sin(angle_rad))
            cv2.putText(
                overlay,
                str(sectors[i]),
                (lx - 8, ly + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (255, 255, 255),
                1,
            )

    def _update_annotated_frame(
        self,
        frame: np.ndarray,
        roi: np.ndarray,
        motion_mask: np.ndarray | None,
        detection=None,
        score_result: dict | None = None,
    ) -> None:
        annotated = frame.copy()
        fps = self.fps_counter.fps()
        cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cal_status = "CAL: OK" if self.board_calibration.is_valid() else "CAL: NONE"
        cal_color = (0, 255, 0) if self.board_calibration.is_valid() else (0, 0, 255)
        cv2.putText(
            annotated,
            cal_status,
            (frame.shape[1] - 150, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            cal_color,
            2,
        )

        dart_count = len(self.dart_detector.get_all_confirmed())
        cv2.putText(
            annotated,
            f"Darts: {dart_count}/3",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        if detection is not None and score_result is not None:
            cv2.circle(annotated, detection.center, 15, (0, 0, 255), 2)
            label = f"{score_result['ring'].upper()} {score_result['score']}"
            cv2.putText(
                annotated,
                label,
                (detection.center[0] + 20, detection.center[1]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        if self.show_overlay_markers:
            self._draw_marker_overlay(annotated)

        if self.show_overlay_motion and motion_mask is not None:
            fh, fw = annotated.shape[:2]
            overlay_size = min(fw // 2, fh // 2, 320)
            margin = 10
            overlay_y = fh - overlay_size - margin
            overlay_x = fw - overlay_size - margin
            self._composite_overlay(annotated, motion_mask, overlay_x, overlay_y, overlay_size, "MOTION")

        self._last_annotated_frame = annotated

        if self.debug:
            cv2.imshow("Dart Vision", annotated)
            roi_display = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR) if len(roi.shape) == 2 else roi
            cv2.imshow("ROI", roi_display)
            if motion_mask is not None:
                cv2.imshow("Motion", motion_mask)
            cv2.waitKey(1)

    def _draw_marker_overlay(self, frame: np.ndarray) -> None:
        """Draw detected ArUco and ChArUco markers on the frame."""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
            fh, fw = frame.shape[:2]
            aruco_count = 0
            charuco_count = 0

            # --- ArUco markers (DICT_4X4_50, board alignment) ---
            aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
            aruco_params = cv2.aruco.DetectorParameters()
            aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            aruco_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
            aruco_corners, aruco_ids, _ = aruco_detector.detectMarkers(gray)

            if aruco_ids is not None and len(aruco_ids) > 0:
                cv2.aruco.drawDetectedMarkers(frame, aruco_corners, aruco_ids,
                                               borderColor=(0, 255, 0))
                aruco_count = len(aruco_ids)

            # --- ChArUco board (DICT_6X6_250, lens calibration) ---
            charuco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
            charuco_params = cv2.aruco.DetectorParameters()
            charuco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
            charuco_detector = cv2.aruco.ArucoDetector(charuco_dict, charuco_params)
            charuco_corners, charuco_ids, _ = charuco_detector.detectMarkers(gray)

            if charuco_ids is not None and len(charuco_ids) > 0:
                # Draw the 6x6 ArUco markers in yellow
                cv2.aruco.drawDetectedMarkers(frame, charuco_corners, charuco_ids,
                                               borderColor=(0, 255, 255))

                # Try to interpolate ChArUco corners for extra feedback
                board_spec = DEFAULT_CHARUCO_BOARD_SPEC
                if hasattr(self, "camera_calibration") and self.camera_calibration is not None:
                    board_spec = self.camera_calibration.get_charuco_board_spec()
                board = board_spec.create_board(charuco_dict)
                ret, ch_corners, ch_ids = cv2.aruco.interpolateCornersCharuco(
                    charuco_corners, charuco_ids, gray, board,
                )
                if ret > 0 and ch_corners is not None:
                    charuco_count = ret
                    for pt in ch_corners:
                        x, y = int(pt[0][0]), int(pt[0][1])
                        cv2.circle(frame, (x, y), 4, (255, 255, 0), -1)  # Cyan filled
                        cv2.circle(frame, (x, y), 5, (255, 200, 0), 1)   # Outline

            # Status text at bottom
            status_parts = []
            if aruco_count > 0:
                status_parts.append(f"ArUco 4x4: {aruco_count} Marker")
            if charuco_count > 0:
                status_parts.append(f"ChArUco: {charuco_count} Corners")
            if not status_parts:
                status_parts.append("Keine Marker erkannt")

            status_text = " | ".join(status_parts)
            # Background bar for readability
            text_y = fh - 15
            cv2.rectangle(frame, (0, fh - 35), (fw, fh), (0, 0, 0), -1)
            cv2.putText(frame, status_text, (10, text_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 200), 1)

        except Exception as e:
            logger.debug("Marker overlay error: %s", e)

    def _composite_overlay(self, frame: np.ndarray, overlay_img: np.ndarray, x: int, y: int, size: int, label: str) -> None:
        if x < 0 or y < 0:
            return
        try:
            overlay_bgr = cv2.cvtColor(overlay_img, cv2.COLOR_GRAY2BGR) if len(overlay_img.shape) == 2 else overlay_img
            resized = cv2.resize(overlay_bgr, (size, size))
            fh, fw = frame.shape[:2]
            if y + size > fh or x + size > fw:
                return
            frame[y : y + size, x : x + size] = resized
            cv2.rectangle(frame, (x, y), (x + size, y + size), (100, 100, 100), 1)
            cv2.putText(frame, label, (x + 4, y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Dart Vision CV Pipeline")
    parser.add_argument("--source", default=0, help="Camera source index or replay video path")
    parser.add_argument("--debug", action="store_true", help="Show debug windows")
    parser.add_argument("--marker-size", type=float, default=None,
                        help="ArUco marker edge length in mm (default: from config or 75)")
    parser.add_argument("--marker-spacing", type=float, default=None,
                        help="ArUco marker center-to-center distance in mm (default: 430)")
    args = parser.parse_args()

    source: int | str
    try:
        source = int(args.source)
    except Exception:
        source = str(args.source)

    setup_logging()

    def on_dart(score: dict, detection=None) -> None:
        ring = score["ring"]
        points = score["score"]
        sector = score["sector"]
        mult = score["multiplier"]
        logger.info("SCORE: %s %d (sector=%d, x%d)", ring, points, sector, mult)

    pipeline = DartPipeline(camera_src=source, on_dart_detected=on_dart, debug=args.debug,
                            marker_size_mm=args.marker_size,
                            marker_spacing_mm=args.marker_spacing)
    try:
        pipeline.start()
        logger.info("Pipeline running. Press Ctrl+C to stop.")
        while True:
            pipeline.process_frame()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        pipeline.stop()


if __name__ == "__main__":
    main()
