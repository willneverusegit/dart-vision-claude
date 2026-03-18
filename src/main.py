"""Dart-Vision: FastAPI application entry point."""

import asyncio
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.game.engine import GameEngine
from src.web.events import EventManager
from src.web.routes import setup_routes
from src.utils.logger import setup_logging
from src.utils.telemetry import TelemetryHistory, TelemetrySample

logger = logging.getLogger(__name__)

# Shared application state
app_state: dict = {
    "game_engine": None,
    "pipeline": None,
    "event_manager": None,
    "latest_frame": None,
    "pipeline_running": False,
    "shutdown_event": None,
    # Hit candidate system
    "pending_hits": {},          # {candidate_id: candidate_dict}
    "pending_hits_lock": None,   # threading.Lock for thread safety
    # Overlay toggles (for annotated stream)
    "overlay_roi": False,
    "overlay_motion": False,
    "overlay_fields": False,
    # Multi-camera pipeline
    "multi_pipeline": None,         # MultiCameraPipeline | None
    "multi_pipeline_running": False,
    "active_camera_ids": [],        # List of active camera IDs
    "multi_latest_frames": {},      # {camera_id: frame} for per-camera MJPEG
    # A1: Lock protecting pipeline lifecycle mutations accessed by both the
    # CV background thread and HTTP route handlers.
    "pipeline_lock": None,
    # Per-pipeline thread lifecycle: each pipeline thread gets its own stop
    # event so it can be individually terminated without affecting the app.
    "pipeline_stop_event": None,       # threading.Event for single pipeline thread
    "multi_pipeline_stop_event": None, # threading.Event for multi pipeline thread
    "pipeline_thread": None,           # threading.Thread handle
    "multi_pipeline_thread": None,     # threading.Thread handle
    # Video recorder
    "recorder": None,                  # VideoRecorder instance
}


def _compute_quality_score(detection, score_result: dict) -> int:
    """Compute a quality score (0-100) for a hit candidate.

    Based on:
    - Temporal confirmation frames (how many frames confirmed the detection)
    - Contour area vs expected area
    - Distance to nearest field boundary (closer = less certain)
    """
    quality = 50  # Base score

    # Factor 1: Confirmation frames (more frames = higher confidence)
    if hasattr(detection, "frame_count"):
        frames = detection.frame_count
        quality += min(frames * 8, 25)  # Up to +25 for 3+ frames
    else:
        quality += 15  # Default if not tracked

    # Factor 2: Contour area reasonableness
    if hasattr(detection, "area") and detection.area > 0:
        # Expected dart tip area is roughly 50-500px^2 in ROI
        area = detection.area
        if 30 <= area <= 800:
            quality += 15  # Good range
        elif 10 <= area <= 1500:
            quality += 5   # Acceptable range
        # else: no bonus (suspicious area)
    else:
        quality += 10  # Default

    # Factor 3: Distance to field boundary
    # If the hit is very close to a ring or sector boundary, lower confidence
    ring = score_result.get("ring", "single")
    if ring in ("inner_bull", "outer_bull"):
        quality += 10  # Bull hits are distinctive
    elif ring in ("double", "triple"):
        quality += 5   # Narrow rings — could go either way
    else:
        quality += 8   # Single is large, decent confidence

    return min(quality, 100)


