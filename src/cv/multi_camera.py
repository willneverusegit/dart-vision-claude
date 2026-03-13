"""Multi-camera pipeline: coordinate multiple DartPipelines and fuse results."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import numpy as np

from src.cv.pipeline import DartPipeline
from src.cv.stereo_utils import CameraParams, triangulate_point, point_3d_to_board_2d
from src.cv.geometry import BoardGeometry, BOARD_RADIUS_MM
from src.utils.config import get_stereo_pair

logger = logging.getLogger(__name__)

# Maximum time difference (seconds) between detections from two cameras
# to be considered "simultaneous" (software sync).
MAX_DETECTION_TIME_DIFF_S = 0.15  # 150ms


class MultiCameraPipeline:
    """Orchestrate multiple DartPipeline instances and fuse detections."""

    def __init__(
        self,
        camera_configs: list[dict],
        on_multi_dart_detected: Callable[[dict], None] | None = None,
        debug: bool = False,
    ) -> None:
        """
        Args:
            camera_configs: List of dicts, each with keys:
                - camera_id (str): Unique name, e.g. "cam_left"
                - src (int | str): Camera source index or video path
                - camera_params (CameraParams | None): For triangulation
            on_multi_dart_detected: Callback with fused score dict.
            debug: Enable debug visualization.
        """
        self.camera_configs = camera_configs
        self.on_multi_dart_detected = on_multi_dart_detected
        self.debug = debug

        self._pipelines: dict[str, DartPipeline] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._detection_buffer: dict[str, dict] = {}  # camera_id -> latest detection
        self._buffer_lock = threading.Lock()
        self._running = False
        self._fusion_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start all camera pipelines in separate threads."""
        self._running = True

        for cfg in self.camera_configs:
            cam_id = cfg["camera_id"]
            src = cfg.get("src", 0)

            pipeline = DartPipeline(
                camera_src=src,
                on_dart_detected=lambda score, det, _id=cam_id: self._on_single_detection(_id, score, det),
                debug=self.debug,
            )

            # Configure pipeline with camera-specific calibration
            from src.cv.board_calibration import BoardCalibrationManager
            from src.cv.camera_calibration import CameraCalibrationManager
            pipeline.board_calibration = BoardCalibrationManager(
                camera_id=cam_id,
            )
            pipeline.camera_calibration = CameraCalibrationManager(
                camera_id=cam_id,
            )

            self._pipelines[cam_id] = pipeline

            thread = threading.Thread(
                target=self._run_pipeline_loop,
                args=(cam_id, pipeline),
                daemon=True,
                name=f"cv-pipeline-{cam_id}",
            )
            self._threads[cam_id] = thread
            thread.start()
            logger.info("Pipeline started for camera '%s' (src=%s)", cam_id, src)

        # Start fusion thread
        self._fusion_thread = threading.Thread(
            target=self._fusion_loop,
            daemon=True,
            name="cv-fusion",
        )
        self._fusion_thread.start()

    def stop(self) -> None:
        """Stop all pipelines."""
        self._running = False
        for cam_id, pipeline in self._pipelines.items():
            pipeline.stop()
            logger.info("Pipeline stopped for camera '%s'", cam_id)
        for thread in self._threads.values():
            thread.join(timeout=5.0)
        if self._fusion_thread:
            self._fusion_thread.join(timeout=5.0)

    def _run_pipeline_loop(self, cam_id: str, pipeline: DartPipeline) -> None:
        """Frame processing loop for a single camera."""
        try:
            pipeline.start()
        except Exception as e:
            logger.warning("Camera '%s' failed to start: %s", cam_id, e)
            return

        while self._running:
            try:
                pipeline.process_frame()
            except Exception as e:
                logger.debug("Frame error on '%s': %s", cam_id, e)
            time.sleep(0.001)

    def _on_single_detection(self, camera_id: str, score_result: dict, detection) -> None:
        """Callback from a single pipeline. Buffer detection for fusion."""
        with self._buffer_lock:
            self._detection_buffer[camera_id] = {
                "camera_id": camera_id,
                "score_result": score_result,
                "detection": detection,
                "timestamp": time.time(),
            }

    def _fusion_loop(self) -> None:
        """Periodically check detection buffer and fuse multi-camera results."""
        while self._running:
            time.sleep(0.05)  # 20Hz check rate
            self._try_fuse()

    def _try_fuse(self) -> None:
        """Attempt to fuse detections from multiple cameras."""
        with self._buffer_lock:
            if len(self._detection_buffer) < 2:
                # Single camera fallback: emit the lone detection
                if len(self._detection_buffer) == 1:
                    entry = list(self._detection_buffer.values())[0]
                    age = time.time() - entry["timestamp"]
                    if age > MAX_DETECTION_TIME_DIFF_S:
                        # Detection is old enough that the other camera won't
                        # catch up -> use single-camera result as fallback
                        result = dict(entry["score_result"])
                        result["source"] = "single"
                        result["camera_id"] = entry["camera_id"]
                        self._emit(result)
                        self._detection_buffer.clear()
                return

            # Check if detections are temporally close enough
            entries = list(self._detection_buffer.values())
            timestamps = [e["timestamp"] for e in entries]
            if max(timestamps) - min(timestamps) > MAX_DETECTION_TIME_DIFF_S:
                # Too far apart — use the most recent single detection
                latest = max(entries, key=lambda e: e["timestamp"])
                result = dict(latest["score_result"])
                result["source"] = "single_timeout"
                result["camera_id"] = latest["camera_id"]
                self._emit(result)
                self._detection_buffer.clear()
                return

            # Two+ cameras detected within time window -> attempt triangulation
            cam_params = {
                cfg["camera_id"]: cfg.get("camera_params")
                for cfg in self.camera_configs
            }

            # Try triangulation for first pair with valid CameraParams
            triangulated = False
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    p1 = cam_params.get(entries[i]["camera_id"])
                    p2 = cam_params.get(entries[j]["camera_id"])
                    if p1 is None or p2 is None:
                        continue

                    det1 = entries[i]["detection"]
                    det2 = entries[j]["detection"]
                    if det1 is None or det2 is None:
                        continue

                    tri = triangulate_point(
                        det1.center, det2.center, p1, p2,
                    )
                    if tri.valid:
                        board_x_mm, board_y_mm = point_3d_to_board_2d(tri.point_3d)
                        # Convert mm to board score via geometry of first camera
                        pipeline_1 = self._pipelines.get(entries[i]["camera_id"])
                        if pipeline_1 and pipeline_1.geometry:
                            geo = pipeline_1.geometry
                            radius_px = geo.double_outer_radius_px
                            mm_per_px = BOARD_RADIUS_MM / radius_px if radius_px > 0 else 1.0
                            ox, oy = geo.optical_center_px
                            roi_x = ox + board_x_mm / mm_per_px
                            roi_y = oy + board_y_mm / mm_per_px
                            hit = geo.point_to_score(roi_x, roi_y)
                            result = geo.hit_to_dict(hit)
                            result["source"] = "triangulation"
                            result["reprojection_error"] = tri.reprojection_error
                            self._emit(result)
                            triangulated = True
                            break
                if triangulated:
                    break

            if not triangulated:
                # Voting fallback: use best single-camera result
                result = self._voting_fallback(entries)
                self._emit(result)

            self._detection_buffer.clear()

    def _voting_fallback(self, entries: list[dict]) -> dict:
        """When triangulation fails, use best single-camera result or average."""
        # Pick the detection with highest confidence
        best = max(entries, key=lambda e: getattr(e.get("detection"), "confidence", 0))
        result = dict(best["score_result"])
        result["source"] = "voting_fallback"
        result["camera_id"] = best["camera_id"]
        return result

    def _emit(self, score_result: dict) -> None:
        """Emit fused detection via callback."""
        if self.on_multi_dart_detected:
            self.on_multi_dart_detected(score_result)

    def reset_all(self) -> None:
        """Reset detectors on all pipelines (darts removed)."""
        for pipeline in self._pipelines.values():
            pipeline.reset_turn()
        with self._buffer_lock:
            self._detection_buffer.clear()

    def get_pipelines(self) -> dict[str, DartPipeline]:
        """Expose individual pipelines for frame access, overlays, etc."""
        return dict(self._pipelines)
