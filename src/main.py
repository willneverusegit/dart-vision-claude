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
from src.utils.state import (
    clear_multi_pipeline_state,
    clear_pipeline_thread_handles,
    clear_single_pipeline_state,
    initialize_runtime_state,
    set_multi_latest_frame,
    set_multi_pipeline_state,
    set_pipeline_thread_handles,
    set_single_pipeline_state,
)

logger = logging.getLogger(__name__)

PENDING_HIT_TTL_SECONDS = 30.0
MAX_PENDING_HITS = 10

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
    "pending_hits_expired_total": 0,
    "pending_hits_rejected_by_timeout_total": 0,
    "pending_hits_dropped_overflow_total": 0,
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
}


def _pending_hits_store(state: dict) -> dict:
    return state.setdefault("pending_hits", {})


def _pending_hit_timestamp(candidate: dict) -> float | None:
    ts = candidate.get("timestamp")
    if isinstance(ts, (int, float)) and ts > 0:
        return float(ts)
    return None


def _pending_hit_sort_key(candidate: dict) -> tuple[float, str]:
    ts = _pending_hit_timestamp(candidate)
    candidate_id = str(candidate.get("candidate_id", ""))
    return (ts if ts is not None else float("inf"), candidate_id)


def _broadcast_pending_hit_rejected(state: dict, candidate: dict, reason: str) -> None:
    em = state.get("event_manager")
    if em:
        em.broadcast_sync(
            "hit_rejected",
            {"candidate_id": candidate.get("candidate_id"), "reason": reason},
        )


def _expire_pending_hits_locked(state: dict, now: float) -> list[dict]:
    pending_hits = _pending_hits_store(state)
    expired_ids = [
        candidate_id
        for candidate_id, candidate in pending_hits.items()
        if (timestamp := _pending_hit_timestamp(candidate)) is not None
        and (now - timestamp) >= PENDING_HIT_TTL_SECONDS
    ]
    expired = [pending_hits.pop(candidate_id) for candidate_id in expired_ids]
    if expired:
        state["pending_hits_expired_total"] = state.get("pending_hits_expired_total", 0) + len(expired)
        state["pending_hits_rejected_by_timeout_total"] = (
            state.get("pending_hits_rejected_by_timeout_total", 0) + len(expired)
        )
    return expired


def expire_pending_hits(state: dict, now: float | None = None) -> list[dict]:
    """Remove timed-out hit candidates and emit rejection events."""
    now = time.time() if now is None else now
    lock = state.get("pending_hits_lock")
    if lock:
        with lock:
            expired = _expire_pending_hits_locked(state, now)
    else:
        expired = _expire_pending_hits_locked(state, now)

    for candidate in expired:
        _broadcast_pending_hit_rejected(state, candidate, reason="timeout")
        logger.info("Pending hit timed out: %s", candidate.get("candidate_id"))
    return expired


def add_pending_hit(state: dict, candidate: dict, now: float | None = None) -> list[dict]:
    """Add a pending hit, expiring stale entries and trimming overflow."""
    now = time.time() if now is None else now
    lock = state.get("pending_hits_lock")
    overflow: list[dict] = []
    expired: list[dict] = []

    if lock:
        with lock:
            expired = _expire_pending_hits_locked(state, now)
            pending_hits = _pending_hits_store(state)
            pending_hits[candidate["candidate_id"]] = candidate
            while len(pending_hits) > MAX_PENDING_HITS:
                overflow_id, overflow_candidate = min(
                    pending_hits.items(),
                    key=lambda item: _pending_hit_sort_key(item[1]),
                )
                overflow.append(pending_hits.pop(overflow_id))
    else:
        expired = _expire_pending_hits_locked(state, now)
        pending_hits = _pending_hits_store(state)
        pending_hits[candidate["candidate_id"]] = candidate
        while len(pending_hits) > MAX_PENDING_HITS:
            overflow_id, overflow_candidate = min(
                pending_hits.items(),
                key=lambda item: _pending_hit_sort_key(item[1]),
            )
            overflow.append(pending_hits.pop(overflow_id))

    if overflow:
        state["pending_hits_dropped_overflow_total"] = (
            state.get("pending_hits_dropped_overflow_total", 0) + len(overflow)
        )

    for expired_candidate in expired:
        _broadcast_pending_hit_rejected(state, expired_candidate, reason="timeout")
        logger.info("Pending hit timed out: %s", expired_candidate.get("candidate_id"))
    for overflow_candidate in overflow:
        _broadcast_pending_hit_rejected(state, overflow_candidate, reason="overflow")
        logger.warning(
            "Pending hit dropped due to overflow: %s",
            overflow_candidate.get("candidate_id"),
        )
    return overflow


def get_pending_hits_snapshot(state: dict) -> list[dict]:
    """Return active pending hits after server-side expiry cleanup."""
    expire_pending_hits(state)
    lock = state.get("pending_hits_lock")
    if lock:
        with lock:
            return list(_pending_hits_store(state).values())
    return list(_pending_hits_store(state).values())


def pop_pending_hit(state: dict, candidate_id: str) -> dict | None:
    """Pop a pending hit after first removing timed-out entries."""
    expire_pending_hits(state)
    lock = state.get("pending_hits_lock")
    if lock:
        with lock:
            return _pending_hits_store(state).pop(candidate_id, None)
    return _pending_hits_store(state).pop(candidate_id, None)


