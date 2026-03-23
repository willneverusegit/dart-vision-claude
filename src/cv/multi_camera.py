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
    triangulate_multi_pair,
    triangulate_point,
    point_3d_to_board_2d,
    transform_to_board_frame,
)
from src.cv.geometry import BoardGeometry, BOARD_RADIUS_MM
from src.utils.config import get_stereo_pair, get_board_transform, get_sync_depth_config, get_governor_config
from src.utils.triangulation_telemetry import TriangulationTelemetry

logger = logging.getLogger(__name__)

# Maximum time difference (seconds) between detections from two cameras
# to be considered "simultaneous" (software sync).
MAX_DETECTION_TIME_DIFF_S = 0.5  # 500ms — FrameDiff settle timing varies between cameras

# Frame-rate target for each camera loop.  Keeps CPU usage bounded and gives
# the GIL breathing room when running 2-3 camera threads in parallel.
_TARGET_FPS = 30
_FRAME_INTERVAL_S = 1.0 / _TARGET_FPS  # ~0.0333 s

# Dart tip must be within this distance of the board face (in board frame Z)
# to be considered a valid hit.  Accounts for dart penetration (~30 mm),
# triangulation noise (~20 mm), calibration error (~20 mm), and the fact
# that the two cameras may detect slightly different points on the dart.
BOARD_DEPTH_TOLERANCE_M = 0.30  # 300 mm — generous; voting fallback handles bad results


class FPSGovernor:
    """Adaptive FPS control based on processing time.

    Tracks moving average of frame processing time and reduces
    target FPS when the pipeline can't keep up.
    """

    def __init__(
        self,
        target_fps: int = 30,
        min_fps: int = 10,
        is_primary: bool = True,
        buffer_max_depth: int = 5,
    ) -> None:
        self._target_fps = target_fps
        self._min_fps = min_fps
        self._is_primary = is_primary
        self._effective_fps = float(target_fps)
        self._processing_times: list[float] = []  # ring buffer
        self._max_samples = 30
        self._overload_count = 0
        self._overload_threshold = 10  # consecutive overloaded frames before reducing
        self._buffer_max_depth = buffer_max_depth
        self._frames_dropped = 0
        self._frames_total = 0

    def should_skip_frame(self, buffer_depth: int) -> bool:
        """Return True if the frame should be skipped due to backpressure.

        Args:
            buffer_depth: Current number of entries in the detection buffer.
        """
        if buffer_depth >= self._buffer_max_depth:
            self._frames_dropped += 1
            return True
        return False

    def record_frame_time(self, elapsed_s: float) -> None:
        """Record processing time for one frame."""
        self._frames_total += 1
        self._processing_times.append(elapsed_s)
        if len(self._processing_times) > self._max_samples:
            self._processing_times.pop(0)

        frame_budget = 1.0 / self._effective_fps
        if elapsed_s > 0.8 * frame_budget:
            self._overload_count += 1
        else:
            self._overload_count = max(0, self._overload_count - 1)

        # Reduce FPS if consistently overloaded (but not for primary camera)
        if self._overload_count >= self._overload_threshold and not self._is_primary:
            new_fps = max(self._min_fps, self._effective_fps * 0.8)
            if new_fps < self._effective_fps:
                logger.info("FPSGovernor: reducing FPS %.0f → %.0f (overloaded)", self._effective_fps, new_fps)
                self._effective_fps = new_fps
                self._overload_count = 0

        # Recovery: if avg processing time is well under budget, try increasing
        if len(self._processing_times) >= self._max_samples:
            avg = sum(self._processing_times) / len(self._processing_times)
            target_budget = 1.0 / self._target_fps
            if avg < 0.5 * target_budget and self._effective_fps < self._target_fps:
                new_fps = min(self._target_fps, self._effective_fps * 1.1)
                if new_fps > self._effective_fps:
                    logger.info("FPSGovernor: recovering FPS %.0f → %.0f", self._effective_fps, new_fps)
                    self._effective_fps = new_fps

    @property
    def frame_interval_s(self) -> float:
        """Current frame interval based on effective FPS."""
        return 1.0 / self._effective_fps

    @property
    def effective_fps(self) -> float:
        return round(self._effective_fps, 1)

    def get_stats(self) -> dict:
        """Return governor statistics."""
        avg_time = sum(self._processing_times) / len(self._processing_times) if self._processing_times else 0.0
        return {
            "target_fps": self._target_fps,
            "effective_fps": self.effective_fps,
            "is_primary": self._is_primary,
            "avg_processing_ms": round(avg_time * 1000, 1),
            "overload_count": self._overload_count,
            "buffer_max_depth": self._buffer_max_depth,
            "frames_dropped": self._frames_dropped,
            "frames_total": self._frames_total,
        }


