"""FastAPI routes: REST endpoints + WebSocket + MJPEG stream."""

import asyncio
import base64
import logging

import cv2
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.web.stream import encode_frame_jpeg, make_mjpeg_frame

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def setup_routes(app_state: dict) -> APIRouter:
    """Create router with access to shared app state."""

    # --- Page ---

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Serve main page."""
        return templates.TemplateResponse(request, "index.html")

    # --- Game State ---

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
        # Clear pending hits on new game
        lock = app_state.get("pending_hits_lock")
        if lock:
            with lock:
                app_state["pending_hits"].clear()
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
        """Signal that darts have been removed from the board.

        Only resets the CV detector — does NOT advance to next player.
        That is now a separate action via /api/game/next-player.
        """
        pipeline = app_state.get("pipeline")
        if pipeline and hasattr(pipeline, "detector"):
            pipeline.detector.reset()
        # Clear pending hits
        lock = app_state.get("pending_hits_lock")
        if lock:
            with lock:
                app_state["pending_hits"].clear()
        em = app_state.get("event_manager")
        if em:
            em.broadcast_sync("darts_removed", {})
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
        # Clear pending hits
        lock = app_state.get("pending_hits_lock")
        if lock:
            with lock:
                app_state["pending_hits"].clear()
        return state

    # --- Hit Candidate Review ---

    @router.get("/api/hits/pending")
    async def get_pending_hits() -> dict:
        """Get all pending hit candidates."""
        lock = app_state.get("pending_hits_lock")
        if lock:
            with lock:
                return {"ok": True, "hits": list(app_state["pending_hits"].values())}
        return {"ok": True, "hits": []}

    @router.post("/api/hits/{candidate_id}/confirm")
    async def confirm_hit(candidate_id: str) -> dict:
        """Confirm a hit candidate — registers the throw in the game engine."""
        lock = app_state.get("pending_hits_lock")
        candidate = None
        if lock:
            with lock:
                candidate = app_state["pending_hits"].pop(candidate_id, None)

        if candidate is None:
            return {"ok": False, "error": f"Candidate {candidate_id} not found"}

        engine = app_state.get("game_engine")
        em = app_state.get("event_manager")
        if not engine:
            return {"ok": False, "error": "No game engine"}

        # Register the confirmed throw
        score_result = {
            "score": candidate["score"],
            "sector": candidate["sector"],
            "multiplier": candidate["multiplier"],
            "ring": candidate["ring"],
        }
        game_state = engine.register_throw(score_result)

        # Broadcast confirmed hit + updated game state
        if em:
            em.broadcast_sync("hit_confirmed", candidate)
            em.broadcast_sync("game_state", game_state)

        logger.info("Hit confirmed: %s (%s %d)", candidate_id,
                     candidate["ring"], candidate["score"])
        return {"ok": True, "game_state": game_state}

    @router.post("/api/hits/{candidate_id}/reject")
    async def reject_hit(candidate_id: str) -> dict:
        """Reject a hit candidate — removes it without affecting game state."""
        lock = app_state.get("pending_hits_lock")
        candidate = None
        if lock:
            with lock:
                candidate = app_state["pending_hits"].pop(candidate_id, None)

        if candidate is None:
            return {"ok": False, "error": f"Candidate {candidate_id} not found"}

        em = app_state.get("event_manager")
        if em:
            em.broadcast_sync("hit_rejected", {"candidate_id": candidate_id})

        logger.info("Hit rejected: %s", candidate_id)
        return {"ok": True}

    @router.post("/api/hits/{candidate_id}/correct")
    async def correct_hit(candidate_id: str, request: Request) -> dict:
        """Correct a hit candidate — override score before registering."""
        body = await request.json()
        lock = app_state.get("pending_hits_lock")
        candidate = None
        if lock:
            with lock:
                candidate = app_state["pending_hits"].pop(candidate_id, None)

        if candidate is None:
            return {"ok": False, "error": f"Candidate {candidate_id} not found"}

        # Apply corrections
        corrected_score = body.get("score", candidate["score"])
        corrected_sector = body.get("sector", candidate["sector"])
        corrected_multiplier = body.get("multiplier", candidate["multiplier"])
        corrected_ring = body.get("ring", candidate["ring"])

        engine = app_state.get("game_engine")
        em = app_state.get("event_manager")
        if not engine:
            return {"ok": False, "error": "No game engine"}

        score_result = {
            "score": corrected_score,
            "sector": corrected_sector,
            "multiplier": corrected_multiplier,
            "ring": corrected_ring,
        }
        game_state = engine.register_throw(score_result)

        corrected_candidate = {**candidate, **score_result, "corrected": True}
        if em:
            em.broadcast_sync("hit_confirmed", corrected_candidate)
            em.broadcast_sync("game_state", game_state)

        logger.info("Hit corrected: %s -> %s %d", candidate_id,
                     corrected_ring, corrected_score)
        return {"ok": True, "game_state": game_state}

    # --- Manual Score Entry ---

    @router.post("/api/game/manual-score")
    async def manual_score(request: Request) -> dict:
        """Manually enter a score (bypass CV pipeline)."""
        body = await request.json()
        engine = app_state.get("game_engine")
        em = app_state.get("event_manager")
        if not engine:
            return {"error": "No game engine"}

        score_result = {
            "score": body.get("score", 0),
            "sector": body.get("sector", 0),
            "multiplier": body.get("multiplier", 1),
            "ring": body.get("ring", "single"),
        }
        game_state = engine.register_throw(score_result)
        if em:
            em.broadcast_sync("score", score_result)
            em.broadcast_sync("game_state", game_state)
        return game_state

    # --- Overlay Toggles ---

    @router.post("/api/overlays")
    async def set_overlays(request: Request) -> dict:
        """Toggle vision overlays on the video stream."""
        body = await request.json()
        pipeline = app_state.get("pipeline")
        if pipeline:
            if "motion" in body:
                pipeline.show_overlay_motion = bool(body["motion"])
            if "markers" in body:
                pipeline.show_overlay_markers = bool(body["markers"])
        return {
            "ok": True,
            "motion": pipeline.show_overlay_motion if pipeline else False,
            "markers": pipeline.show_overlay_markers if pipeline else False,
        }

    @router.get("/api/overlays")
    async def get_overlays() -> dict:
        """Get current overlay toggle states."""
        pipeline = app_state.get("pipeline")
        return {
            "motion": pipeline.show_overlay_motion if pipeline else False,
            "markers": pipeline.show_overlay_markers if pipeline else False,
        }

    # --- Calibration ---

    async def _run_manual_board_alignment(points: list[list[float]]) -> dict:
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "board_calibration"):
            return {"ok": False, "error": "No pipeline/board calibration manager"}
        result = pipeline.board_calibration.manual_calibration(points)
        if result.get("ok"):
            pipeline.refresh_remapper()
        return result

    @router.post("/api/calibration/manual")
    async def manual_calibration(request: Request) -> dict:
        """Legacy endpoint: manual board alignment."""
        body = await request.json()
        points = body.get("points", [])
        return await _run_manual_board_alignment(points)

    @router.post("/api/calibration/board/manual")
    async def board_manual_calibration(request: Request) -> dict:
        """Board alignment via manual 4-point selection."""
        body = await request.json()
        points = body.get("points", [])
        return await _run_manual_board_alignment(points)

    @router.get("/api/calibration/frame")
    async def get_calibration_frame() -> JSONResponse:
        """Get a single frame for calibration UI."""
        frame = app_state.get("latest_frame")
        if frame is not None:
            jpeg = encode_frame_jpeg(frame, quality=90)
            b64 = base64.b64encode(jpeg).decode("ascii")
            return JSONResponse({"ok": True, "image": "data:image/jpeg;base64," + b64})
        return JSONResponse({"ok": False, "error": "No frame available"})

    async def _run_aruco_board_alignment(frame) -> dict:
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "board_calibration"):
            return {"ok": False, "error": "No pipeline/board calibration manager"}
        result = pipeline.board_calibration.aruco_calibration(frame)
        if result.get("ok"):
            pipeline.refresh_remapper()
        return result

    @router.post("/api/calibration/aruco")
    async def aruco_calibration() -> dict:
        """Legacy endpoint: ArUco board alignment on latest frame."""
        pipeline = app_state.get("pipeline")
        frame = pipeline.get_latest_raw_frame() if pipeline else None
        if frame is None:
            frame = app_state.get("latest_frame")
        if frame is None:
            return {"ok": False, "error": "No frame available"}
        return await _run_aruco_board_alignment(frame)

    @router.post("/api/calibration/board/aruco")
    async def board_aruco_calibration() -> dict:
        """Board alignment via ArUco markers on latest raw frame."""
        pipeline = app_state.get("pipeline")
        frame = pipeline.get_latest_raw_frame() if pipeline else None
        if frame is None:
            frame = app_state.get("latest_frame")
        if frame is None:
            return {"ok": False, "error": "No frame available"}
        return await _run_aruco_board_alignment(frame)

    async def _run_lens_charuco_calibration() -> dict:
        """Capture latest raw frames and calibrate camera intrinsics."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "camera_calibration"):
            return {"ok": False, "error": "No pipeline/camera calibration manager"}
        if not pipeline.camera:
            return {"ok": False, "error": "Camera not available"}

        import time as _time

        frames = []
        for _ in range(30):
            raw = pipeline.get_latest_raw_frame()
            if raw is not None:
                frames.append(raw.copy())
            _time.sleep(0.1)

        if len(frames) < 3:
            return {"ok": False, "error": f"Only captured {len(frames)} frames, need at least 3"}
        result = pipeline.camera_calibration.charuco_calibration(frames)
        if result.get("ok"):
            pipeline.refresh_remapper()
        return result

    @router.post("/api/calibration/charuco")
    async def charuco_calibration() -> dict:
        """Legacy endpoint: now performs lens setup via ChArUco."""
        return await _run_lens_charuco_calibration()

    @router.post("/api/calibration/lens/charuco")
    async def lens_charuco_calibration() -> dict:
        """Lens setup: estimate camera intrinsics with ChArUco."""
        return await _run_lens_charuco_calibration()

    @router.get("/api/calibration/lens/info")
    async def lens_info() -> dict:
        """Get lens calibration metadata."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "camera_calibration"):
            return {"ok": False, "error": "No camera calibration manager"}
        cfg = pipeline.camera_calibration.get_config()
        return {
            "ok": True,
            "valid": bool(cfg.get("lens_valid", False)),
            "method": cfg.get("lens_method"),
            "image_size": cfg.get("lens_image_size"),
            "reprojection_error": cfg.get("lens_reprojection_error"),
        }

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
        """Verify calibrated ring radii against expected dartboard dimensions."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "No pipeline"}
        roi = pipeline.get_roi_preview()
        if roi is None:
            return {"ok": False, "error": "No ROI frame available"}
        result = pipeline.board_calibration.verify_rings(roi)
        return result

    @router.post("/api/calibration/optical-center")
    async def detect_optical_center() -> dict:
        """Detect the true bullseye position via color thresholding."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "No pipeline"}
        oc = pipeline.detect_optical_center()
        if oc is None:
            return {"ok": False, "error": "Could not detect optical center"}
        return {"ok": True, "optical_center": [oc[0], oc[1]]}

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

    @router.get("/api/calibration/info")
    async def calibration_info() -> dict:
        """Get combined calibration metadata (board + lens)."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "board_calibration"):
            return {"ok": False, "error": "No calibration manager"}
        config = pipeline.board_calibration.get_config()
        lens_cfg = pipeline.camera_calibration.get_config() if hasattr(pipeline, "camera_calibration") else {}
        return {
            "ok": True,
            "board_valid": config.get("valid", False),
            "board_method": config.get("method"),
            "mm_per_px": config.get("mm_per_px", 1.0),
            "radii_px": config.get("radii_px", []),
            "center_px": config.get("center_px", [200, 200]),
            "optical_center_roi_px": config.get("optical_center_roi_px"),
            "lens_valid": bool(lens_cfg.get("lens_valid", False)),
            "lens_method": lens_cfg.get("lens_method"),
            "schema_version": config.get("schema_version", 1),
        }

    @router.post("/api/calibration/stereo")
    async def stereo_calibration(request: Request) -> dict:
        """Run stereo calibration between two cameras."""
        body = await request.json()
        cam_a = body.get("camera_a", "default")
        cam_b = body.get("camera_b")
        if not cam_b:
            return {"ok": False, "error": "camera_b is required"}
        # Stub — full implementation in Step 5
        return {"ok": False, "error": "Not yet implemented — complete in Step 5"}

    @router.get("/api/board/geometry")
    async def board_geometry() -> dict:
        """Expose canonical board geometry used by scoring/rendering."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "get_geometry_info"):
            return {"ok": False, "error": "No pipeline geometry available"}
        return {"ok": True, **pipeline.get_geometry_info()}

    # --- Stats ---

    @router.get("/api/stats")
    async def get_stats() -> dict:
        """Get system stats (FPS, connections, etc)."""
        em = app_state.get("event_manager")
        pipeline = app_state.get("pipeline")
        fps = 0.0
        if pipeline and hasattr(pipeline, "fps_counter"):
            fps = pipeline.fps_counter.fps()
        lock = app_state.get("pending_hits_lock")
        pending_count = 0
        if lock:
            with lock:
                pending_count = len(app_state.get("pending_hits", {}))
        return {
            "fps": round(fps, 1),
            "connections": em.connection_count if em else 0,
            "pipeline_running": app_state.get("pipeline_running", False),
            "pending_hits": pending_count,
        }

    # --- Video Stream ---

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

    @router.get("/video/motion")
    async def motion_feed() -> StreamingResponse:
        """MJPEG stream of the motion mask."""
        async def generate():
            while True:
                pipeline = app_state.get("pipeline")
                mask = pipeline._last_motion_mask if pipeline else None
                if mask is not None:
                    bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) if len(mask.shape) == 2 else mask
                    jpeg = encode_frame_jpeg(bgr)
                    yield make_mjpeg_frame(jpeg)
                await asyncio.sleep(0.066)  # ~15fps

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    # --- WebSocket ---

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
        # Send any pending hits
        lock = app_state.get("pending_hits_lock")
        if lock:
            with lock:
                for candidate in app_state.get("pending_hits", {}).values():
                    await websocket.send_json({
                        "type": "hit_candidate",
                        "data": candidate,
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
