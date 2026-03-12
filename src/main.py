"""Dart-Vision: FastAPI application entry point."""

import asyncio
import logging
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


def _run_pipeline(state: dict) -> None:
    """Run CV pipeline in a background thread.

    Captures frames, runs detection, and creates hit candidates.
    Graceful degradation: if no camera available, logs warning and exits.
    """
    shutdown_event = state["shutdown_event"]
    pipeline = None
    try:
        from src.cv.pipeline import DartPipeline

        pipeline = DartPipeline(camera_src=0, debug=False)

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

        # Start camera
        try:
            pipeline.start()
        except Exception as cam_err:
            logger.warning("Camera not available: %s — running without CV", cam_err)
            state["pipeline"] = pipeline
            state["pipeline_running"] = False
            return

        state["pipeline"] = pipeline
        state["pipeline_running"] = True
        logger.info("CV Pipeline started")

        while not shutdown_event.is_set():
            try:
                pipeline.process_frame()
                # Store annotated frame for MJPEG stream
                annotated = pipeline.get_annotated_frame()
                if annotated is not None:
                    state["latest_frame"] = annotated
            except Exception as frame_err:
                logger.debug("Frame processing error: %s", frame_err)

            shutdown_event.wait(0.001)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start/stop pipeline and game engine."""
    setup_logging()
    logger.info("Dart-Vision starting up...")

    # Initialize game engine and event manager
    app_state["game_engine"] = GameEngine()
    em = EventManager()
    em.set_loop(asyncio.get_running_loop())
    app_state["event_manager"] = em
    app_state["shutdown_event"] = threading.Event()
    app_state["pending_hits_lock"] = threading.Lock()

    # Start CV pipeline in background thread
    pipeline_thread = threading.Thread(
        target=_run_pipeline,
        args=(app_state,),
        daemon=True,
        name="cv-pipeline",
    )
    pipeline_thread.start()
    logger.info("Application ready")

    yield

    # Shutdown
    logger.info("Dart-Vision shutting down...")
    app_state["shutdown_event"].set()
    pipeline_thread.join(timeout=5.0)
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