class MultiCameraPipeline:
    """Orchestrate multiple DartPipeline instances and fuse detections."""

    def __init__(
        self,
        camera_configs: list[dict],
        on_multi_dart_detected: Callable[[dict], None] | None = None,
        on_camera_errors_changed: Callable[[dict[str, str]], None] | None = None,
        debug: bool = False,
        sync_wait_s: float = 0.8,
        max_time_diff_s: float | None = None,
        depth_tolerance_m: float | None = None,
        depth_auto_adapt: bool = True,
        load_config_from_yaml: bool = True,
    ) -> None:
        """
        Args:
            camera_configs: List of dicts, each with keys:
                - camera_id (str): Unique name, e.g. "cam_left"
                - src (int | str): Camera source index or video path
            on_multi_dart_detected: Callback with fused score dict.
            debug: Enable debug visualization.
            sync_wait_s: Max wait time for 2nd camera after 1st detection.
            max_time_diff_s: Max allowed time diff between detections for sync.
                If None, loaded from config/multi_cam.yaml (or standard preset).
            depth_tolerance_m: Z-plausibility tolerance for board depth.
                If None, loaded from config/multi_cam.yaml (or standard preset).
            depth_auto_adapt: Auto-widen depth tolerance on high rejection rate.
            load_config_from_yaml: Load sync/depth/governor settings from YAML.
        """
        self.camera_configs = camera_configs
        self.on_multi_dart_detected = on_multi_dart_detected
        self.on_camera_errors_changed = on_camera_errors_changed
        self.debug = debug
        self._sync_wait_s = sync_wait_s
        self._depth_auto_adapt = depth_auto_adapt

        # Load sync/depth from config, with explicit args as overrides
        if load_config_from_yaml:
            try:
                sd_cfg = get_sync_depth_config()
            except Exception:
                sd_cfg = {"max_time_diff_s": MAX_DETECTION_TIME_DIFF_S, "depth_tolerance_m": BOARD_DEPTH_TOLERANCE_M}
            try:
                self._governor_config = get_governor_config()
            except Exception:
                self._governor_config = {"secondary_target_fps": 15, "min_fps": 10, "buffer_max_depth": 5}
        else:
            sd_cfg = {"max_time_diff_s": MAX_DETECTION_TIME_DIFF_S, "depth_tolerance_m": BOARD_DEPTH_TOLERANCE_M}
            self._governor_config = {"secondary_target_fps": 15, "min_fps": 10, "buffer_max_depth": 5}

        self._max_time_diff_s = max_time_diff_s if max_time_diff_s is not None else sd_cfg["max_time_diff_s"]
        self._depth_tolerance_m = depth_tolerance_m if depth_tolerance_m is not None else sd_cfg["depth_tolerance_m"]
        self._effective_depth_tolerance_m = self._depth_tolerance_m
        self._buffer_max_depth = self._governor_config["buffer_max_depth"]

        logger.info(
            "MultiCam config: max_time_diff=%.0fms depth_tol=%.1fmm buffer_max=%d",
            self._max_time_diff_s * 1000,
            self._depth_tolerance_m * 1000,
            self._buffer_max_depth,
        )

        self._pipelines: dict[str, DartPipeline] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._detection_buffer: dict[str, dict] = {}  # camera_id -> latest detection
        self._buffer_lock = threading.Lock()
        self._running = False
        self._fusion_thread: threading.Thread | None = None
        self._camera_errors: dict[str, dict] = {}  # camera_id -> {message, timestamp, level}
        self._consecutive_frame_errors: dict[str, int] = {}  # camera_id -> count
        self._per_camera_fps: dict[str, int] = {}
        self._governors: dict[str, FPSGovernor] = {}
        self._tri_telemetry = TriangulationTelemetry()
        self._viewing_angle_qualities: dict[str, float] = {}

        # Auto-reconnect settings
        self._max_reconnect_attempts = 5  # max attempts before giving up
        self._reconnect_base_delay_s = 2.0  # initial delay between reconnect attempts
        self._reconnect_max_delay_s = 30.0  # max backoff delay
        self._camera_degraded: set[str] = set()  # cameras that permanently failed

        # Loaded from config at start() / reload_stereo_params()
        self._stereo_params: dict[str, CameraParams] = {}   # camera_id -> CameraParams
        self._board_transforms: dict[str, dict] = {}          # camera_id -> {R_cb, t_cb}

    def start(self) -> None:
        """Start all camera pipelines in separate threads.

        Atomic: if any camera fails to initialize, all already-started
        pipelines are stopped and the exception propagates.
        """
        self._running = True
        started_ids: list[str] = []

        try:
            for cfg in self.camera_configs:
                cam_id = cfg["camera_id"]
                src = cfg.get("src", 0)

                per_fps = cfg.get("capture_fps", _TARGET_FPS)
                self._per_camera_fps[cam_id] = per_fps

                is_primary = cfg.get("priority", "primary") == "primary"
                gov_cfg = self._governor_config
                target = per_fps if is_primary else min(per_fps, gov_cfg["secondary_target_fps"])
                self._governors[cam_id] = FPSGovernor(
                    target_fps=target,
                    min_fps=gov_cfg["min_fps"],
                    is_primary=is_primary,
                    buffer_max_depth=gov_cfg["buffer_max_depth"],
                )

                pipeline = DartPipeline(
                    camera_src=src,
                    on_dart_detected=lambda score, det, _id=cam_id: self._on_single_detection(_id, score, det),
                    debug=self.debug,
                    capture_width=cfg.get("capture_width"),
                    capture_height=cfg.get("capture_height"),
                    capture_fps=per_fps,
                    diff_threshold=cfg.get("diff_threshold"),
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

                # Store per-camera exposure/gain config for application after start
                self._pipelines[cam_id] = pipeline
                self._apply_camera_profile(cam_id, cfg)

                thread = threading.Thread(
                    target=self._run_pipeline_loop,
                    args=(cam_id, pipeline),
                    daemon=True,
                    name=f"cv-pipeline-{cam_id}",
                )
                self._threads[cam_id] = thread
                thread.start()
                started_ids.append(cam_id)
                logger.info("Pipeline started for camera '%s' (src=%s)", cam_id, src)

            # Start fusion thread
            self._fusion_thread = threading.Thread(
                target=self._fusion_loop,
                daemon=True,
                name="cv-fusion",
            )
            self._fusion_thread.start()

            # Compute viewing angle quality for each camera
            for cfg in self.camera_configs:
                cam_id = cfg["camera_id"]
                pipeline = self._pipelines.get(cam_id)
                if pipeline:
                    vaq = pipeline.board_calibration.get_viewing_angle_quality()
                    self._viewing_angle_qualities[cam_id] = vaq
                    logger.info("Camera '%s' viewing_angle_quality=%.3f", cam_id, vaq)

            # Load stereo extrinsics and board transforms from config
            self._load_extrinsics()

        except Exception:
            # Rollback: stop all already-started pipelines so no threads leak
            logger.error("Multi-cam start() failed after starting %d cameras — rolling back", len(started_ids))
            self._running = False
            for cid in started_ids:
                try:
                    self._pipelines[cid].stop()
                except Exception:
                    pass
            for cid in started_ids:
                t = self._threads.get(cid)
                if t is not None:
                    t.join(timeout=3.0)
            if self._fusion_thread is not None:
                self._fusion_thread.join(timeout=2.0)
            raise

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
        """Frame processing loop for a single camera, rate-limited per-camera FPS.

        Includes auto-reconnect: if the pipeline fails to start or hits
        persistent frame errors, it attempts to restart the pipeline with
        exponential backoff.  After max attempts, the camera is marked as
        degraded and the loop exits gracefully.
        """
        if not self._start_pipeline_with_retry(cam_id, pipeline):
            return  # permanently failed, degraded

        self._apply_exposure_gain(cam_id, pipeline)

        governor = self._governors.get(cam_id)

        while self._running:
            # Backpressure: skip frame if detection buffer is full
            if governor:
                with self._buffer_lock:
                    buf_depth = len(self._detection_buffer)
                if governor.should_skip_frame(buf_depth):
                    time.sleep(governor.frame_interval_s)
                    continue

            t0 = time.monotonic()
            try:
                pipeline.process_frame()
                # Clear consecutive error counter on success
                if self._consecutive_frame_errors.get(cam_id, 0) > 0:
                    self._consecutive_frame_errors[cam_id] = 0
                    if cam_id in self._camera_errors:
                        self._clear_camera_error(cam_id)
            except Exception as e:
                self._consecutive_frame_errors[cam_id] = self._consecutive_frame_errors.get(cam_id, 0) + 1
                count = self._consecutive_frame_errors[cam_id]
                logger.debug("Frame error on '%s': %s (consecutive=%d)", cam_id, e, count)
                if count == 10:
                    self._set_camera_error(cam_id, f"Wiederholte Frame-Fehler: {e}", level="warning")
                elif count >= 50:
                    self._set_camera_error(cam_id, f"Kamera antwortet nicht: {e}", level="error")
                    # Attempt auto-reconnect
                    logger.warning("Camera '%s': 50 consecutive errors, attempting auto-reconnect...", cam_id)
                    self._consecutive_frame_errors[cam_id] = 0
                    if self._attempt_reconnect(cam_id, pipeline):
                        self._apply_exposure_gain(cam_id, pipeline)
                        continue
                    else:
                        # Reconnect failed permanently
                        return
            elapsed = time.monotonic() - t0
            if governor:
                governor.record_frame_time(elapsed)
                sleep_s = max(0.0, governor.frame_interval_s - elapsed)
            else:
                sleep_s = max(0.0, _FRAME_INTERVAL_S - elapsed)
            if sleep_s > 0:
                time.sleep(sleep_s)

    def _start_pipeline_with_retry(self, cam_id: str, pipeline: DartPipeline) -> bool:
        """Try to start a pipeline with exponential backoff retries.

        Returns True if started successfully, False if permanently failed.
        """
        delay = self._reconnect_base_delay_s
        for attempt in range(1, self._max_reconnect_attempts + 1):
            try:
                pipeline.start()
                logger.info("Camera '%s' started (attempt %d)", cam_id, attempt)
                return True
            except Exception as e:
                logger.warning(
                    "Camera '%s' failed to start (attempt %d/%d): %s",
                    cam_id, attempt, self._max_reconnect_attempts, e,
                )
                self._set_camera_error(
                    cam_id,
                    f"Start fehlgeschlagen (Versuch {attempt}/{self._max_reconnect_attempts}): {e}",
                    level="warning" if attempt < self._max_reconnect_attempts else "error",
                )
                if attempt < self._max_reconnect_attempts and self._running:
                    time.sleep(delay)
                    delay = min(delay * 2, self._reconnect_max_delay_s)

        # All attempts exhausted
        self._degrade_camera(cam_id)
        return False

    def _attempt_reconnect(self, cam_id: str, pipeline: DartPipeline) -> bool:
        """Attempt to reconnect a camera by stopping and restarting its pipeline.

        Returns True on success, False if permanently failed (camera degraded).
        """
        self._set_camera_error(cam_id, "Auto-Reconnect laeuft...", level="warning")
        logger.info("Camera '%s': stopping pipeline for reconnect...", cam_id)

        try:
            pipeline.stop()
        except Exception as e:
            logger.debug("Camera '%s': error during stop: %s", cam_id, e)

        delay = self._reconnect_base_delay_s
        for attempt in range(1, self._max_reconnect_attempts + 1):
            if not self._running:
                return False
            time.sleep(delay)

            try:
                # Rebuild camera source and restart
                pipeline.camera = pipeline._build_camera_source()
                pipeline.camera.start()
                # Re-init detector state
                if hasattr(pipeline, 'detector') and pipeline.detector is not None:
                    pipeline.detector.reset()

                logger.info("Camera '%s': reconnect successful (attempt %d)", cam_id, attempt)
                self._clear_camera_error(cam_id)
                return True
            except Exception as e:
                logger.warning(
                    "Camera '%s': reconnect attempt %d/%d failed: %s",
                    cam_id, attempt, self._max_reconnect_attempts, e,
                )
                self._set_camera_error(
                    cam_id,
                    f"Reconnect fehlgeschlagen (Versuch {attempt}/{self._max_reconnect_attempts}): {e}",
                    level="warning" if attempt < self._max_reconnect_attempts else "error",
                )
                delay = min(delay * 2, self._reconnect_max_delay_s)

        # All reconnect attempts failed
        self._degrade_camera(cam_id)
        return False

    def _degrade_camera(self, cam_id: str) -> None:
        """Mark a camera as permanently degraded."""
        self._camera_degraded.add(cam_id)
        remaining = [c for c in self._pipelines if c not in self._camera_degraded]
        self._set_camera_error(
            cam_id,
            f"Kamera dauerhaft ausgefallen — degradiert. Verbleibende Kameras: {remaining}",
            level="error",
        )
        logger.error(
            "Camera '%s' permanently degraded. Remaining cameras: %s",
            cam_id, remaining,
        )

    def _apply_exposure_gain(self, cam_id: str, pipeline: DartPipeline) -> None:
        """Apply exposure/gain settings from config to a pipeline's camera."""
        for cfg in self.camera_configs:
            if cfg["camera_id"] == cam_id:
                cam = getattr(pipeline, "camera", None)
                if cam is not None and hasattr(cam, "set_exposure"):
                    exposure = cfg.get("exposure")
                    if exposure is not None:
                        cam.set_exposure(exposure)
                    gain = cfg.get("gain")
                    if gain is not None:
                        cam.set_gain(gain)
                break

    def reconnect_camera(self, cam_id: str) -> dict:
        """Manually trigger a reconnect for a specific camera.

        Returns a status dict with success/failure info.
        """
        if cam_id not in self._pipelines:
            return {"ok": False, "error": f"Kamera '{cam_id}' nicht gefunden"}

        pipeline = self._pipelines[cam_id]

        # Remove from degraded set so it can be retried
        self._camera_degraded.discard(cam_id)
        self._consecutive_frame_errors[cam_id] = 0

        logger.info("Manual reconnect requested for camera '%s'", cam_id)

        # Stop and restart in a background thread to not block the API
        def _do_reconnect():
            success = self._attempt_reconnect(cam_id, pipeline)
            if success:
                self._apply_exposure_gain(cam_id, pipeline)
                # Restart the processing loop in a new thread
                thread = threading.Thread(
                    target=self._run_pipeline_loop,
                    args=(cam_id, pipeline),
                    daemon=True,
                    name=f"cv-pipeline-{cam_id}",
                )
                self._threads[cam_id] = thread
                thread.start()

        reconnect_thread = threading.Thread(
            target=_do_reconnect,
            daemon=True,
            name=f"reconnect-{cam_id}",
        )
        reconnect_thread.start()

        return {"ok": True, "message": f"Reconnect fuer '{cam_id}' gestartet"}

    def get_degraded_cameras(self) -> list[str]:
        """Return list of permanently degraded camera IDs."""
        return list(self._camera_degraded)

    def _apply_camera_profile(self, cam_id: str, cfg: dict) -> None:
        """Log per-camera profile settings (exposure/gain applied after start)."""
        profile_keys = ("exposure", "gain", "diff_threshold", "capture_fps")
        active = {k: cfg[k] for k in profile_keys if k in cfg}
        if active:
            logger.info("Camera '%s' profile: %s", cam_id, active)

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

                # Warn if lens calibration is newer than stereo calibration
                stereo_utc = pair_data.get("calibrated_utc")
                if stereo_utc:
                    for cam_id, pipe in [(cam_a, pipe_a), (cam_b, pipe_b)]:
                        lens_utc = pipe.camera_calibration._config_io.get_config().get(
                            "lens_last_update_utc"
                        )
                        if lens_utc and lens_utc > stereo_utc:
                            logger.warning(
                                "STEREO CALIBRATION STALE: Lens calibration for '%s' (%s) "
                                "is newer than stereo calibration (%s). "
                                "Triangulation will likely fail — please redo stereo calibration!",
                                cam_id, lens_utc[:19], stereo_utc[:19],
                            )

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
                    if age > self._sync_wait_s:
                        # Detection is old enough that the other camera won't
                        # catch up -> use single-camera result as fallback
                        result = dict(entry["score_result"])
                        result["source"] = "single"
                        result["camera_id"] = entry["camera_id"]
                        logger.info("Single-camera fallback: camera_id='%s'", entry["camera_id"])
                        self._tri_telemetry.record_attempt("single_fallback")
                        self._emit(result)
                        self._detection_buffer.clear()
                return

            # Check if detections are temporally close enough
            entries = list(self._detection_buffer.values())
            timestamps = [e["timestamp"] for e in entries]
            if max(timestamps) - min(timestamps) > self._max_time_diff_s:
                # Too far apart — use the most recent single detection
                latest = max(entries, key=lambda e: e["timestamp"])
                result = dict(latest["score_result"])
                result["source"] = "single_timeout"
                result["camera_id"] = latest["camera_id"]
                time_diff = max(timestamps) - min(timestamps)
                logger.info(
                    "Timeout fallback: camera_id='%s' (time_diff=%.0fms, max=%.0fms)",
                    latest["camera_id"], time_diff * 1000, self._max_time_diff_s * 1000,
                )
                self._emit(result)
                self._detection_buffer.clear()
                return

            # Two+ cameras detected within time window -> attempt triangulation
            # Use self._stereo_params (populated by _load_extrinsics at startup)
            cam_params = self._stereo_params

            # Multi-pair triangulation with outlier rejection
            triangulated = False
            tri_result = triangulate_multi_pair(
                detections=[{"camera_id": e["camera_id"], "detection": e["detection"]} for e in entries],
                camera_params=cam_params,
                board_transforms=self._board_transforms,
                depth_tolerance_m=self._effective_depth_tolerance_m,
            )

            if tri_result is not None and not tri_result.get("failed"):
                # Convert mm to board score via geometry of first camera
                board_x_mm = tri_result["board_x_mm"]
                board_y_mm = tri_result["board_y_mm"]
                # Find first pipeline with geometry
                pipeline_1 = None
                for e in entries:
                    p = self._pipelines.get(e["camera_id"])
                    if p and p.geometry:
                        pipeline_1 = p
                        break

                if pipeline_1:
                    geo = pipeline_1.geometry
                    radius_px = geo.double_outer_radius_px
                    mm_per_px = BOARD_RADIUS_MM / radius_px if radius_px > 0 else 1.0
                    ox, oy = geo.optical_center_px
                    roi_x = ox + board_x_mm / mm_per_px
                    roi_y = oy + board_y_mm / mm_per_px
                    hit = geo.point_to_score(roi_x, roi_y)
                    result = geo.hit_to_dict(hit)
                    result["source"] = "triangulation"
                    result["reprojection_error"] = tri_result["reprojection_error"]
                    result["pairs_used"] = tri_result["pairs_used"]
                    logger.info(
                        "Triangulation: pairs=%d reproj=%.2f",
                        tri_result["pairs_used"], tri_result["reprojection_error"],
                    )
                    self._tri_telemetry.record_attempt(
                        "triangulation",
                        tri_result["reprojection_error"],
                        tri_result.get("z_depth"),
                    )
                    self._emit(result)
                    triangulated = True

            if not triangulated:
                # Track Z-rejections for auto-adapt
                if tri_result and tri_result.get("failed"):
                    z_rej = tri_result.get("z_rejected", 0)
                    for _ in range(z_rej):
                        self._tri_telemetry.record_attempt("z_rejected")

                    # Depth auto-adapt: widen tolerance on high rejection rate
                    if self._depth_auto_adapt:
                        stats = self._tri_telemetry.get_summary()
                        total = stats.get("total_attempts", 0)
                        z_total = stats.get("z_rejected", 0)
                        if total >= 20 and z_total / total > 0.5:
                            widened = min(self._depth_tolerance_m * 1.67, 0.025)
                            if self._effective_depth_tolerance_m < widened:
                                self._effective_depth_tolerance_m = widened
                                logger.warning(
                                    "Depth auto-adapt: widened Z-tolerance to %.1fmm (rejection rate %.0f%%)",
                                    widened * 1000, z_total / total * 100,
                                )

                # Voting fallback: use best single-camera result
                self._tri_telemetry.record_attempt("voting_fallback")
                result = self._voting_fallback(entries)
                self._emit(result)

            self._detection_buffer.clear()

    def _voting_fallback(self, entries: list[dict]) -> dict:
        """When triangulation fails, use confidence-weighted voting.

        - Weights each camera's score by its detection confidence.
        - For ≥3 cameras, uses median of total_score instead of mean.
        - Falls back to highest-confidence single result for non-numeric scores.
        """
        # Extract confidences weighted by quality and viewing angle
        confidences = []
        for e in entries:
            det = e.get("detection")
            conf = getattr(det, "confidence", 0.0) if det else 0.0
            quality = getattr(det, "quality", 0.0) if det else 0.0
            vaq = self._viewing_angle_qualities.get(e["camera_id"], 1.0)
            confidences.append(conf * max(quality, 0.1) * vaq)

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

    def get_triangulation_telemetry(self) -> dict:
        """Return triangulation telemetry summary."""
        return self._tri_telemetry.get_summary()

    def get_fusion_config(self) -> dict:
        """Return current fusion parameters."""
        return {
            "sync_wait_s": self._sync_wait_s,
            "max_time_diff_s": self._max_time_diff_s,
            "depth_tolerance_m": self._depth_tolerance_m,
            "effective_depth_tolerance_m": self._effective_depth_tolerance_m,
            "depth_auto_adapt": self._depth_auto_adapt,
            "buffer_max_depth": self._buffer_max_depth,
        }

    def get_governor_stats(self) -> dict[str, dict]:
        """Return per-camera FPS governor statistics."""
        return {cam_id: gov.get_stats() for cam_id, gov in self._governors.items()}

    def _set_camera_error(self, cam_id: str, message: str, level: str = "error") -> None:
        """Set an error for a camera and notify listeners."""
        self._camera_errors[cam_id] = {
            "message": message,
            "timestamp": time.time(),
            "level": level,  # "warning" or "error"
        }
        self._notify_camera_errors()

    def _clear_camera_error(self, cam_id: str) -> None:
        """Clear error for a camera and notify listeners."""
        if cam_id in self._camera_errors:
            del self._camera_errors[cam_id]
            self._notify_camera_errors()

    def _notify_camera_errors(self) -> None:
        """Notify callback when camera errors change."""
        if self.on_camera_errors_changed:
            try:
                self.on_camera_errors_changed(self.get_camera_errors())
            except Exception as e:
                logger.debug("on_camera_errors_changed callback failed: %s", e)

    def get_camera_errors(self) -> dict[str, dict]:
        """Return dict of camera_id -> {message, timestamp, level} for cameras with errors."""
        return dict(self._camera_errors)
