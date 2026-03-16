"""Multi-camera pipeline: coordinate multiple DartPipelines and fuse results."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import numpy as np

from src.cv.pipeline import DartPipeline
from src.cv.stereo_utils import (
    CameraParams,
    triangulate_point,
    point_3d_to_board_2d,
    transform_to_board_frame,
)
from src.cv.geometry import BoardGeometry, BOARD_RADIUS_MM
from src.utils.config import get_stereo_pair, get_board_transform

logger = logging.getLogger(__name__)

# Maximum time difference (seconds) between detections from two cameras
# to be considered "simultaneous" (software sync).
MAX_DETECTION_TIME_DIFF_S = 0.15  # 150ms

# Frame-rate target for each camera loop.  Keeps CPU usage bounded and gives
# the GIL breathing room when running 2-3 camera threads in parallel.
_TARGET_FPS = 30
_FRAME_INTERVAL_S = 1.0 / _TARGET_FPS  # ~0.0333 s

# Dart tip must be within this distance of the board face (in board frame Z)
# to be considered a valid hit.  Accounts for dart penetration (~5 mm),
# triangulation noise (~5 mm), and calibration error (~5 mm).
BOARD_DEPTH_TOLERANCE_M = 0.015  # 15 mm


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

        # Loaded from config at start() / reload_stereo_params()
        self._stereo_params: dict[str, CameraParams] = {}   # camera_id -> CameraParams
        self._board_transforms: dict[str, dict] = {}          # camera_id -> {R_cb, t_cb}

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
                capture_width=cfg.get("capture_width"),
                capture_height=cfg.get("capture_height"),
                capture_fps=cfg.get("capture_fps"),
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

        # Load stereo extrinsics and board transforms from config
        self._load_extrinsics()

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
        """Frame processing loop for a single camera, rate-limited to _TARGET_FPS."""
        try:
            pipeline.start()
        except Exception as e:
            logger.warning("Camera '%s' failed to start: %s", cam_id, e)
            self._camera_errors[cam_id] = str(e)
            return

        while self._running:
            t0 = time.monotonic()
            try:
                pipeline.process_frame()
            except Exception as e:
                logger.debug("Frame error on '%s': %s", cam_id, e)
            elapsed = time.monotonic() - t0
            sleep_s = max(0.0, _FRAME_INTERVAL_S - elapsed)
            if sleep_s > 0:
                time.sleep(sleep_s)

    def _load_extrinsics(self) -> None:
        """Load stereo pair extrinsics and board transforms from config files.

        Called at start() and by reload_stereo_params() for hot-reloading.
        Populates self._stereo_params and self._board_transforms.
        """
        # --- Board transforms (camera frame -> board frame) ---
        for cfg in self.camera_configs:
            cam_id = cfg["camera_id"]
            bt = get_board_transform(cam_id)
            if bt is not None:
                try:
                    self._board_transforms[cam_id] = {
                        "R_cb": np.array(bt["R_cb"], dtype=np.float64).reshape(3, 3),
                        "t_cb": np.array(bt["t_cb"], dtype=np.float64).reshape(3),
                    }
                    logger.info("Loaded board_transform for camera '%s'", cam_id)
                except Exception as e:
                    logger.warning("Invalid board_transform for '%s': %s", cam_id, e)
            else:
                logger.warning(
                    "No board_transform found for camera '%s' — triangulation will be skipped",
                    cam_id,
                )

        # --- Stereo pair extrinsics (inter-camera R, T) ---
        for i, cfg_a in enumerate(self.camera_configs):
            for cfg_b in self.camera_configs[i + 1:]:
                cam_a = cfg_a["camera_id"]
                cam_b = cfg_b["camera_id"]
                pair_data = get_stereo_pair(cam_a, cam_b)
                if pair_data is None:
                    logger.warning(
                        "No stereo pair data for '%s'--'%s' — triangulation disabled for this pair",
                        cam_a, cam_b,
                    )
                    continue

                pipe_a = self._pipelines.get(cam_a)
                pipe_b = self._pipelines.get(cam_b)
                if pipe_a is None or pipe_b is None:
                    continue

                intr_a = pipe_a.camera_calibration.get_intrinsics()
                intr_b = pipe_b.camera_calibration.get_intrinsics()
                if intr_a is None or intr_b is None:
                    logger.warning(
                        "Missing intrinsics for '%s' or '%s' — triangulation disabled for this pair",
                        cam_a, cam_b,
                    )
                    continue

                # Camera 1 is the world origin (identity extrinsics)
                self._stereo_params[cam_a] = CameraParams(
                    camera_id=cam_a,
                    camera_matrix=intr_a.camera_matrix,
                    dist_coeffs=intr_a.dist_coeffs,
                    R=np.eye(3, dtype=np.float64),
                    T=np.zeros((3, 1), dtype=np.float64),
                )
                # Camera 2: relative pose from stereo calibration (cam1 -> cam2)
                self._stereo_params[cam_b] = CameraParams(
                    camera_id=cam_b,
                    camera_matrix=intr_b.camera_matrix,
                    dist_coeffs=intr_b.dist_coeffs,
                    R=np.array(pair_data["R"], dtype=np.float64).reshape(3, 3),
                    T=np.array(pair_data["T"], dtype=np.float64).reshape(3, 1),
                )
                logger.info(
                    "Loaded stereo params for pair '%s'--'%s'", cam_a, cam_b
                )

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
            # Use self._stereo_params (populated by _load_extrinsics at startup)
            cam_params = self._stereo_params

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
                    if not tri.valid:
                        continue

                    # Transform from camera-1 frame to board frame.
                    # Without this, point_3d[2] is the distance to the camera
                    # lens — not the dart's depth into the board.
                    bt = self._board_transforms.get(entries[i]["camera_id"])
                    if bt is None:
                        logger.debug(
                            "No board_transform for camera '%s' — skipping triangulation",
                            entries[i]["camera_id"],
                        )
                        continue

                    p_board = transform_to_board_frame(
                        tri.point_3d, bt["R_cb"], bt["t_cb"]
                    )

                    # Z plausibility in board frame: dart tip must be within
                    # BOARD_DEPTH_TOLERANCE_M of the board face (Z = 0).
                    if abs(p_board[2]) > BOARD_DEPTH_TOLERANCE_M:
                        logger.info(
                            "Triangulation Z implausible in board frame "
                            "(Z=%.4f m) for cameras '%s','%s' — voting fallback",
                            p_board[2],
                            entries[i]["camera_id"],
                            entries[j]["camera_id"],
                        )
                        continue

                    board_x_mm, board_y_mm = point_3d_to_board_2d(p_board)
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
                            "Triangulation: cameras='%s','%s' reproj=%.2f Z_board=%.4f",
                            entries[i]["camera_id"], entries[j]["camera_id"],
                            tri.reprojection_error, p_board[2],
                        )
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

    def reload_stereo_params(self) -> None:
        """Hot-reload stereo extrinsics and board transforms from config files.

        Call this after running stereo or board-pose calibration to pick up
        the new data without restarting the pipeline.
        """
        logger.info("Reloading stereo extrinsics and board transforms...")
        self._stereo_params.clear()
        self._board_transforms.clear()
        self._load_extrinsics()
        logger.info(
            "Stereo params reloaded: %d camera params, %d board transforms",
            len(self._stereo_params), len(self._board_transforms),
        )

    def get_pipelines(self) -> dict[str, DartPipeline]:
        """Expose individual pipelines for frame access, overlays, etc."""
        return dict(self._pipelines)

    def get_camera_errors(self) -> dict[str, str]:
        """Return dict of camera_id -> error message for cameras that failed to start."""
        return dict(self._camera_errors)
