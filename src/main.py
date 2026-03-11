"""Dart-Vision: FastAPI application entry point."""

import logging
import threading
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
}


def _run_pipeline(state: dict) -> None:
    """Run CV pipeline in a background thread.

    Captures frames, runs detection, and bridges to game engine.
    Graceful degradation: if no camera available, logs warning and exits.
    """
    shutdown_event = state["shutdown_event"]
    pipeline = None
    try:
        from src.cv.pipeline import DartPipeline

        pipeline = DartPipeline(camera_src=0, debug=False)

        def on_dart_detected(score_result: dict) -> None:
            """Callback when a dart is detected by the pipeline."""
            engine = state.get("game_engine")
            em = state.get("event_manager")
            if engine:
                game_state = engine.register_throw(score_result)
                if em:
                    em.broadcast_sync("score", score_result)
                    em.broadcast_sync("game_state", game_state)
                logger.info("Dart scored: %s", score_result)

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
    app_state["event_manager"] = EventManager()
    app_state["shutdown_event"] = threading.Event()

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
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup routes with shared state
configured_router = setup_routes(app_state)
app.include_router(configured_router)