def _run_pipeline(state: dict, stop_event: threading.Event | None = None,
                   camera_src: int | str = 0) -> None:
    """Run CV pipeline in a background thread.

    Captures frames, runs detection, and creates hit candidates.
    Graceful degradation: if no camera available, logs warning and exits.

    Args:
        state: Shared application state dict.
        stop_event: Per-thread stop signal. Falls back to state["shutdown_event"].
        camera_src: Camera index or path to use.
    """
    shutdown_event = state["shutdown_event"]
    if stop_event is None:
        stop_event = shutdown_event
    pipeline = None
    try:
        from src.cv.pipeline import DartPipeline

        pipeline = DartPipeline(camera_src=camera_src, debug=False)

        def on_dart_detected(score_result: dict, detection=None) -> None:
            """Callback when a dart is detected by the pipeline.

            Creates a hit candidate instead of immediately registering.
            """
            em = state.get("event_manager")
            engine = state.get("game_engine")
            lock = state.get("pending_hits_lock")

            if not engine or not em:
                return

            # Compute quality score
            quality = 50
            if detection is not None:
                quality = _compute_quality_score(detection, score_result)

            # Create candidate
            candidate_id = str(uuid.uuid4())[:8]
            candidate = {
                "candidate_id": candidate_id,
                "score": score_result["score"],
                "sector": score_result["sector"],
                "multiplier": score_result["multiplier"],
                "ring": score_result["ring"],
                "roi_x": score_result.get("roi_x", 0),
                "roi_y": score_result.get("roi_y", 0),
                "quality": quality,
                "timestamp": time.time(),
            }

            if lock:
                with lock:
                    state["pending_hits"][candidate_id] = candidate

            # Send candidate to all clients via WebSocket
            em.broadcast_sync("hit_candidate", candidate)
            logger.info("Hit candidate: %s (quality=%d, %s %d)",
                        candidate_id, quality, score_result["ring"],
                        score_result["score"])

        pipeline.on_dart_detected = on_dart_detected

        # Camera health callback — broadcast state changes via WebSocket
        def on_camera_state_change(src, old_state, new_state) -> None:
            em = state.get("event_manager")
            if em:
                em.broadcast_sync("camera_state", {
                    "camera_id": "default",
                    "src": src,
                    "old_state": old_state.value,
                    "state": new_state.value,
                })

        # Start camera
        try:
            pipeline.start()
        except Exception as cam_err:
            logger.warning("Camera not available: %s — running without CV", cam_err)
            state["pipeline"] = pipeline
            state["pipeline_running"] = False
            return

        # Register health callback after successful start
        from src.cv.capture import ThreadedCamera
        if isinstance(pipeline.camera, ThreadedCamera):
            pipeline.camera.on_state_change(on_camera_state_change)

        state["pipeline"] = pipeline
        state["pipeline_running"] = True
        logger.info("CV Pipeline started")

        def _should_stop() -> bool:
            return stop_event.is_set() or shutdown_event.is_set()

        while not _should_stop():
            try:
                pipeline.process_frame()
                # Store annotated frame for MJPEG stream
                annotated = pipeline.get_annotated_frame()
                if annotated is not None:
                    state["latest_frame"] = annotated
                # Record raw frame if recording is active
                recorder = state.get("recorder")
                raw = pipeline.get_latest_raw_frame()
                if recorder is not None and raw is not None:
                    recorder.write(raw)
            except Exception as frame_err:
                logger.debug("Frame processing error: %s", frame_err)

            stop_event.wait(0.001)

    except ImportError as e:
        logger.warning("CV Pipeline not available: %s", e)
    except Exception as e:
        logger.error("CV Pipeline error: %s", e)
    finally:
        state["pipeline_running"] = False
        if pipeline is not None:
            try:
                pipeline.stop()
            except Exception:
                pass
        logger.info("CV Pipeline stopped")


