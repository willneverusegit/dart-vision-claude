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

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def setup_routes(app_state: dict) -> APIRouter:
    """Create router with access to shared app state."""

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

    async def _run_lens_charuco_calibration(request: Request | None = None) -> dict:
        """Capture latest raw frames and calibrate camera intrinsics."""
        pipeline = app_state.get("pipeline")
        if not pipeline or not hasattr(pipeline, "camera_calibration"):
            return {"ok": False, "error": "No pipeline/camera calibration manager"}
        if not pipeline.camera:
            return {"ok": False, "error": "Camera not available"}
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
            return {"ok": False, "error": f"Only captured {len(frames)} frames, need at least 3"}
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
            return {"ok": False, "error": "No camera calibration manager"}
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

    @router.post("/api/calibration/optical-center/manual")
    async def set_optical_center_manual(request: Request) -> dict:
        """Manually override the bullseye position (ROI pixel coordinates)."""
        pipeline = app_state.get("pipeline")
        if not pipeline:
            return {"ok": False, "error": "No pipeline"}
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

        # Check that both cameras have lens intrinsics
        intr_a = pipe_a.camera_calibration.get_intrinsics()
        intr_b = pipe_b.camera_calibration.get_intrinsics()
        if intr_a is None:
            return {"ok": False, "error": f"Camera '{cam_a}' has no lens calibration"}
        if intr_b is None:
            return {"ok": False, "error": f"Camera '{cam_b}' has no lens calibration"}

        # Capture synchronized frame pairs
        num_pairs = body.get("num_pairs", 15)
        capture_delay = body.get("capture_delay", 0.5)
        frames_a = []
        frames_b = []

        for i in range(num_pairs):
            raw_a = pipe_a.get_latest_raw_frame()
            raw_b = pipe_b.get_latest_raw_frame()
            if raw_a is not None and raw_b is not None:
                frames_a.append(raw_a.copy())
                frames_b.append(raw_b.copy())
            _time.sleep(capture_delay)

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

    # --- Multi-Camera Pipeline Routes ---

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
        for cam in cameras:
            if "camera_id" not in cam:
                return {"ok": False, "error": "Each camera must have a camera_id"}

        # A1: Stop the existing single pipeline under the lifecycle lock
        _pl = app_state.get("pipeline_lock")
        with (_pl if _pl else _nullcontext()):
            if app_state.get("pipeline_running") and app_state.get("pipeline"):
                try:
                    app_state["pipeline"].stop()
                except Exception:
                    pass
                app_state["pipeline_running"] = False
                app_state["pipeline"] = None

        # Start multi-pipeline in a background thread
        from src.main import _run_multi_pipeline
        multi_thread = threading.Thread(
            target=_run_multi_pipeline,
            args=(app_state, cameras),
            daemon=True,
            name="cv-multi-pipeline",
        )
        multi_thread.start()

        # Wait for pipeline to initialize (up to 3s)
        for _ in range(30):
            _time.sleep(0.1)
            if app_state.get("multi_pipeline_running"):
                break

        if not app_state.get("multi_pipeline_running"):
            return {
                "ok": False,
                "error": "Multi-Pipeline konnte nicht gestartet werden. Prüfe ob alle Kameras angeschlossen sind.",
            }

        return {
            "ok": True,
            "cameras": [c["camera_id"] for c in cameras],
            "running": True,
        }

    @router.post("/api/multi/stop")
    async def multi_stop() -> dict:
        """Stop multi-camera pipeline."""
        multi = app_state.get("multi_pipeline")
        if multi is None:
            return {"ok": False, "error": "Multi-pipeline not running"}

        try:
            multi.stop()
        except Exception as e:
            logger.error("Error stopping multi-pipeline: %s", e)

        # A1: Mutate pipeline state under the lifecycle lock
        _pl = app_state.get("pipeline_lock")
        with (_pl if _pl else _nullcontext()):
            app_state["multi_pipeline"] = None
            app_state["multi_pipeline_running"] = False
            app_state["active_camera_ids"] = []
            app_state["multi_latest_frames"] = {}

        return {"ok": True}

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
        board_calibrated = False
        if pipeline and hasattr(pipeline, "board_calibration"):
            board_calibrated = pipeline.board_calibration.is_valid()
        return {
            "fps": round(fps, 1),
            "connections": em.connection_count if em else 0,
            "pipeline_running": app_state.get("pipeline_running", False),
            "multi_pipeline_running": app_state.get("multi_pipeline_running", False),
            "active_cameras": app_state.get("active_camera_ids", []),
            "pending_hits": pending_count,
            "board_calibrated": board_calibrated,
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
