"""Orchestrates the full CV pipeline: capture -> preprocess -> detect -> score."""

import cv2
import numpy as np
import argparse
import logging
import math
from typing import Callable

from src.cv.capture import ThreadedCamera
from src.cv.roi import ROIProcessor
from src.cv.motion import MotionDetector
from src.cv.detector import DartImpactDetector
from src.cv.field_mapper import FieldMapper
from src.cv.calibration import CalibrationManager
from src.utils.fps import FPSCounter
from src.utils.logger import setup_logging

logger = logging.getLogger(__name__)


class DartPipeline:
    """Orchestrates the full CV pipeline: capture -> preprocess -> detect -> score."""

    def __init__(self, camera_src: int | str = 0,
                 on_dart_detected: Callable | None = None,
                 on_dart_removed: Callable[[], None] | None = None,
                 debug: bool = False) -> None:
        """
        Args:
            camera_src: Camera source for ThreadedCamera.
            on_dart_detected: Callback(score_result, detection) when a dart is confirmed.
            on_dart_removed: Callback when darts are removed (turn reset).
            debug: Show OpenCV debug windows with overlays.
        """
        self.camera_src = camera_src
        self.on_dart_detected = on_dart_detected
        self.on_dart_removed = on_dart_removed
        self.debug = debug

        # Modules (initialized in start())
        self.camera: ThreadedCamera | None = None
        self.roi_processor = ROIProcessor(roi_size=(400, 400))
        self.motion_detector = MotionDetector(threshold=500)
        self.dart_detector = DartImpactDetector(confirmation_frames=3)
        self.field_mapper = FieldMapper()
        self.fps_counter = FPSCounter()
        self.calibration = CalibrationManager()

        # Aliases used by web routes
        self.roi = self.roi_processor
        self.detector = self.dart_detector

        # CLAHE for contrast enhancement
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        # Frame storage for annotated output
        self._last_annotated_frame: np.ndarray | None = None
        self._last_score: dict | None = None
        self._last_roi: np.ndarray | None = None
        self._last_motion_mask: np.ndarray | None = None

        # Motion overlay toggle (set from web routes)
        self.show_overlay_motion = False

    def start(self) -> None:
        """Initialize all modules and start processing loop."""
        self.camera = ThreadedCamera(src=self.camera_src)
        self.camera.start()
        # Load existing calibration if valid
        if self.calibration.is_valid():
            homography = self.calibration.get_homography()
            if homography is not None:
                self.roi_processor.set_homography_matrix(homography)
                logger.info("Loaded existing calibration (method=%s)",
                            self.calibration.get_config().get("method"))
            # Apply calibrated ring radii to field mapper
            radii_px = self.calibration.get_radii_px()
            if radii_px and len(radii_px) == 6:
                outer_r = radii_px[-1]  # double_outer
                if outer_r > 0:
                    self.field_mapper.set_ring_radii_px(radii_px, outer_r)
                    logger.info("Field mapper radii updated from calibration")
        logger.info("DartPipeline started (src=%s, debug=%s)", self.camera_src, self.debug)

    def stop(self) -> None:
        """Stop processing and release resources."""
        if self.camera is not None:
            self.camera.stop()
        if self.debug:
            cv2.destroyAllWindows()
        logger.info("DartPipeline stopped")

    def process_frame(self) -> dict | None:
        """Process one frame. Returns score dict if dart detected, else None."""
        if self.camera is None:
            return None

        ret, frame = self.camera.read()
        if not ret or frame is None:
            return None

        self.fps_counter.update()

        # 1. Preprocessing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        enhanced = self.clahe.apply(gray)

        # 2. ROI Extraction
        roi = self.roi_processor.warp_roi(enhanced)
        self._last_roi = roi

        # 3. Motion Gating
        motion_mask, has_motion = self.motion_detector.detect(roi)
        self._last_motion_mask = motion_mask

        if not has_motion:
            self._update_annotated_frame(frame, roi, None)
            return None

        # 4. Dart Detection (only when motion detected)
        detection = self.dart_detector.detect(roi, motion_mask)

        if detection is None:
            self._update_annotated_frame(frame, roi, motion_mask)
            return None

        # 5. Scoring
        center_x = self.roi_processor.roi_size[0] // 2
        center_y = self.roi_processor.roi_size[1] // 2
        # Use calibrated double-outer radius if available
        radii_px = self.calibration.get_radii_px()
        if radii_px and len(radii_px) == 6 and radii_px[-1] > 0:
            radius_px = radii_px[-1]  # double_outer in pixels
        else:
            radius_px = float(min(center_x, center_y))

        score_result = self.field_mapper.point_to_score(
            detection.center[0], detection.center[1],
            center_x, center_y, radius_px
        )

        # Add ROI coordinates for exact hit positioning
        score_result["roi_x"] = detection.center[0]
        score_result["roi_y"] = detection.center[1]

        # 6. Callback — pass both score_result and detection
        if self.on_dart_detected:
            self.on_dart_detected(score_result, detection)

        self._last_score = score_result
        self._update_annotated_frame(frame, roi, motion_mask, detection, score_result)
        return score_result

    def set_calibration(self, src_points: np.ndarray, dst_points: np.ndarray) -> None:
        """Update calibration (from web frontend or CLI)."""
        self.roi_processor.set_homography(src_points, dst_points)
        self.motion_detector.reset()
        logger.info("Calibration updated, motion detector reset")

    def reset_turn(self) -> None:
        """Reset detector state for new turn (after darts removed)."""
        self.dart_detector.reset()
        if self.on_dart_removed:
            self.on_dart_removed()
        logger.info("Turn reset — dart detector cleared")

    def get_annotated_frame(self) -> np.ndarray | None:
        """Get current frame with HUD overlay (for MJPEG stream)."""
        return self._last_annotated_frame

    def get_roi_preview(self) -> np.ndarray | None:
        """Get the current ROI-warped frame for calibration preview."""
        if self.camera is None:
            return None
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        enhanced = self.clahe.apply(gray)
        roi = self.roi_processor.warp_roi(enhanced)
        if len(roi.shape) == 2:
            roi = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        return roi

    def get_field_overlay(self) -> np.ndarray | None:
        """Get current ROI frame with dartboard field boundaries drawn."""
        if self.camera is None:
            return None
        ret, frame = self.camera.read()
        if not ret or frame is None:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        enhanced = self.clahe.apply(gray)
        roi = self.roi_processor.warp_roi(enhanced)
        if len(roi.shape) == 2:
            overlay = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        else:
            overlay = roi.copy()

        self._draw_field_overlay(overlay)
        return overlay

    def _draw_field_overlay(self, overlay: np.ndarray) -> None:
        """Draw dartboard field boundaries on an overlay image."""
        h, w = overlay.shape[:2]
        cx, cy = w // 2, h // 2

        # Use calibrated double-outer radius if available
        radii_px = self.calibration.get_radii_px()
        if radii_px and len(radii_px) == 6 and radii_px[-1] > 0:
            radius = radii_px[-1]  # double_outer in pixels
        else:
            radius = min(cx, cy)

        # Draw ring circles
        ring_fractions = list(self.field_mapper.ring_radii.values())
        ring_colors = [
            (0, 0, 255),    # inner bull
            (0, 255, 0),    # outer bull
            (255, 255, 0),  # triple inner
            (255, 255, 0),  # triple outer
            (0, 165, 255),  # double inner
            (0, 165, 255),  # double outer
        ]
        for frac, color in zip(ring_fractions, ring_colors):
            r = int(frac * radius)
            cv2.circle(overlay, (cx, cy), r, color, 1)

        # Draw sector lines
        # Sector boundaries: 20 is centered at 12 o'clock (top).
        sector_angle = 18.0
        offset = 9.0
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

        # Draw sector number labels
        sectors = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                   3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
        for i in range(20):
            angle_deg = -90 - offset + (i + 0.5) * sector_angle
            angle_rad = math.radians(angle_deg)
            label_r = 0.85 * radius
            lx = int(cx + label_r * math.cos(angle_rad))
            ly = int(cy + label_r * math.sin(angle_rad))
            cv2.putText(overlay, str(sectors[i]), (lx - 8, ly + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

    def _update_annotated_frame(self, frame: np.ndarray, roi: np.ndarray,
                                 motion_mask: np.ndarray | None,
                                 detection=None, score_result: dict | None = None) -> None:
        """Draw debug HUD overlay on frame, including optional vision overlays."""
        annotated = frame.copy()
        fps = self.fps_counter.fps()

        # FPS (top left, green)
        cv2.putText(annotated, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Calibration status (top right)
        cal_status = "CAL: OK" if self.roi_processor.homography is not None else "CAL: NONE"
        cal_color = (0, 255, 0) if self.roi_processor.homography is not None else (0, 0, 255)
        cv2.putText(annotated, cal_status, (frame.shape[1] - 150, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, cal_color, 2)

        # Confirmed darts count
        dart_count = len(self.dart_detector.get_all_confirmed())
        cv2.putText(annotated, f"Darts: {dart_count}/3", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Detection marker
        if detection is not None and score_result is not None:
            cv2.circle(annotated, detection.center, 15, (0, 0, 255), 2)
            label = f"{score_result['ring'].upper()} {score_result['score']}"
            cv2.putText(annotated, label,
                        (detection.center[0] + 20, detection.center[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # --- Motion mask overlay (large, bottom-right corner) ---
        if self.show_overlay_motion and motion_mask is not None:
            fh, fw = annotated.shape[:2]
            overlay_size = min(fw // 2, fh // 2, 320)
            margin = 10
            overlay_y = fh - overlay_size - margin
            overlay_x = fw - overlay_size - margin
            self._composite_overlay(annotated, motion_mask, overlay_x, overlay_y,
                                     overlay_size, "MOTION")

        self._last_annotated_frame = annotated

        if self.debug:
            cv2.imshow("Dart Vision", annotated)
            if len(roi.shape) == 2:
                roi_display = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
            else:
                roi_display = roi
            cv2.imshow("ROI", roi_display)
            if motion_mask is not None:
                cv2.imshow("Motion", motion_mask)
            cv2.waitKey(1)

    def _composite_overlay(self, frame: np.ndarray, overlay_img: np.ndarray,
                            x: int, y: int, size: int, label: str) -> None:
        """Resize and composite a small overlay image onto the main frame."""
        if x < 0 or y < 0:
            return
        try:
            if len(overlay_img.shape) == 2:
                overlay_bgr = cv2.cvtColor(overlay_img, cv2.COLOR_GRAY2BGR)
            else:
                overlay_bgr = overlay_img
            resized = cv2.resize(overlay_bgr, (size, size))
            # Bounds check
            fh, fw = frame.shape[:2]
            if y + size > fh or x + size > fw:
                return
            frame[y:y + size, x:x + size] = resized
            # Border
            cv2.rectangle(frame, (x, y), (x + size, y + size), (100, 100, 100), 1)
            # Label
            cv2.putText(frame, label, (x + 4, y + 14),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        except Exception:
            pass  # Silent fail if overlay doesn't fit


def main() -> None:
    """CLI entry point for standalone pipeline testing."""
    parser = argparse.ArgumentParser(description="Dart Vision CV Pipeline")
    parser.add_argument("--source", type=int, default=0, help="Camera source index")
    parser.add_argument("--debug", action="store_true", help="Show debug windows")
    args = parser.parse_args()

    setup_logging()

    def on_dart(score: dict, detection=None) -> None:
        ring = score["ring"]
        points = score["score"]
        sector = score["sector"]
        mult = score["multiplier"]
        logger.info("SCORE: %s %d (sector=%d, x%d)", ring, points, sector, mult)

    pipeline = DartPipeline(
        camera_src=args.source,
        on_dart_detected=on_dart,
        debug=args.debug
    )

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