def _run_multi_pipeline(state: dict, camera_configs: list[dict],
                        stop_event: threading.Event | None = None) -> None:
    """Run multi-camera CV pipeline in a background thread.

    Instantiates MultiCameraPipeline instead of DartPipeline.
    The callback on_multi_dart_detected creates hit candidates analogous
    to the single-pipeline flow.

    Args:
        state: Shared application state dict.
        camera_configs: List of camera configuration dicts.
        stop_event: Per-thread stop signal. Falls back to state["shutdown_event"].
    """
    shutdown_event = state["shutdown_event"]
    if stop_event is None:
        stop_event = shutdown_event
    multi = None
    try:
        from src.cv.multi_camera import MultiCameraPipeline

        def on_multi_dart_detected(score_result: dict) -> None:
            """Callback when a dart is detected by the multi-pipeline."""
            em = state.get("event_manager")
            engine = state.get("game_engine")
            lock = state.get("pending_hits_lock")

            if not engine or not em:
                return

            # Build a fake detection-like object for quality scoring
            class _FakeDetection:
                frame_count = 3
                area = 200.0
                confidence = 0.7
            detection = _FakeDetection()

            quality = _compute_quality_score(detection, score_result)

            candidate_id = str(uuid.uuid4())[:8]
            candidate = {
                "candidate_id": candidate_id,
                "score": score_result.get("score", 0),
                "sector": score_result.get("sector", 0),
                "multiplier": score_result.get("multiplier", 1),
                "ring": score_result.get("ring", "single"),
                "roi_x": score_result.get("roi_x", 0),
                "roi_y": score_result.get("roi_y", 0),
                "quality": quality,
                "source": score_result.get("source", "multi"),
                "timestamp": time.time(),
            }

            if lock:
                with lock:
                    state["pending_hits"][candidate_id] = candidate

            em.broadcast_sync("hit_candidate", candidate)
            logger.info("Multi-cam hit candidate: %s (quality=%d, source=%s, %s %d)",
                        candidate_id, quality, score_result.get("source", "?"),
                        score_result.get("ring", "?"), score_result.get("score", 0))

        multi = MultiCameraPipeline(
            camera_configs=camera_configs,
            on_multi_dart_detected=on_multi_dart_detected,
        )

        state["multi_pipeline"] = multi
        state["multi_pipeline_running"] = True
        state["active_camera_ids"] = [c["camera_id"] for c in camera_configs]

        multi.start()
        logger.info("Multi-camera pipeline started with %d cameras", len(camera_configs))

        def _should_stop() -> bool:
            return stop_event.is_set() or shutdown_event.is_set()

        # Update per-camera annotated frames for MJPEG streams
        while not _should_stop():
            pipelines = multi.get_pipelines()
            for cam_id, pipeline in pipelines.items():
                annotated = pipeline.get_annotated_frame()
                if annotated is not None:
                    state["multi_latest_frames"][cam_id] = annotated
                    # Also update default latest_frame with first camera
                    if state.get("latest_frame") is None or cam_id == state["active_camera_ids"][0]:
                        state["latest_frame"] = annotated
            stop_event.wait(0.033)  # ~30fps frame grab rate

    except ImportError as e:
        logger.warning("Multi-camera pipeline not available: %s", e)
    except Exception as e:
        logger.error("Multi-camera pipeline error: %s", e)
    finally:
        state["multi_pipeline_running"] = False
        state["active_camera_ids"] = []
        if multi is not None:
            try:
                multi.stop()
            except Exception:
                pass
        state["multi_pipeline"] = None
        logger.info("Multi-camera pipeline stopped")


def stop_pipeline_thread(state: dict, kind: str = "single", timeout: float = 5.0) -> None:
    """Signal a pipeline thread to stop and wait for it to exit.

    Args:
        state: Shared application state dict.
        kind: "single" or "multi".
        timeout: Max seconds to wait for thread to join.
    """
    if kind == "single":
        stop_evt = state.get("pipeline_stop_event")
        thread = state.get("pipeline_thread")
    else:
        stop_evt = state.get("multi_pipeline_stop_event")
        thread = state.get("multi_pipeline_thread")

    if stop_evt is not None:
        stop_evt.set()
    if thread is not None and thread.is_alive():
        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.warning("%s pipeline thread did not exit within %.1fs", kind, timeout)

    # Clear handles
    if kind == "single":
        state["pipeline_stop_event"] = None
        state["pipeline_thread"] = None
    else:
        state["multi_pipeline_stop_event"] = None
        state["multi_pipeline_thread"] = None


