"""FastAPI routes: REST endpoints + WebSocket + MJPEG stream."""

import asyncio
import base64
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.web.stream import encode_frame_jpeg, make_mjpeg_frame

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def setup_routes(app_state: dict) -> APIRouter:
    """Create router with access to shared app state.

    Args:
        app_state: Dict with keys "game_engine", "pipeline", "event_manager", "latest_frame"

    Returns:
        Configured APIRouter
    """

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Serve main page."""
        return templates.TemplateResponse(request, "index.html")

    @router.get("/api/state")
    async def get_state() -> dict:
        """Get current game state."""
        engine = app_state.get("game_engine")
        if engine:
            return engine.get_state()
        return {"phase": "idle", "error": "No game engine"}

    @router.post("/api/game/new")
    async def new_game(request: Request) -> dict:
        """Start a new game."""
        body = await request.json()
        engine = app_state.get("game_engine")
        if not engine:
            return {"error": "No game engine"}
        mode = body.get("mode", "x01")
        players = body.get("players", ["Player 1"])
        starting_score = body.get("starting_score", 501)
        engine.new_game(mode=mode, players=players, starting_score=starting_score)
        state = engine.get_state()
        em = app_state.get("event_manager")
        if em:
            em.broadcast_sync("game_state", state)
        pipeline = app_state.get("pipeline")
        if pipeline and hasattr(pipeline, "detector"):
            pipeline.detector.reset()
        return state

    @router.post("/api/game/undo")
    async def undo_throw() -> dict:
        """Undo the last throw."""
        engine = app_state.get("game_engine")
        if not engine:
            return {"error": "No game engine"}
        engine.undo_last_throw()
        state = engine.get_state()
        em = app_state.get("event_manager")
        if em:
            em.broadcast_sync("game_state", state)
        return state

    @router.post("/api/game/next-player")
    async def next_player() -> dict:
        """Advance to the next player."""
        engine = app_state.get("game_engine")
        if not engine:
            return {"error": "No game engine"}
        engine.next_player()
        state = engine.get_state()
        em = app_state.get("event_manager")
        if em:
            em.broadcast_sync("game_state", state)
        return state

    @router.post("/api/game/remove-darts")
    async def remove_darts() -> dict:
        """Signal that darts have been removed from the board."""
        pipeline = app_state.get("pipeline")
        if pipeline and hasattr(pipeline, "detector"):
            pipeline.detector.reset()
        engine = app_state.get("game_engine")
        if engine:
            engine.next_player()
            state = engine.get_state()
            em = app_state.get("event_manager")
            if em:
                em.broadcast_sync("game_state", state)
            return state
        return {"ok": True}

    @router.post("/api/game/end")
    async def end_game() -> dict:
        """End the current game and return to idle state."""
        engine = app_state.get("game_engine")
        if not engine:
            return {"error": "No game engine"}
        engine.end_game()
        state = engine.get_state()
        em = app_state.get("event_manager")
        if em:
            em.broadcast_sync("game_state", state)
        pipeline = app_state.get("pipeline")
        if pipeline and hasattr(pipeline, "detector"):
            pipeline.detector.reset()
        return state

    @router.post("/api/calibration/manual")
    async def manual_calibration(request: Request) -> dict:
        """Perform manual 4-point calibration."""
        body = await request.json()
        points = body.get("points", [])
        pipeline = app_state.get("pipeline")
        if pipeline and hasattr(pipeline, "calibration"):
            result = pipeline.calibration.manual_calibration(points)
            if result.get("ok"):
                homography = pipeline.calibration.get_homography()
                if homography is not None and hasattr(pipeline, "roi"):
                    pipeline.roi.set_homography_matrix(homography)
            return result
        return {"ok": False, "error": "No pipeline/calibration manager"}

    @router.get("/api/calibration/frame")
    async def get_calibration_frame() -> JSONResponse:
        """Get a single frame for calibration UI."""
        frame = app_state.get("latest_frame")
        if frame is not None:
            jpeg = encode_frame_jpeg(frame, quality=90)
            b64 = base64.b64encode(jpeg).decode("ascii")
            return JSONResponse({"ok": True, "image": "data:image/jpeg;base64," + b64})
        return JSONResponse({"ok": False, "error": "No frame available"})

    @router.post("/api/calibration/aruco")
    async def aruco_calibration() -> dict:
        """Perform ArUco marker-based calibration on current frame."""
        frame = app_state.get("latest_frame")
        if frame is None:
            return {"ok": False, "error": "No frame available"}
        pipeline = app_state.get("pipeline")
        if pipeline and hasattr(pipeline, "calibration"):
            result = pipeline.calibration.aruco_calibration(frame)
            if result.get("ok"):
                homography = pipeline.calibration.get_homography()
                if homography is not None and hasattr(pipeline, "roi"):
                    pipeline.roi.set_homography_matrix(homography)
            return result
        return {"ok": False, "error": "No pipeline/calibration manager"}

    @router.post("/api/calibration/charuco")
    async def charuco_calibration() -> dict:
        """Perform ChArUco calibration (collects frames automatically)."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "calibration"):
            return {"ok": False, "error": "No pipeline/calibration manager"}
        if not pipeline.camera:
            return {"ok": False, "error": "Camera not available"}
        import time as _time
        frames = []
        for _ in range(30):
            ret, frame = pipeline.camera.read()
            if ret and frame is not None:
                frames.append(frame.copy())
            _time.sleep(0.1)
        if len(frames) < 3:
            return {"ok": False, "error": f"Only captured {len(frames)} frames, need at least 3"}
        result = pipeline.calibration.charuco_calibration(frames)
        if result.get("ok"):
            homography = pipeline.calibration.get_homography()
            if homography is not None and hasattr(pipeline, "roi"):
                pipeline.roi.set_homography_matrix(homography)
        return result

    @router.get("/api/calibration/roi-preview")
    async def roi_preview() -> JSONResponse:
        """Return the current ROI-warped frame as base64 JPEG."""
        pipeline = app_state.get("pipeline")
        if pipeline:
            roi = pipeline.get_roi_preview()
            if roi is not None:
                jpeg = encode_frame_jpeg(roi, quality=90)
                b64 = base64.b64encode(jpeg).decode("ascii")
                return JSONResponse({"ok": True, "image": "data:image/jpeg;base64," + b64})
        return JSONResponse({"ok": False, "error": "No ROI available"})

    @router.post("/api/calibration/verify-rings")
    async def verify_rings() -> dict:
        """Run Hough circle + Canny edge detection to verify ring alignment."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "No pipeline"}
        roi = pipeline.get_roi_preview()
        if roi is None:
            return {"ok": False, "error": "No ROI frame available"}
        result = pipeline.calibration.verify_rings(roi)
        return result

    @router.get("/api/calibration/overlay")
    async def field_overlay() -> JSONResponse:
        """Return ROI frame with field boundaries drawn as base64 JPEG."""
        pipeline = app_state.get("pipeline")
        if pipeline:
            overlay = pipeline.get_field_overlay()
            if overlay is not None:
                jpeg = encode_frame_jpeg(overlay, quality=90)
                b64 = base64.b64encode(jpeg).decode("ascii")
                return JSONResponse({"ok": True, "image": "data:image/jpeg;base64," + b64})
        return JSONResponse({"ok": False, "error": "No overlay available"})

    @router.get("/api/stats")
    async def get_stats() -> dict:
        """Get system stats (FPS, connections, etc)."""
        em = app_state.get("event_manager")
        pipeline = app_state.get("pipeline")
        fps = 0.0
        if pipeline and hasattr(pipeline, "fps_counter"):
            fps = pipeline.fps_counter.fps()
        return {
            "fps": round(fps, 1),
            "connections": em.connection_count if em else 0,
            "pipeline_running": app_state.get("pipeline_running", False),
        }

    @router.get("/video/feed")
    async def video_feed() -> StreamingResponse:
        """MJPEG video stream endpoint."""
        async def generate():
            while True:
                frame = app_state.get("latest_frame")
                if frame is not None:
                    jpeg = encode_frame_jpeg(frame)
                    yield make_mjpeg_frame(jpeg)
                await asyncio.sleep(0.033)  # ~30fps max

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time game events."""
        em = app_state.get("event_manager")
        if not em:
            await websocket.close(code=1011, reason="No event manager")
            return
        await em.connect(websocket)
        # Send initial state
        engine = app_state.get("game_engine")
        if engine:
            await websocket.send_json({
                "type": "game_state",
                "data": engine.get_state(),
            })
        try:
            while True:
                data = await websocket.receive_json()
                cmd = data.get("command")
                if cmd == "ping":
                    await websocket.send_json({"type": "pong", "data": {}})
                elif cmd == "get_state":
                    if engine:
                        await websocket.send_json({
                            "type": "game_state",
                            "data": engine.get_state(),
                        })
        except WebSocketDisconnect:
            await em.disconnect(websocket)
        except Exception as e:
            logger.error("WebSocket error: %s", e)
            await em.disconnect(websocket)

    return router