def clear_pending_hits(state: dict) -> None:
    """Remove all pending hits without emitting rejection events."""
    lock = state.get("pending_hits_lock")
    if lock:
        with lock:
            _pending_hits_store(state).clear()
    else:
        _pending_hits_store(state).clear()


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

            add_pending_hit(state, candidate)

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
            set_single_pipeline_state(state, pipeline, running=False)
            return

        # Register health callback after successful start
        from src.cv.capture import ThreadedCamera
        if isinstance(pipeline.camera, ThreadedCamera):
            pipeline.camera.on_state_change(on_camera_state_change)

        set_single_pipeline_state(state, pipeline, running=True)
        logger.info("CV Pipeline started")
        next_pending_cleanup_at = time.time() + 1.0

        def _should_stop() -> bool:
            return stop_event.is_set() or shutdown_event.is_set()

        while not _should_stop():
            try:
                pipeline.process_frame()
                # Store annotated frame for MJPEG stream
                annotated = pipeline.get_annotated_frame()
                if annotated is not None:
                    state["latest_frame"] = annotated
            except Exception as frame_err:
                logger.debug("Frame processing error: %s", frame_err)

            now = time.time()
            if now >= next_pending_cleanup_at:
                expire_pending_hits(state, now=now)
                next_pending_cleanup_at = now + 1.0

            stop_event.wait(0.001)

    except ImportError as e:
        logger.warning("CV Pipeline not available: %s", e)
    except Exception as e:
        logger.error("CV Pipeline error: %s", e)
    finally:
        clear_single_pipeline_state(state)
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

            add_pending_hit(state, candidate)

            em.broadcast_sync("hit_candidate", candidate)
            logger.info("Multi-cam hit candidate: %s (quality=%d, source=%s, %s %d)",
                        candidate_id, quality, score_result.get("source", "?"),
                        score_result.get("ring", "?"), score_result.get("score", 0))

        multi = MultiCameraPipeline(
            camera_configs=camera_configs,
            on_multi_dart_detected=on_multi_dart_detected,
        )

        set_multi_pipeline_state(
            state,
            multi,
            [c["camera_id"] for c in camera_configs],
        )

        multi.start()
        logger.info("Multi-camera pipeline started with %d cameras", len(camera_configs))
        next_pending_cleanup_at = time.time() + 1.0

        def _should_stop() -> bool:
            return stop_event.is_set() or shutdown_event.is_set()

        # Update per-camera annotated frames for MJPEG streams
        while not _should_stop():
            pipelines = multi.get_pipelines()
            for cam_id, pipeline in pipelines.items():
                annotated = pipeline.get_annotated_frame()
                if annotated is not None:
                    set_multi_latest_frame(state, cam_id, annotated)
            now = time.time()
            if now >= next_pending_cleanup_at:
                expire_pending_hits(state, now=now)
                next_pending_cleanup_at = now + 1.0
            stop_event.wait(0.033)  # ~30fps frame grab rate

    except ImportError as e:
        logger.warning("Multi-camera pipeline not available: %s", e)
    except Exception as e:
        logger.error("Multi-camera pipeline error: %s", e)
    finally:
        if multi is not None:
            try:
                multi.stop()
            except Exception:
                pass
        clear_multi_pipeline_state(state)
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
    clear_pipeline_thread_handles(state, kind)


def start_single_pipeline(state: dict, camera_src: int | str = 0) -> None:
    """Start a single pipeline in a new background thread.

    Stops any existing single pipeline first.
    """
    stop_pipeline_thread(state, "single", timeout=5.0)
    stop_evt = threading.Event()
    thread = threading.Thread(
        target=_run_pipeline,
        args=(state, stop_evt, camera_src),
        daemon=True,
        name="cv-pipeline",
    )
    set_pipeline_thread_handles(state, "single", stop_event=stop_evt, thread=thread)
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
    game_engine = GameEngine()
    em = EventManager()
    em.set_loop(asyncio.get_running_loop())
    initialize_runtime_state(
        app_state,
        game_engine=game_engine,
        event_manager=em,
        shutdown_event=threading.Event(),
        pending_hits_lock=threading.Lock(),
        pipeline_lock=threading.Lock(),
    )

    # Start CV pipeline — single or multi camera depending on config
    from src.utils.config import get_startup_cameras
    startup_cameras = get_startup_cameras()

    if startup_cameras:
        stop_evt = threading.Event()
        pipeline_thread = threading.Thread(
            target=_run_multi_pipeline,
            args=(app_state, startup_cameras, stop_evt),
            daemon=True,
            name="cv-multi-pipeline",
        )
        set_pipeline_thread_handles(
            app_state,
            "multi",
            stop_event=stop_evt,
            thread=pipeline_thread,
        )
        pipeline_thread.start()
        logger.info("Starting multi-camera pipeline (%d cameras)", len(startup_cameras))
    else:
        start_single_pipeline(app_state, camera_src=0)

    logger.info("Application ready")

    yield

    # Shutdown: signal all threads via both app-level and per-thread events
    logger.info("Dart-Vision shutting down...")
    app_state["shutdown_event"].set()
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