def start_single_pipeline(state: dict, camera_src: int | str = 0) -> None:
    """Start a single pipeline in a new background thread.

    Stops any existing single pipeline first.
    """
    stop_pipeline_thread(state, "single", timeout=5.0)
    stop_evt = threading.Event()
    state["pipeline_stop_event"] = stop_evt
    thread = threading.Thread(
        target=_run_pipeline,
        args=(state, stop_evt, camera_src),
        daemon=True,
        name="cv-pipeline",
    )
    state["pipeline_thread"] = thread
    thread.start()
    logger.info("Single pipeline started (camera_src=%s)", camera_src)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start/stop pipeline and game engine."""
    log_file = os.environ.get("DARTVISION_LOG_FILE", None)
    setup_logging(log_file=log_file)
    from src.utils.logger import SESSION_ID
    logger.info("Dart-Vision starting up... (session=%s)", SESSION_ID)

    # Initialize game engine and event manager
    app_state["game_engine"] = GameEngine()
    em = EventManager()
    em.set_loop(asyncio.get_running_loop())
    app_state["event_manager"] = em
    app_state["shutdown_event"] = threading.Event()
    app_state["pending_hits_lock"] = threading.Lock()
    app_state["pipeline_lock"] = threading.Lock()  # A1: pipeline lifecycle guard

    # Video recorder for capturing test clips
    from src.cv.recorder import VideoRecorder
    app_state["recorder"] = VideoRecorder()

    # Telemetry history
    telemetry = TelemetryHistory(max_samples=300, fps_alert_threshold=15.0, queue_alert_threshold=0.8)
    app_state["telemetry"] = telemetry

    # Start telemetry collection background task
    async def _collect_telemetry():
        """Collect telemetry samples every second."""
        prev_fps_alert = False
        prev_queue_alert = False
        while not app_state["shutdown_event"].is_set():
            pipeline = app_state.get("pipeline")
            fps = 0.0
            dropped = 0
            queue_pressure = 0.0
            try:
                if pipeline and hasattr(pipeline, "fps_counter"):
                    fps = float(pipeline.fps_counter.fps())
                if pipeline and hasattr(pipeline, "_dropped_frames"):
                    dropped = int(pipeline._dropped_frames)
                if pipeline and hasattr(pipeline, "camera") and pipeline.camera is not None:
                    if hasattr(pipeline.camera, "queue_pressure"):
                        queue_pressure = float(pipeline.camera.queue_pressure)
            except (TypeError, ValueError):
                pass

            # Memory (lightweight)
            memory_mb = 0.0
            try:
                import ctypes
                from ctypes import wintypes
                class _PMC(ctypes.Structure):
                    _fields_ = [("cb", wintypes.DWORD),
                                ("PageFaultCount", wintypes.DWORD),
                                ("PeakWorkingSetSize", ctypes.c_size_t),
                                ("WorkingSetSize", ctypes.c_size_t)]
                _fn = ctypes.windll.psapi.GetProcessMemoryInfo
                _fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
                _fn.restype = wintypes.BOOL
                pmc = _PMC()
                pmc.cb = ctypes.sizeof(pmc)
                handle = ctypes.windll.kernel32.GetCurrentProcess()
                if _fn(handle, ctypes.byref(pmc), pmc.cb):
                    memory_mb = round(pmc.WorkingSetSize / (1024 * 1024), 1)
            except Exception:
                pass

            # Optional CPU via psutil
            cpu = None
            try:
                import psutil
                cpu = psutil.cpu_percent(interval=None)
            except ImportError:
                pass

            sample = TelemetrySample(
                timestamp=time.time(),
                fps=fps,
                queue_pressure=queue_pressure,
                dropped_frames=dropped,
                memory_mb=memory_mb,
                cpu_percent=cpu,
            )
            telemetry.record(sample)

            # Broadcast alerts on state change
            fps_alert = telemetry.fps_alert_active
            queue_alert = telemetry.queue_alert_active
            if fps_alert != prev_fps_alert or queue_alert != prev_queue_alert:
                em_ref = app_state.get("event_manager")
                if em_ref:
                    em_ref.broadcast_sync("telemetry_alert", telemetry.get_alerts())
                prev_fps_alert = fps_alert
                prev_queue_alert = queue_alert

            await asyncio.sleep(1.0)

    telemetry_task = asyncio.create_task(_collect_telemetry())

    # Start CV pipeline — single or multi camera depending on config
    from src.utils.config import get_startup_cameras
    startup_cameras = get_startup_cameras()

    if startup_cameras:
        stop_evt = threading.Event()
        app_state["multi_pipeline_stop_event"] = stop_evt
        pipeline_thread = threading.Thread(
            target=_run_multi_pipeline,
            args=(app_state, startup_cameras, stop_evt),
            daemon=True,
            name="cv-multi-pipeline",
        )
        app_state["multi_pipeline_thread"] = pipeline_thread
        pipeline_thread.start()
        logger.info("Starting multi-camera pipeline (%d cameras)", len(startup_cameras))
    else:
        start_single_pipeline(app_state, camera_src=0)

    logger.info("Application ready")

    yield

    # Shutdown: signal all threads via both app-level and per-thread events
    logger.info("Dart-Vision shutting down...")
    app_state["shutdown_event"].set()
    telemetry_task.cancel()
    try:
        await telemetry_task
    except asyncio.CancelledError:
        pass
    stop_pipeline_thread(app_state, "single", timeout=5.0)
    stop_pipeline_thread(app_state, "multi", timeout=5.0)
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Dart-Vision",
    description="CPU-optimized dart scoring system",
    version="0.2.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup routes with shared state
configured_router = setup_routes(app_state)
app.include_router(configured_router)
