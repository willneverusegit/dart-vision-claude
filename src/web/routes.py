"""FastAPI routes: REST endpoints + WebSocket + MJPEG stream."""

import asyncio
import base64
import logging
import threading
import time as _time
from contextlib import nullcontext as _nullcontext

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from src.web.stream import encode_frame_jpeg, make_mjpeg_frame

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="templates")


def setup_routes(app_state: dict) -> APIRouter:
    """Create a fresh router with access to shared app state.

    Each call creates a new APIRouter instance, avoiding module-level
    state pollution when setup_routes is called multiple times (e.g. in tests).
    """
    router = APIRouter()

    async def _optional_json_body(request: Request | None) -> dict:
        if request is None:
            return {}
        try:
            return await request.json()
        except Exception:
            return {}

    def _charuco_override_fields(body: dict | None) -> dict:
        body = body if isinstance(body, dict) else {}
        return {
            "preset": body.get("preset") or body.get("charuco_preset"),
            "squares_x": body.get("squares_x"),
            "squares_y": body.get("squares_y"),
            "square_length_mm": body.get("square_length_mm"),
            "marker_length_mm": body.get("marker_length_mm"),
        }

    def _has_charuco_override(body: dict | None) -> bool:
        fields = _charuco_override_fields(body)
        return any(value is not None for value in fields.values())

    VALID_RINGS = {"single", "double", "triple", "inner_bull", "outer_bull", "miss"}
    VALID_SECTORS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 50}

    def _validate_score_input(body: dict) -> tuple[dict | None, str | None]:
        """Validate score/sector/multiplier/ring from request body.
        Returns (validated_dict, error_msg). If error_msg is not None, validation failed."""
        errors = []
        score = body.get("score", 0)
        sector = body.get("sector", 0)
        multiplier = body.get("multiplier", 1)
        ring = body.get("ring", "single")

        if not isinstance(score, int) or score < 0 or score > 180:
            errors.append(f"score must be int 0-180, got {score!r}")
        if not isinstance(sector, int) or sector not in VALID_SECTORS:
            errors.append(f"sector must be int in {sorted(VALID_SECTORS)}, got {sector!r}")
        if not isinstance(multiplier, int) or multiplier not in {1, 2, 3}:
            errors.append(f"multiplier must be 1, 2, or 3, got {multiplier!r}")
        if not isinstance(ring, str) or ring not in VALID_RINGS:
            errors.append(f"ring must be one of {sorted(VALID_RINGS)}, got {ring!r}")

        if errors:
            return None, "; ".join(errors)
        return {"score": score, "sector": sector, "multiplier": multiplier, "ring": ring}, None

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
        # A2: Guard — board must be calibrated before starting a game
        pipeline = app_state.get("pipeline")
        if pipeline and hasattr(pipeline, "board_calibration"):
            if not pipeline.board_calibration.is_valid():
                return {
                    "ok": False,
                    "error": "Board nicht kalibriert. Bitte zuerst die Board-Kalibrierung durchführen.",
                }
        mode = body.get("mode", "x01")
        if mode not in ("x01", "cricket", "free"):
            mode = "x01"
        players = body.get("players", ["Player 1"])
        if not isinstance(players, list) or len(players) == 0 or not all(isinstance(p, str) for p in players):
            players = ["Player 1"]
        starting_score = body.get("starting_score", 501)
        if not isinstance(starting_score, int) or starting_score < 2 or starting_score > 10000:
            starting_score = 501
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

        # Apply corrections — merge candidate defaults with body overrides
        merged = {
            "score": body.get("score", candidate["score"]),
            "sector": body.get("sector", candidate["sector"]),
            "multiplier": body.get("multiplier", candidate["multiplier"]),
            "ring": body.get("ring", candidate["ring"]),
        }
        validated, err = _validate_score_input(merged)
        if err:
            return {"ok": False, "error": f"Invalid score input: {err}"}

        engine = app_state.get("game_engine")
        em = app_state.get("event_manager")
        if not engine:
            return {"ok": False, "error": "No game engine"}

        score_result = validated
        game_state = engine.register_throw(score_result)

        corrected_candidate = {**candidate, **score_result, "corrected": True}
        if em:
            em.broadcast_sync("hit_confirmed", corrected_candidate)
            em.broadcast_sync("game_state", game_state)

        logger.info("Hit corrected: %s -> %s %d", candidate_id,
                     score_result["ring"], score_result["score"])
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

        raw = {
            "score": body.get("score", 0),
            "sector": body.get("sector", 0),
            "multiplier": body.get("multiplier", 1),
            "ring": body.get("ring", "single"),
        }
        score_result, err = _validate_score_input(raw)
        if err:
            return {"error": f"Invalid score input: {err}"}
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

    # --- CV Parameter Tuning ---

    @router.get("/api/cv-params")
    async def get_cv_params() -> dict:
        """Get current CV detection parameters."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "No pipeline active"}
        params = pipeline.frame_diff_detector.get_params()
        params["motion_threshold"] = pipeline.motion_detector.threshold
        return {"ok": True, **params}

    @router.post("/api/cv-params")
    async def set_cv_params(request: Request) -> dict:
        """Update CV detection parameters at runtime (partial update)."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "No pipeline active"}
        body = await request.json()
        # Filter to known params only
        known = {"settle_frames", "diff_threshold", "min_diff_area",
                 "max_diff_area", "min_elongation"}
        params = {k: v for k, v in body.items() if k in known}
        # Type coercion
        for k in ("settle_frames", "diff_threshold", "min_diff_area", "max_diff_area"):
            if k in params:
                params[k] = int(params[k])
        if "min_elongation" in params:
            params["min_elongation"] = float(params["min_elongation"])
        # Motion threshold (separate detector)
        if "motion_threshold" in body:
            mt = int(body["motion_threshold"])
            pipeline.motion_detector.set_threshold(mt)
        try:
            updated = pipeline.frame_diff_detector.set_params(**params)
            updated["motion_threshold"] = pipeline.motion_detector.threshold
            return {"ok": True, **updated}
        except ValueError as e:
            return {"ok": False, "error": str(e)}

    @router.post("/api/diagnostics/toggle")
    async def toggle_diagnostics(request: Request) -> dict:
        """Enable/disable diagnostics image saving at runtime."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "No pipeline active"}
        body = await request.json()
        path = body.get("path")  # None to disable
        enabled = pipeline.frame_diff_detector.toggle_diagnostics(path)
        return {"ok": True, "diagnostics_enabled": enabled}

    # --- Capture Settings ---

    def _get_camera_from_pipeline():
        """Get the active ThreadedCamera instance (single or first multi)."""
        pipeline = app_state.get("pipeline")
        if pipeline and hasattr(pipeline, "camera") and pipeline.camera is not None:
            return pipeline.camera, "single"
        multi = app_state.get("multi_pipeline")
        if multi is not None:
            pipelines = multi.get_pipelines()
            for cam_id, pipe in pipelines.items():
                if hasattr(pipe, "camera") and pipe.camera is not None:
                    return pipe.camera, cam_id
        return None, None

    @router.get("/api/capture/config")
    async def get_capture_config() -> dict:
        """Get current capture resolution and FPS (requested vs actual)."""
        from src.cv.capture import ThreadedCamera
        pipeline = app_state.get("pipeline")
        result = {"ok": True, "cameras": {}}

        # Single pipeline
        if pipeline and hasattr(pipeline, "camera") and pipeline.camera is not None:
            cam = pipeline.camera
            if isinstance(cam, ThreadedCamera):
                result["cameras"]["default"] = cam.get_capture_config()

        # Multi pipeline
        multi = app_state.get("multi_pipeline")
        if multi is not None:
            for cam_id, pipe in multi.get_pipelines().items():
                if hasattr(pipe, "camera") and pipe.camera is not None:
                    cam = pipe.camera
                    if isinstance(cam, ThreadedCamera):
                        result["cameras"][cam_id] = cam.get_capture_config()

        if not result["cameras"]:
            return {"ok": False, "error": "Keine aktive Kamera verfuegbar"}
        return result

    @router.post("/api/capture/config")
    async def set_capture_config(request: Request) -> dict:
        """Apply new capture resolution/FPS to an active camera.

        Body: {"camera_id": "default", "width": 640, "height": 480, "fps": 30}
        camera_id is optional — defaults to "default" (single pipeline).
        """
        from src.cv.capture import ThreadedCamera
        body = await request.json()
        cam_id = body.get("camera_id", "default")
        width = body.get("width")
        height = body.get("height")
        fps = body.get("fps")

        if not any([width, height, fps]):
            return {"ok": False, "error": "Mindestens width, height oder fps angeben"}

        # Find the target camera
        target_cam = None
        if cam_id == "default":
            pipeline = app_state.get("pipeline")
            if pipeline and hasattr(pipeline, "camera") and pipeline.camera is not None:
                target_cam = pipeline.camera
        else:
            multi = app_state.get("multi_pipeline")
            if multi is not None:
                pipelines = multi.get_pipelines()
                pipe = pipelines.get(cam_id)
                if pipe and hasattr(pipe, "camera") and pipe.camera is not None:
                    target_cam = pipe.camera

        if target_cam is None or not isinstance(target_cam, ThreadedCamera):
            return {"ok": False, "error": f"Kamera '{cam_id}' nicht gefunden oder kein Live-Capture"}

        # Apply — use current values as fallback for unspecified fields
        cur = target_cam.get_capture_config()["requested"]
        new_w = width if width is not None else cur["width"]
        new_h = height if height is not None else cur["height"]
        new_fps = fps if fps is not None else cur["fps"]

        try:
            config = target_cam.apply_settings(new_w, new_h, new_fps)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}

        return {"ok": True, "camera_id": cam_id, **config}

    # --- Recording ---

    @router.post("/api/recording/start")
    async def start_recording(request: Request) -> dict:
        """Start recording raw camera frames to .mp4 file.

        Body (all optional): {"filename": "test.mp4", "fps": 30}
        """
        recorder = app_state.get("recorder")
        if recorder is None:
            return {"ok": False, "error": "Recorder nicht initialisiert"}
        if recorder.is_recording:
            return {"ok": False, "error": "Aufnahme laeuft bereits", **recorder.status()}

        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        filename = body.get("filename")
        fps = body.get("fps", 30.0)

        # Get frame size from pipeline
        pipeline = app_state.get("pipeline")
        frame_size = (640, 480)
        if pipeline:
            raw = pipeline.get_latest_raw_frame()
            if raw is not None:
                h, w = raw.shape[:2]
                frame_size = (w, h)

        try:
            output_path = recorder.start(filename=filename, fps=fps, frame_size=frame_size)
        except RuntimeError as e:
            return {"ok": False, "error": str(e)}

        return {"ok": True, "output_path": output_path, **recorder.status()}

    @router.post("/api/recording/stop")
    async def stop_recording() -> dict:
        """Stop recording and finalize the video file."""
        recorder = app_state.get("recorder")
        if recorder is None:
            return {"ok": False, "error": "Recorder nicht initialisiert"}
        summary = recorder.stop()
        return {"ok": summary.get("stopped", False), **summary}

    @router.get("/api/recording/status")
    async def recording_status() -> dict:
        """Get current recording status."""
        recorder = app_state.get("recorder")
        if recorder is None:
            return {"recording": False}
        return recorder.status()

    # --- Calibration ---

    async def _run_manual_board_alignment(points: list[list[float]]) -> dict:
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "board_calibration"):
            return {"ok": False, "error": "Pipeline nicht aktiv — bitte zuerst die Kamera starten."}
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
        return JSONResponse({"ok": False, "error": "Kein Kamerabild verfuegbar — ist die Kamera gestartet?"})

    async def _run_aruco_board_alignment(frame) -> dict:
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "board_calibration"):
            return {"ok": False, "error": "Pipeline nicht aktiv — bitte zuerst die Kamera starten."}
        result = pipeline.board_calibration.aruco_calibration_with_fallback(frame)
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
            return {"ok": False, "error": "Kein Kamerabild verfuegbar — ist die Kamera gestartet?"}
        return await _run_aruco_board_alignment(frame)

    @router.post("/api/calibration/board/aruco")
    async def board_aruco_calibration() -> dict:
        """Board alignment via ArUco markers on latest raw frame."""
        pipeline = app_state.get("pipeline")
        frame = pipeline.get_latest_raw_frame() if pipeline else None
        if frame is None:
            frame = app_state.get("latest_frame")
        if frame is None:
            return {"ok": False, "error": "Kein Kamerabild verfuegbar — ist die Kamera gestartet?"}
        return await _run_aruco_board_alignment(frame)

    async def _run_lens_charuco_calibration(request: Request | None = None) -> dict:
        """Capture latest raw frames and calibrate camera intrinsics."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "camera_calibration"):
            return {"ok": False, "error": "Pipeline nicht aktiv — bitte zuerst die Kamera starten."}
        if not pipeline.camera:
            return {"ok": False, "error": "Kamera nicht verfuegbar — bitte Verbindung pruefen."}
        body = await _optional_json_body(request)
        overrides = _charuco_override_fields(body)
        try:
            board_spec = pipeline.camera_calibration.get_charuco_board_spec(**overrides)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}

        frames = []
        for _ in range(30):
            raw = pipeline.get_latest_raw_frame()
            if raw is not None:
                frames.append(raw.copy())
            _time.sleep(0.1)

        if len(frames) < 3:
            return {"ok": False, "error": f"Nur {len(frames)} Frames erfasst (mind. 3 noetig) — Kamera pruefen."}
        result = pipeline.camera_calibration.charuco_calibration(frames, board_spec=board_spec)
        if result.get("ok"):
            pipeline.refresh_remapper()
        return result

    @router.post("/api/calibration/charuco")
    async def charuco_calibration(request: Request) -> dict:
        """Legacy endpoint: now performs lens setup via ChArUco."""
        return await _run_lens_charuco_calibration(request)

    @router.post("/api/calibration/lens/charuco")
    async def lens_charuco_calibration(request: Request) -> dict:
        """Lens setup: estimate camera intrinsics with ChArUco."""
        return await _run_lens_charuco_calibration(request)

    @router.get("/api/calibration/lens/info")
    async def lens_info() -> dict:
        """Get lens calibration metadata."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "camera_calibration"):
            return {"ok": False, "error": "Pipeline nicht aktiv — bitte zuerst die Kamera starten."}
        cfg = pipeline.camera_calibration.get_config()
        board_spec = pipeline.camera_calibration.get_charuco_board_spec()
        return {
            "ok": True,
            "valid": bool(cfg.get("lens_valid", False)),
            "method": cfg.get("lens_method"),
            "image_size": cfg.get("lens_image_size"),
            "reprojection_error": cfg.get("lens_reprojection_error"),
            "charuco_board": board_spec.to_api_payload(),
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
        return JSONResponse({"ok": False, "error": "Keine ROI-Vorschau — Board-Kalibrierung zuerst durchfuehren."})

    @router.post("/api/calibration/verify-rings")
    async def verify_rings() -> dict:
        """Verify calibrated ring radii against expected dartboard dimensions."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "Pipeline nicht aktiv — bitte zuerst die Kamera starten."}
        roi = pipeline.get_roi_preview()
        if roi is None:
            return {"ok": False, "error": "Kein ROI-Frame — Board-Kalibrierung zuerst durchfuehren."}
        result = pipeline.board_calibration.verify_rings(roi)
        return result

    @router.post("/api/calibration/optical-center")
    async def detect_optical_center() -> dict:
        """Detect the true bullseye position via color thresholding."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "Pipeline nicht aktiv — bitte zuerst die Kamera starten."}
        oc = pipeline.detect_optical_center()
        if oc is None:
            return {"ok": False, "error": "Mittelpunkt konnte nicht erkannt werden — manuell setzen."}
        return {"ok": True, "optical_center": [oc[0], oc[1]]}

    @router.post("/api/calibration/optical-center/manual")
    async def set_optical_center_manual(request: Request) -> dict:
        """Manually override the bullseye position (ROI pixel coordinates)."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "Pipeline nicht aktiv — bitte zuerst die Kamera starten."}
        if not (hasattr(pipeline, "board_calibration") and pipeline.board_calibration.is_valid()):
            return {"ok": False, "error": "Board nicht kalibriert"}
        body = await request.json()
        x = body.get("x")
        y = body.get("y")
        if x is None or y is None:
            return {"ok": False, "error": "x und y erforderlich"}
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            return {"ok": False, "error": "x und y müssen Zahlen sein"}
        pipeline.board_calibration.store_optical_center((x, y))
        if hasattr(pipeline, "_refresh_geometry"):
            pipeline._refresh_geometry()
        return {"ok": True, "optical_center": [x, y]}

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
        return JSONResponse({"ok": False, "error": "Kein Overlay verfuegbar — Board-Kalibrierung zuerst durchfuehren."})

    @router.get("/api/calibration/info")
    async def calibration_info() -> dict:
        """Get combined calibration metadata (board + lens)."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "board_calibration"):
            return {"ok": False, "error": "Pipeline nicht aktiv — bitte zuerst die Kamera starten."}
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
        """Run stereo calibration between two cameras.

        Requires: Both cameras must be running in the multi-pipeline
        and have valid lens intrinsics.
        Captures synchronized frame pairs, runs stereo_calibrate,
        saves to multi_cam.yaml.
        """
        body = await request.json()
        cam_a = body.get("camera_a", "default")
        cam_b = body.get("camera_b")
        if not cam_b:
            return {"ok": False, "error": "camera_b is required"}

        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-camera pipeline is not running"}

        pipelines = multi.get_pipelines()
        pipe_a = pipelines.get(cam_a)
        pipe_b = pipelines.get(cam_b)
        if pipe_a is None or pipe_b is None:
            return {"ok": False, "error": f"Camera '{cam_a}' or '{cam_b}' not found in active pipelines"}

        # Pre-flight: Intrinsics-Validierung via validate_stereo_prerequisites
        from src.cv.stereo_calibration import validate_stereo_prerequisites
        preflight = validate_stereo_prerequisites(cam_a, cam_b)
        if not preflight["ready"]:
            error_msg = (
                "Bitte Linsen-Kalibrierung zuerst durchfuehren. "
                + " ".join(preflight["errors"])
            )
            return {"ok": False, "error": error_msg, "preflight": preflight}
        intr_a = pipe_a.camera_calibration.get_intrinsics()
        intr_b = pipe_b.camera_calibration.get_intrinsics()

        # Capture synchronized frame pairs
        num_pairs = body.get("num_pairs", 15)
        capture_delay = body.get("capture_delay", 0.5)
        frames_a = []
        frames_b = []

        from src.web.stereo_progress import StereoProgressTracker
        from src.cv.stereo_calibration import detect_charuco_corners
        import cv2

        valid_pairs_count = 0
        for i in range(num_pairs):
            raw_a = pipe_a.get_latest_raw_frame()
            raw_b = pipe_b.get_latest_raw_frame()
            detected_a = False
            detected_b = False
            if raw_a is not None and raw_b is not None:
                frames_a.append(raw_a.copy())
                frames_b.append(raw_b.copy())
                gray_a = cv2.cvtColor(raw_a, cv2.COLOR_BGR2GRAY) if len(raw_a.shape) == 3 else raw_a
                gray_b = cv2.cvtColor(raw_b, cv2.COLOR_BGR2GRAY) if len(raw_b.shape) == 3 else raw_b
                corners_a, _ = detect_charuco_corners(gray_a)
                corners_b, _ = detect_charuco_corners(gray_b)
                detected_a = corners_a is not None
                detected_b = corners_b is not None
                if detected_a and detected_b:
                    valid_pairs_count += 1

            progress = StereoProgressTracker.frame_progress(
                i, num_pairs, detected_a, detected_b,
                valid_pairs=valid_pairs_count, phase="capture",
            )
            em = app_state.get("event_manager")
            if em and hasattr(em, 'broadcast_sync'):
                em.broadcast_sync("stereo_progress", progress)
            _time.sleep(capture_delay)

        # Broadcast computing phase
        em = app_state.get("event_manager")
        if em and hasattr(em, 'broadcast_sync'):
            em.broadcast_sync("stereo_progress", {
                "type": "stereo_progress",
                "phase": "computing",
                "percent": 100,
                "valid_pairs": valid_pairs_count,
                "total": num_pairs,
            })

        if len(frames_a) < 5:
            return {"ok": False, "error": f"Only captured {len(frames_a)} pairs, need at least 5"}

        # Run stereo calibration
        from src.cv.stereo_calibration import stereo_calibrate
        try:
            if _has_charuco_override(body):
                board_spec = pipe_a.camera_calibration.get_charuco_board_spec(
                    **_charuco_override_fields(body),
                )
            else:
                board_spec = pipe_a.camera_calibration.get_charuco_board_spec()
                board_spec_b = pipe_b.camera_calibration.get_charuco_board_spec()
                if board_spec != board_spec_b:
                    return {
                        "ok": False,
                        "error": (
                            "Configured ChArUco board differs between cameras. "
                            "Provide an explicit preset or board geometry for stereo calibration."
                        ),
                    }
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        result = stereo_calibrate(
            frames_a, frames_b,
            intr_a.camera_matrix, intr_a.dist_coeffs,
            intr_b.camera_matrix, intr_b.dist_coeffs,
            board_spec=board_spec,
        )

        if not result.ok:
            return {"ok": False, "error": result.error_message}

        # Save to multi_cam.yaml
        from src.utils.config import save_stereo_pair
        save_stereo_pair(
            cam_a, cam_b,
            result.R.tolist(), result.T.tolist(),
            result.reprojection_error,
        )

        # Hot-reload extrinsics into the running pipeline (non-fatal on failure)
        multi = app_state.get("multi_pipeline")
        if multi is not None and hasattr(multi, "reload_stereo_params"):
            try:
                multi.reload_stereo_params()
                logger.info("Stereo params reloaded into live pipeline after calibration")
            except Exception as reload_err:
                logger.warning("Failed to reload stereo params: %s", reload_err)

        result_event = StereoProgressTracker.calibration_result(
            result.reprojection_error, len(frames_a), cam_a, cam_b
        )
        em = app_state.get("event_manager")
        if em and hasattr(em, 'broadcast_sync'):
            em.broadcast_sync("stereo_result", result_event)

        return {
            "ok": True,
            "reprojection_error": result.reprojection_error,
            "pairs_used": len(frames_a),
            "camera_a": cam_a,
            "camera_b": cam_b,
            "charuco_board": board_spec.to_api_payload(),
        }

    @router.post("/api/calibration/stereo/reload")
    async def reload_stereo_extrinsics() -> dict:
        """Reload stereo extrinsics from disk into the running multi-pipeline.

        Use this after manually editing multi_cam.yaml or if the auto-reload
        during calibration failed.
        """
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-camera pipeline is not running"}
        if not hasattr(multi, "reload_stereo_params"):
            return {"ok": False, "error": "Pipeline does not support hot reload"}
        try:
            multi.reload_stereo_params()
            return {
                "ok": True,
                "stereo_pairs": len(multi._stereo_params),
                "board_transforms": len(multi._board_transforms),
            }
        except Exception as e:
            logger.error("Stereo param reload failed: %s", e)
            return {"ok": False, "error": str(e)}

    @router.post("/api/calibration/board-pose")
    async def board_pose_calibration(request: Request) -> dict:
        """Estimate and save the 3D pose of the dartboard relative to a camera.

        Detects the 4 ArUco markers (DICT_4X4_50) on the board, runs solvePnP
        using their known physical positions, and saves R_cb + t_cb to
        multi_cam.yaml so triangulation can map from camera frame to board frame.

        Requires: Camera must have valid lens intrinsics.
        Body: {"camera_id": "cam_left"}
        """
        import cv2 as _cv2
        import numpy as _np
        from src.cv.calibration import ARUCO_MARKER_SIZE_MM, MARKER_SPACING_MM

        body = await request.json()
        cam_id = body.get("camera_id", "")
        if not cam_id:
            return {"ok": False, "error": "camera_id is required"}

        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-camera pipeline not running"}

        pipelines = multi.get_pipelines()
        pipeline = pipelines.get(cam_id)
        if pipeline is None:
            return {"ok": False, "error": f"Camera '{cam_id}' not found in multi-pipeline"}

        intr = pipeline.camera_calibration.get_intrinsics()
        if intr is None:
            return {"ok": False, "error": f"Camera '{cam_id}' has no lens intrinsics — run lens calibration first"}

        frame = pipeline.get_latest_raw_frame()
        if frame is None:
            return {"ok": False, "error": "No frame available from camera"}

        # --- Detect ArUco markers ---
        dictionary = _cv2.aruco.getPredefinedDictionary(_cv2.aruco.DICT_4X4_50)
        params = _cv2.aruco.DetectorParameters()
        params.cornerRefinementMethod = _cv2.aruco.CORNER_REFINE_SUBPIX
        detector = _cv2.aruco.ArucoDetector(dictionary, params)

        gray = _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)
        if ids is None or len(ids) < 4:
            clahe = _cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            corners, ids, _ = detector.detectMarkers(clahe.apply(gray))

        if ids is None or len(ids) < 4:
            found = 0 if ids is None else len(ids)
            return {"ok": False, "error": f"Only found {found} ArUco markers (need IDs 0-3)"}

        flat_ids = ids.flatten().tolist()
        for eid in [0, 1, 2, 3]:
            if eid not in flat_ids:
                return {"ok": False, "error": f"Marker ID {eid} not detected. Found: {flat_ids}"}

        # Order marker centers TL→TR→BR→BL by image position (same as board calibration)
        marker_centers = []
        for eid in [0, 1, 2, 3]:
            idx = flat_ids.index(eid)
            mc = corners[idx][0]
            marker_centers.append([float(mc[:, 0].mean()), float(mc[:, 1].mean())])

        centers_arr = _np.float32(marker_centers)
        s = centers_arr.sum(axis=1)
        d = _np.diff(centers_arr, axis=1).flatten()
        order = [int(_np.argmin(s)), int(_np.argmin(d)), int(_np.argmax(s)), int(_np.argmax(d))]
        image_points = _np.array([marker_centers[i] for i in order], dtype=_np.float64)

        # --- 3D object points in board frame (meters, Z=0 = board face) ---
        # Markers are at corners of a square with center-to-center distance MARKER_SPACING_MM.
        # Board frame: X right, Y up, Z out of board face.
        half_m = (MARKER_SPACING_MM / 2.0) / 1000.0  # 0.205 m
        object_points = _np.array([
            [-half_m, +half_m, 0.0],  # TL marker center
            [+half_m, +half_m, 0.0],  # TR marker center
            [+half_m, -half_m, 0.0],  # BR marker center
            [-half_m, -half_m, 0.0],  # BL marker center
        ], dtype=_np.float64)

        # --- solvePnP ---
        success, rvec, tvec = _cv2.solvePnP(
            object_points, image_points,
            intr.camera_matrix, intr.dist_coeffs,
            flags=_cv2.SOLVEPNP_IPPE,
        )
        if not success:
            return {"ok": False, "error": "solvePnP failed — check detection quality and intrinsics"}

        R_cb, _ = _cv2.Rodrigues(rvec)
        t_cb = tvec.reshape(3)

        # Reprojection error
        proj, _ = _cv2.projectPoints(object_points, rvec, tvec, intr.camera_matrix, intr.dist_coeffs)
        reproj_err = float(_np.mean(_np.linalg.norm(proj.reshape(-1, 2) - image_points, axis=1)))

        from src.utils.config import save_board_transform
        save_board_transform(cam_id, R_cb.tolist(), t_cb.tolist())
        logger.info(
            "Board pose saved for camera '%s': reproj_error=%.2f px", cam_id, reproj_err
        )

        # Hot-reload transforms into live pipeline
        if hasattr(multi, "reload_stereo_params"):
            try:
                multi.reload_stereo_params()
            except Exception as e:
                logger.warning("Board-pose hot-reload failed: %s", e)

        return {
            "ok": True,
            "camera_id": cam_id,
            "reprojection_error_px": reproj_err,
        }

    # --- Single-Camera Pipeline Routes ---

    @router.post("/api/single/start")
    async def single_start(request: Request) -> dict:
        """Start (or restart) single-camera pipeline with a chosen camera source.

        Body: {"src": 0}  — camera index (default 0).
        Stops any running multi or single pipeline first.
        """
        from src.main import stop_pipeline_thread, start_single_pipeline
        body = await _optional_json_body(request)
        camera_src = body.get("src", 0)

        _pl = app_state.get("pipeline_lock")
        with (_pl if _pl else _nullcontext()):
            # Stop multi if running
            if app_state.get("multi_pipeline_running"):
                stop_pipeline_thread(app_state, "multi", timeout=5.0)
                app_state["multi_latest_frames"] = {}
            # Stop existing single if running
            if app_state.get("pipeline_running") and app_state.get("pipeline"):
                try:
                    app_state["pipeline"].stop()
                except Exception:
                    pass
                app_state["pipeline_running"] = False
                app_state["pipeline"] = None
            stop_pipeline_thread(app_state, "single", timeout=5.0)

        _time.sleep(0.5)  # Windows needs time after camera release
        start_single_pipeline(app_state, camera_src=camera_src)

        # Wait for pipeline to initialize (up to 3s)
        for _ in range(30):
            _time.sleep(0.1)
            if app_state.get("pipeline_running"):
                break

        if not app_state.get("pipeline_running"):
            return {"ok": False, "error": "Single-Pipeline konnte nicht gestartet werden."}

        return {"ok": True, "src": camera_src}

    @router.post("/api/single/stop")
    async def single_stop() -> dict:
        """Stop single-camera pipeline."""
        from src.main import stop_pipeline_thread
        if not app_state.get("pipeline_running"):
            return {"ok": False, "error": "Single-pipeline not running"}

        _pl = app_state.get("pipeline_lock")
        with (_pl if _pl else _nullcontext()):
            stop_pipeline_thread(app_state, "single", timeout=5.0)
            if app_state.get("pipeline"):
                try:
                    app_state["pipeline"].stop()
                except Exception:
                    pass
                app_state["pipeline_running"] = False
                app_state["pipeline"] = None

        return {"ok": True}

    # --- Multi-Camera Pipeline Routes ---

    @router.get("/api/multi/readiness")
    async def multi_readiness() -> dict:
        """Check multi-camera setup readiness.

        Returns per-camera diagnostic: lens intrinsics, board calibration,
        board-pose transform, stereo pairs. Helps users understand what
        setup steps are still missing before multi-cam can work optimally.
        """
        multi = app_state.get("multi_pipeline")
        if multi is None:
            # Check if there's saved config we can report on
            from src.utils.config import load_multi_cam_config
            cfg = load_multi_cam_config()
            saved = cfg.get("last_cameras", [])
            return {
                "ok": True,
                "running": False,
                "saved_cameras": saved,
                "message": "Multi-Pipeline nicht aktiv. Starte zuerst die Multi-Kamera Pipeline.",
            }

        pipelines = multi.get_pipelines()
        camera_ids = list(pipelines.keys())
        camera_readiness = []

        for cam_id in camera_ids:
            pipe = pipelines[cam_id]
            status = {"camera_id": cam_id, "issues": []}

            # Check lens intrinsics
            has_lens = False
            if hasattr(pipe, "camera_calibration"):
                intr = pipe.camera_calibration.get_intrinsics()
                has_lens = intr is not None
            status["lens_calibrated"] = has_lens
            if not has_lens:
                status["issues"].append(
                    "Keine Lens-Kalibrierung. Fuehre 'Lens Setup (ChArUco)' aus."
                )

            # Check board calibration
            has_board = False
            if hasattr(pipe, "board_calibration"):
                has_board = pipe.board_calibration.is_valid()
            status["board_calibrated"] = has_board
            if not has_board:
                status["issues"].append(
                    "Keine Board-Kalibrierung. Fuehre 'Board Manuell' oder 'Board ArUco' aus."
                )

            # Check board-pose transform
            has_pose = cam_id in multi._board_transforms
            status["board_pose"] = has_pose
            if not has_pose:
                status["issues"].append(
                    "Keine Board-Pose. Fuehre 'Board-Pose kalibrieren' aus (benoetigt Lens-Kalibrierung)."
                )

            status["ready"] = has_lens and has_board and has_pose
            camera_readiness.append(status)

        # Check stereo pairs
        stereo_pairs = []
        for i, cam_a in enumerate(camera_ids):
            for cam_b in camera_ids[i + 1:]:
                has_stereo = (
                    cam_a in multi._stereo_params and cam_b in multi._stereo_params
                )
                stereo_pairs.append({
                    "camera_a": cam_a,
                    "camera_b": cam_b,
                    "calibrated": has_stereo,
                })

        all_ready = all(c["ready"] for c in camera_readiness)
        any_stereo = any(p["calibrated"] for p in stereo_pairs)

        overall_issues = []
        if not all_ready:
            overall_issues.append("Nicht alle Kameras sind vollstaendig kalibriert.")
        if not any_stereo and len(camera_ids) >= 2:
            overall_issues.append(
                "Keine Stereo-Kalibrierung vorhanden. "
                "Triangulation ist deaktiviert, Voting-Fallback wird verwendet."
            )

        return {
            "ok": True,
            "running": True,
            "cameras": camera_readiness,
            "stereo_pairs": stereo_pairs,
            "all_ready": all_ready,
            "triangulation_possible": any_stereo and all_ready,
            "issues": overall_issues,
        }

    @router.post("/api/multi/start")
    async def multi_start(request: Request) -> dict:
        """Start multi-camera pipeline.

        Body: {"cameras": [{"camera_id": "cam_left", "src": 0},
                            {"camera_id": "cam_right", "src": 1}]}
        """
        if app_state.get("multi_pipeline_running"):
            return {"ok": False, "error": "Multi-pipeline already running"}

        body = await request.json()
        cameras = body.get("cameras", [])
        if len(cameras) < 2:
            return {"ok": False, "error": "Need at least 2 cameras"}

        # Validate camera configs
        seen_ids = set()
        for cam in cameras:
            if "camera_id" not in cam:
                return {"ok": False, "error": "Jede Kamera braucht eine camera_id"}
            cid = cam["camera_id"]
            if cid in seen_ids:
                return {"ok": False, "error": f"Doppelte camera_id: '{cid}'"}
            seen_ids.add(cid)

        # Stop the existing single pipeline thread cleanly
        from src.main import stop_pipeline_thread
        _pl = app_state.get("pipeline_lock")
        with (_pl if _pl else _nullcontext()):
            stop_pipeline_thread(app_state, "single", timeout=5.0)
            # Thread's finally block already calls pipeline.stop() + camera.release().
            # Only clean up state here — no redundant stop() call.
            if app_state.get("pipeline"):
                app_state["pipeline_running"] = False
                app_state["pipeline"] = None

        # Windows needs a moment after camera release before re-opening
        _time.sleep(0.5)

        # Start multi-pipeline in a background thread with its own stop event
        from src.main import _run_multi_pipeline
        stop_evt = threading.Event()
        app_state["multi_pipeline_stop_event"] = stop_evt
        multi_thread = threading.Thread(
            target=_run_multi_pipeline,
            args=(app_state, cameras, stop_evt),
            daemon=True,
            name="cv-multi-pipeline",
        )
        app_state["multi_pipeline_thread"] = multi_thread
        multi_thread.start()

        # Wait for pipeline to initialize (up to 3s)
        for _ in range(30):
            _time.sleep(0.1)
            if app_state.get("multi_pipeline_running"):
                break

        if not app_state.get("multi_pipeline_running"):
            # Check camera errors for better diagnostics
            multi = app_state.get("multi_pipeline")
            cam_errors = multi.get_camera_errors() if multi else {}
            error_detail = ""
            if cam_errors:
                error_detail = " Kamera-Fehler: " + "; ".join(
                    f"{cid}: {err}" for cid, err in cam_errors.items()
                )
            return {
                "ok": False,
                "error": (
                    "Multi-Pipeline konnte nicht gestartet werden."
                    " Pruefe ob alle Kameras angeschlossen sind."
                    + error_detail
                ),
                "camera_errors": cam_errors,
            }

        # Persist camera config for quick re-start
        from src.utils.config import save_last_cameras
        try:
            save_last_cameras(cameras)
        except Exception:
            pass  # non-fatal

        return {
            "ok": True,
            "cameras": [c["camera_id"] for c in cameras],
            "running": True,
        }

    @router.get("/api/multi/last-config")
    async def multi_last_config() -> dict:
        """Get the last-used multi-camera configuration for quick re-start."""
        from src.utils.config import get_last_cameras
        cameras = get_last_cameras()
        return {"ok": True, "cameras": cameras}

    @router.post("/api/multi/stop")
    async def multi_stop(request: Request) -> dict:
        """Stop multi-camera pipeline.

        Body (optional): {"restart_single": true, "single_src": 0}
        If restart_single is true, starts a single pipeline after stopping multi.
        """
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-pipeline not running"}

        body = await _optional_json_body(request)
        restart_single = body.get("restart_single", True)
        single_src = body.get("single_src", 0)

        # Signal the multi thread to stop and wait for it to exit
        from src.main import stop_pipeline_thread, start_single_pipeline
        _pl = app_state.get("pipeline_lock")
        with (_pl if _pl else _nullcontext()):
            stop_pipeline_thread(app_state, "multi", timeout=5.0)
            app_state["multi_latest_frames"] = {}

        result = {"ok": True}

        # Auto-restart single pipeline so the user isn't left without a camera
        if restart_single:
            _time.sleep(0.5)  # Windows needs time after camera release
            start_single_pipeline(app_state, camera_src=single_src)
            for _ in range(30):
                _time.sleep(0.1)
                if app_state.get("pipeline_running"):
                    break
            result["single_restarted"] = app_state.get("pipeline_running", False)
            result["single_src"] = single_src

        return result

    @router.get("/api/multi/status")
    async def multi_status() -> dict:
        """Get multi-camera pipeline status (per-camera FPS, calibration state)."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {
                "ok": True,
                "running": False,
                "cameras": [],
            }

        pipelines = multi.get_pipelines()
        camera_stats = []
        for cam_id, pipeline in pipelines.items():
            fps = 0.0
            if hasattr(pipeline, "fps_counter"):
                fps = pipeline.fps_counter.fps()
            board_valid = False
            lens_valid = False
            if hasattr(pipeline, "board_calibration"):
                board_valid = pipeline.board_calibration.is_valid()
            if hasattr(pipeline, "camera_calibration"):
                cfg = pipeline.camera_calibration.get_config()
                lens_valid = bool(cfg.get("lens_valid", False))
            camera_stats.append({
                "camera_id": cam_id,
                "fps": round(fps, 1),
                "board_calibrated": board_valid,
                "lens_calibrated": lens_valid,
            })

        # Include camera errors
        camera_errors = {}
        if hasattr(multi, "get_camera_errors"):
            camera_errors = multi.get_camera_errors()

        return {
            "ok": True,
            "running": app_state.get("multi_pipeline_running", False),
            "cameras": camera_stats,
            "camera_errors": camera_errors,
        }

    @router.get("/api/multi/errors")
    async def multi_errors() -> dict:
        """Polling-Fallback: Kamera-Fehler im Multi-Cam-Betrieb abrufen."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": True, "errors": {}, "message": "Multi-Pipeline nicht aktiv"}
        return {"ok": True, "errors": multi.get_camera_errors()}

    @router.get("/api/multi/intrinsics-status")
    async def multi_intrinsics_status() -> dict:
        """Per-camera intrinsics validity for multi-cam setup."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-Kamera-Pipeline laeuft nicht"}
        from src.cv.board_calibration import BoardCalibrationManager
        statuses = []
        for cfg in multi.camera_configs:
            cam_id = cfg["camera_id"]
            bcm = BoardCalibrationManager(camera_id=cam_id)
            has_intr = bcm.has_valid_intrinsics()
            statuses.append({"camera_id": cam_id, "has_intrinsics": has_intr})
        return {"ok": True, "cameras": statuses}

    @router.get("/api/multi/camera-health")
    async def multi_camera_health() -> dict:
        """Per-Kamera Gesundheitsstatus fuer Multi-Cam Setup."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-Kamera-Pipeline laeuft nicht"}
        from src.web.camera_health import CameraHealthMonitor
        monitor = CameraHealthMonitor()
        health = monitor.check_health(multi)
        return {"ok": True, "cameras": health}

    @router.post("/api/multi/camera/{camera_id}/reconnect")
    async def multi_camera_reconnect(camera_id: str) -> dict:
        """Manuellen Reconnect fuer eine bestimmte Kamera ausloesen."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-Kamera-Pipeline laeuft nicht"}
        result = multi.reconnect_camera(camera_id)
        return result

    @router.get("/api/multi/degraded")
    async def multi_degraded_cameras() -> dict:
        """Liste der dauerhaft ausgefallenen Kameras."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": True, "degraded": []}
        return {"ok": True, "degraded": multi.get_degraded_cameras()}

    # --- Per-Camera Video Feeds (Multi-Camera) ---

    @router.get("/video/feed/{camera_id}")
    async def video_feed_camera(camera_id: str) -> StreamingResponse:
        """MJPEG video stream for a specific camera in multi-pipeline."""
        async def generate():
            while True:
                frames = app_state.get("multi_latest_frames", {})
                frame = frames.get(camera_id)
                if frame is not None:
                    jpeg = encode_frame_jpeg(frame)
                    yield make_mjpeg_frame(jpeg)
                await asyncio.sleep(0.033)

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @router.get("/api/board/geometry")
    async def board_geometry() -> dict:
        """Expose canonical board geometry used by scoring/rendering."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "get_geometry_info"):
            return {"ok": False, "error": "Board-Geometrie nicht verfuegbar — Board-Kalibrierung zuerst durchfuehren."}
        return {"ok": True, **pipeline.get_geometry_info()}

    # --- Camera Health ---

    def _collect_camera_health(pipeline, multi_pipeline) -> dict:
        """Collect health info from all active cameras."""
        from src.cv.capture import ThreadedCamera
        health = {}
        if pipeline and hasattr(pipeline, "camera") and pipeline.camera is not None:
            cam = pipeline.camera
            if isinstance(cam, ThreadedCamera):
                health["default"] = cam.get_health()
        if multi_pipeline is not None:
            for cam_id, pipe in multi_pipeline.get_pipelines().items():
                if hasattr(pipe, "camera") and pipe.camera is not None:
                    cam = pipe.camera
                    if isinstance(cam, ThreadedCamera):
                        health[cam_id] = cam.get_health()
        return health

    @router.get("/api/camera/health")
    async def get_camera_health() -> dict:
        """Kamera-Gesundheitsstatus aller aktiven Kameras."""
        pipeline = app_state.get("pipeline")
        multi = app_state.get("multi_pipeline")
        health = _collect_camera_health(pipeline, multi)
        if not health:
            return {"ok": False, "error": "Keine aktive Kamera verfuegbar"}
        return {"ok": True, "cameras": health}

    @router.get("/api/camera/quality")
    async def get_camera_quality() -> dict:
        """Bildqualitaet (Schaerfe + Helligkeit) aller aktiven Kameras."""
        pipeline = app_state.get("pipeline")
        multi = app_state.get("multi_pipeline")
        quality: dict = {}
        if pipeline and hasattr(pipeline, "frame_diff_detector"):
            tracker = pipeline.frame_diff_detector._sharpness_tracker
            quality["default"] = tracker.get_quality_report()
        if multi is not None:
            for cam_id, pipe in multi.get_pipelines().items():
                if hasattr(pipe, "frame_diff_detector"):
                    tracker = pipe.frame_diff_detector._sharpness_tracker
                    quality[cam_id] = tracker.get_quality_report()
        if not quality:
            return {"ok": False, "error": "Keine aktive Kamera verfuegbar"}
        return {"ok": True, "cameras": quality}

    # --- Telemetry ---

    @router.get("/api/telemetry/history")
    async def get_telemetry_history(last_n: int = 60) -> dict:
        """Return telemetry history (FPS, queue, drops, memory over time)."""
        telemetry = app_state.get("telemetry")
        if not telemetry:
            return {"ok": False, "error": "Telemetry not initialized"}
        clamped = max(1, min(last_n, 300))
        return {
            "ok": True,
            "history": telemetry.get_history(last_n=clamped),
            "alerts": telemetry.get_alerts(),
            "summary": telemetry.get_summary(),
        }

    @router.get("/api/telemetry/export", response_model=None)
    async def export_telemetry(format: str = "json"):
        """Export full telemetry history as JSON or CSV download."""
        telemetry = app_state.get("telemetry")
        if not telemetry:
            return JSONResponse({"ok": False, "error": "Telemetry not initialized"})
        history = telemetry.get_history()
        summary = telemetry.get_summary()

        if format == "csv":
            import io
            import csv
            output = io.StringIO()
            if history:
                writer = csv.DictWriter(output, fieldnames=history[0].keys())
                writer.writeheader()
                writer.writerows(history)
            csv_bytes = output.getvalue().encode("utf-8")
            return StreamingResponse(
                iter([csv_bytes]),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=telemetry.csv"},
            )

        import json as _json
        session_id = app_state.get("session_id", "unknown")
        export_data: dict = {"session_id": session_id, "history": history, "summary": summary}
        # Add file size warning if JSONL writer is active
        jsonl_writer = app_state.get("telemetry_jsonl_writer")
        if jsonl_writer is not None:
            export_data["file_info"] = jsonl_writer.check_file_size()
        payload = _json.dumps(export_data, separators=(",", ":"))
        return StreamingResponse(
            iter([payload.encode("utf-8")]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=telemetry.json"},
        )

    @router.get("/api/telemetry/status")
    async def get_telemetry_status() -> dict:
        """Return telemetry file size, rotation status, and retention config."""
        writer = app_state.get("telemetry_jsonl_writer")
        if writer is None:
            return {
                "ok": True,
                "active": False,
                "message": "JSONL telemetry writer not active (set DARTVISION_TELEMETRY_FILE)",
            }
        file_info = writer.check_file_size()
        return {
            "ok": True,
            "active": True,
            "filepath": writer.filepath,
            "session_id": writer.session_id,
            "retain_days": writer._retain_days,
            **file_info,
        }

    @router.post("/api/telemetry/rotate")
    async def rotate_telemetry() -> dict:
        """Manually trigger telemetry file rotation and cleanup."""
        writer = app_state.get("telemetry_jsonl_writer")
        if writer is None:
            return {"ok": False, "error": "JSONL telemetry writer not active"}
        try:
            writer.force_rotate()
            deleted = writer.cleanup_old_files()
            return {"ok": True, "rotated": True, "old_files_deleted": deleted}
        except Exception as e:
            logger.error("Manual telemetry rotation failed: %s", e)
            return {"ok": False, "error": str(e)}

    @router.get("/api/telemetry/stereo")
    async def telemetry_stereo() -> dict:
        """Triangulations-Telemetrie."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-Kamera-Pipeline laeuft nicht"}
        if not hasattr(multi, "get_triangulation_telemetry"):
            return {"ok": False, "error": "Triangulations-Telemetrie nicht verfuegbar"}
        return {"ok": True, **multi.get_triangulation_telemetry()}

    # --- Multi-Cam Error Reporting & Telemetry API ---

    @router.get("/api/multi-cam/errors")
    async def multi_cam_errors() -> dict:
        """Return camera errors from multi-camera pipeline."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"errors": {}, "message": "Multi-Cam-Pipeline nicht aktiv"}
        return {"errors": multi.get_camera_errors()}

    @router.get("/api/multi-cam/telemetry")
    async def multi_cam_telemetry() -> dict:
        """Return triangulation and fusion telemetry."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"active": False, "message": "Multi-Cam-Pipeline nicht aktiv"}

        result = {
            "active": True,
            "triangulation": multi.get_triangulation_telemetry(),
            "fusion_config": multi.get_fusion_config(),
        }

        # Add governor stats if available
        if hasattr(multi, "get_governor_stats"):
            result["governors"] = multi.get_governor_stats()

        return result

    # --- Stats ---

    @router.get("/api/stats")
    async def get_stats() -> dict:
        """Get system stats (FPS, connections, dropped frames, queue pressure, memory)."""
        import os
        em = app_state.get("event_manager")
        pipeline = app_state.get("pipeline")
        fps = 0.0
        dropped_frames = 0
        queue_pressure = 0.0
        if pipeline and hasattr(pipeline, "fps_counter"):
            fps = pipeline.fps_counter.fps()
        if pipeline and hasattr(pipeline, "_dropped_frames"):
            dropped_frames = pipeline._dropped_frames
        if pipeline and hasattr(pipeline, "camera") and pipeline.camera is not None:
            if hasattr(pipeline.camera, "queue_pressure"):
                queue_pressure = pipeline.camera.queue_pressure
        lock = app_state.get("pending_hits_lock")
        pending_count = 0
        if lock:
            with lock:
                pending_count = len(app_state.get("pending_hits", {}))
        board_calibrated = False
        if pipeline and hasattr(pipeline, "board_calibration"):
            board_calibrated = pipeline.board_calibration.is_valid()

        # Lightweight process memory (RSS) — works on Linux and Windows without psutil
        memory_mb = 0.0
        try:
            import resource
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            memory_mb = round(rusage.ru_maxrss / 1024, 1)  # Linux: KB -> MB
        except (ImportError, AttributeError):
            try:
                import ctypes
                from ctypes import wintypes
                class _PMC(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                        ("PrivateUsage", ctypes.c_size_t),
                    ]
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

        # Camera health
        camera_health = _collect_camera_health(pipeline, app_state.get("multi_pipeline"))

        # Pipeline health: detection rate, last hits, calibration quality
        import time as _t
        now = _t.time()
        det_timestamps = app_state.get("detection_timestamps", [])
        # Hits in last 60 seconds -> hits/min
        recent_60 = [t for t in det_timestamps if t >= now - 60]
        detection_rate = len(recent_60)  # hits in last 60s = hits/min

        recent_detections = app_state.get("recent_detections", [])
        last_3_hits = recent_detections[-3:] if recent_detections else []

        # Calibration quality: 0-100 based on viewing angle quality
        calibration_quality = 0
        lens_calibrated = False
        homography_age = 0
        if pipeline and hasattr(pipeline, "board_calibration"):
            bc = pipeline.board_calibration
            if bc.is_valid():
                vaq = bc.get_viewing_angle_quality()
                calibration_quality = min(100, max(0, int(vaq * 100)))
            homography_age = bc.homography_age
        if pipeline and hasattr(pipeline, "lens_calibration"):
            lc = pipeline.lens_calibration
            if hasattr(lc, "is_valid") and lc.is_valid():
                lens_calibrated = True

        # Pipeline state: active / idle / degraded
        pipeline_running = app_state.get("pipeline_running", False)
        if not pipeline_running:
            pipeline_state = "idle"
        elif dropped_frames > 50 or queue_pressure > 0.8:
            pipeline_state = "degraded"
        else:
            pipeline_state = "active"

        return {
            "fps": round(fps, 1),
            "connections": em.connection_count if em else 0,
            "pipeline_running": pipeline_running,
            "multi_pipeline_running": app_state.get("multi_pipeline_running", False),
            "active_cameras": app_state.get("active_camera_ids", []),
            "pending_hits": pending_count,
            "board_calibrated": board_calibrated,
            "dropped_frames": dropped_frames,
            "queue_pressure": round(queue_pressure, 2),
            "memory_mb": memory_mb,
            "camera_health": camera_health,
            "pipeline_health": {
                "state": pipeline_state,
                "detection_rate": detection_rate,
                "last_hits": last_3_hits,
                "calibration_quality": calibration_quality,
                "lens_calibrated": lens_calibrated,
                "board_calibrated": board_calibrated,
                "homography_age": homography_age,
            },
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

    # P65: per-source lock + TTL cache for camera preview
    _preview_locks: dict[int, asyncio.Lock] = {}
    _preview_cache: dict[int, tuple[float, bytes]] = {}
    _PREVIEW_CACHE_TTL = 2.5  # seconds
    _PREVIEW_TIMEOUT = 5.0  # seconds

    @router.get("/api/camera/preview/{source}")
    async def camera_preview_snapshot(source: int) -> StreamingResponse:
        """Grab a single JPEG frame from a camera source for preview thumbnails.

        Opens the camera briefly, captures one frame, then releases it.
        This works independently of the running pipeline.
        Uses per-source locking to prevent concurrent camera access (P65).
        """
        import io

        # Check TTL cache first (no lock needed)
        cached = _preview_cache.get(source)
        if cached is not None:
            ts, data = cached
            if (_time.monotonic() - ts) < _PREVIEW_CACHE_TTL:
                return StreamingResponse(
                    io.BytesIO(data),
                    media_type="image/jpeg",
                    headers={"Cache-Control": "no-cache"},
                )

        # Get or create per-source lock
        if source not in _preview_locks:
            _preview_locks[source] = asyncio.Lock()
        lock = _preview_locks[source]

        try:
            async with asyncio.timeout(_PREVIEW_TIMEOUT):
                async with lock:
                    # Re-check cache after acquiring lock (another request may have filled it)
                    cached = _preview_cache.get(source)
                    if cached is not None:
                        ts, data = cached
                        if (_time.monotonic() - ts) < _PREVIEW_CACHE_TTL:
                            return StreamingResponse(
                                io.BytesIO(data),
                                media_type="image/jpeg",
                                headers={"Cache-Control": "no-cache"},
                            )

                    loop = asyncio.get_event_loop()

                    def _grab_frame():
                        cap = cv2.VideoCapture(source)
                        if not cap.isOpened():
                            return None
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                        ret, frame = cap.read()
                        cap.release()
                        if not ret or frame is None:
                            return None
                        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        return buf.tobytes()

                    jpeg_bytes = await loop.run_in_executor(None, _grab_frame)
                    if jpeg_bytes is None:
                        return JSONResponse({"ok": False, "error": "Camera not available"}, status_code=404)

                    # Store in cache
                    _preview_cache[source] = (_time.monotonic(), jpeg_bytes)

                    return StreamingResponse(
                        io.BytesIO(jpeg_bytes),
                        media_type="image/jpeg",
                        headers={"Cache-Control": "no-cache"},
                    )
        except TimeoutError:
            return JSONResponse(
                {"ok": False, "error": "Camera open timed out"},
                status_code=504,
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

    # --- Stereo Calibration Wizard API ---

    @router.get("/api/multi-cam/calibration/status")
    async def multi_cam_calibration_status() -> dict:
        """Check calibration readiness for each configured camera."""
        from src.cv.camera_calibration import CameraCalibrationManager
        from src.cv.board_calibration import BoardCalibrationManager
        from src.utils.config import load_multi_cam_config

        multi_cfg = load_multi_cam_config()
        cameras = multi_cfg.get("last_cameras", [])

        status = {}
        for cam in cameras:
            cam_id = cam.get("camera_id", "unknown")
            cam_cal = CameraCalibrationManager(camera_id=cam_id)
            board_cal = BoardCalibrationManager(camera_id=cam_id)

            intrinsics_result = cam_cal.validate_intrinsics()

            status[cam_id] = {
                "has_intrinsics": cam_cal.has_intrinsics(),
                "intrinsics_valid": intrinsics_result["valid"],
                "intrinsics_errors": intrinsics_result.get("errors", []),
                "intrinsics_warnings": intrinsics_result.get("warnings", []),
                "has_board_pose": board_cal.is_valid(),
                "viewing_angle_quality": board_cal.get_viewing_angle_quality(),
            }

        # Check stereo pairs
        pairs = multi_cfg.get("pairs", {})
        pair_status = {}
        for pair_key, pair_data in pairs.items():
            pair_status[pair_key] = {
                "has_extrinsics": True,
                "reprojection_error": pair_data.get("reprojection_error"),
            }

        return {
            "cameras": status,
            "pairs": pair_status,
            "ready_for_multi": all(
                s["has_intrinsics"] and s["has_board_pose"]
                for s in status.values()
            ) and len(pairs) > 0,
        }

    @router.post("/api/multi-cam/calibration/validate")
    async def multi_cam_calibration_validate(request: Request) -> dict:
        """Validate stereo calibration prerequisites for a camera pair."""
        body = await request.json()
        cam_a = body.get("cam_a")
        cam_b = body.get("cam_b")

        if not cam_a or not cam_b:
            return JSONResponse({"error": "cam_a und cam_b erforderlich"}, status_code=400)

        from src.cv.stereo_calibration import validate_stereo_prerequisites
        result = validate_stereo_prerequisites(cam_a, cam_b)
        return result

    return router
