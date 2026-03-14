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
        self._camera_errors: dict[str, str] = {}  # camera_id -> error message

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
            self._camera_errors[cam_id] = str(e)
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
                        logger.info("Single-camera fallback: camera_id='%s'", entry["camera_id"])
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
                logger.info("Timeout fallback: camera_id='%s' (detections too far apart)", latest["camera_id"])
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
                    if tri.valid and abs(tri.point_3d[2]) <= 0.05:
                        # Z plausibility: |Z| <= 50mm (board plane ~ Z=0)
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
                            logger.info(
                                "Triangulation: cameras='%s','%s' reproj=%.2f Z=%.4f",
                                entries[i]["camera_id"], entries[j]["camera_id"],
                                tri.reprojection_error, tri.point_3d[2],
                            )
                            self._emit(result)
                            triangulated = True
                            break
                    elif tri.valid and abs(tri.point_3d[2]) > 0.05:
                        logger.info(
                            "Triangulation Z implausible (Z=%.4f) for cameras '%s','%s' — voting fallback",
                            tri.point_3d[2], entries[i]["camera_id"], entries[j]["camera_id"],
                        )
                if triangulated:
                    break

            if not triangulated:
                # Voting fallback: use best single-camera result
                result = self._voting_fallback(entries)
                self._emit(result)

            self._detection_buffer.clear()

    def _voting_fallback(self, entries: list[dict]) -> dict:
        """When triangulation fails, use confidence-weighted voting.

        - Weights each camera's score by its detection confidence.
        - For ≥3 cameras, uses median of total_score instead of mean.
        - Falls back to highest-confidence single result for non-numeric scores.
        """
        # Extract confidences
        confidences = []
        for e in entries:
            det = e.get("detection")
            conf = getattr(det, "confidence", 0.0) if det else 0.0
            confidences.append(conf)

        # Try confidence-weighted scoring
        total_conf = sum(confidences)
        if total_conf > 0 and all("total_score" in e.get("score_result", {}) for e in entries):
            scores = [e["score_result"]["total_score"] for e in entries]

            if len(entries) >= 3:
                # Median for ≥3 cameras (robust against outlier)
                sorted_scores = sorted(scores)
                mid = len(sorted_scores) // 2
                if len(sorted_scores) % 2 == 0:
                    weighted_score = (sorted_scores[mid - 1] + sorted_scores[mid]) / 2.0
                else:
                    weighted_score = sorted_scores[mid]
                logger.info(
                    "Voting fallback: median score=%s from %d cameras",
                    weighted_score, len(entries),
                )
            else:
                # Weighted average for 2 cameras
                weighted_score = sum(
                    s * c for s, c in zip(scores, confidences)
                ) / total_conf
                logger.info(
                    "Voting fallback: weighted score=%.1f (conf=%.2f,%.2f)",
                    weighted_score, *confidences,
                )

            # Use the result dict from the highest-confidence camera as base
            best_idx = confidences.index(max(confidences))
            result = dict(entries[best_idx]["score_result"])
            result["total_score"] = int(round(weighted_score))
            result["source"] = "voting_fallback"
            result["camera_id"] = entries[best_idx]["camera_id"]
            return result

        # Fallback: pick highest confidence
        best_idx = confidences.index(max(confidences))
        best = entries[best_idx]
        result = dict(best["score_result"])
        result["source"] = "voting_fallback"
        result["camera_id"] = best["camera_id"]
        logger.info(
            "Voting fallback: best confidence camera_id='%s' (conf=%.2f)",
            best["camera_id"], confidences[best_idx],
        )
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

    def get_camera_errors(self) -> dict[str, str]:
        """Return dict of camera_id -> error message for cameras that failed to start."""
        return dict(self._camera_errors)
