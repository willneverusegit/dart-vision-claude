"""P64: Additional route tests to push routes.py coverage to 80%+.

Targets uncovered lines: validation helpers, game edge cases, multi pipeline
operations with running pipelines, telemetry edge cases, stats endpoint
branches, camera health/quality from multi, stereo telemetry success path.
"""

import threading
import numpy as np
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app, app_state


def _make_dummy_pipeline():
    pipe = MagicMock()
    pipe.board_calibration.is_valid.return_value = True
    pipe.board_calibration.get_config.return_value = {
        "valid": True, "method": "aruco", "mm_per_px": 0.85,
        "radii_px": [10, 19], "center_px": [200, 200], "schema_version": 2,
    }
    pipe.board_calibration.get_viewing_angle_quality.return_value = 0.85
    pipe.board_calibration.homography_age = 10
    pipe.camera_calibration.get_config.return_value = {"lens_valid": False}
    pipe.camera_calibration.get_intrinsics.return_value = None
    pipe.fps_counter.fps.return_value = 30.0
    pipe.show_overlay_motion = False
    pipe.show_overlay_markers = False
    pipe.get_roi_preview.return_value = np.zeros((400, 400, 3), dtype=np.uint8)
    pipe.get_field_overlay.return_value = np.zeros((400, 400, 3), dtype=np.uint8)
    pipe.get_latest_raw_frame.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
    pipe._last_motion_mask = None
    pipe._dropped_frames = 0
    pipe.camera = None
    pipe.get_geometry_info.return_value = {
        "center_px": [200, 200], "radii_px": [10, 19, 106, 116, 188, 200],
        "rotation_deg": 0, "lens_valid": False, "lens_method": None,
    }
    pipe.frame_diff_detector._sharpness_tracker.get_quality_report.return_value = {
        "sharpness": 80.0, "brightness": 120.0,
    }
    return pipe


class _SR:
    """Save/restore app_state keys."""
    def __init__(self, *keys):
        self._keys = keys
        self._saved = {}

    def __enter__(self):
        for k in self._keys:
            self._saved[k] = app_state.get(k)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                app_state.pop(k, None)
            else:
                app_state[k] = v


# --- Validation helpers ---

class TestValidationEdgeCases:
    def test_manual_score_invalid_score(self):
        """Trigger _validate_score_input error for invalid score."""
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": -5, "sector": 20, "multiplier": 1, "ring": "single",
            })
            data = resp.json()
            assert "error" in data

    def test_manual_score_invalid_sector(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": 20, "sector": 99, "multiplier": 1, "ring": "single",
            })
            assert "error" in resp.json()

    def test_manual_score_invalid_multiplier(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": 20, "sector": 20, "multiplier": 5, "ring": "single",
            })
            assert "error" in resp.json()

    def test_manual_score_invalid_ring(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": 20, "sector": 20, "multiplier": 1, "ring": "invalid",
            })
            assert "error" in resp.json()

    def test_manual_score_string_score(self):
        """Non-int score should fail validation."""
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": "abc", "sector": 20, "multiplier": 1, "ring": "single",
            })
            assert "error" in resp.json()

    def test_correct_hit_invalid_override(self):
        """Correct hit with invalid score values triggers validation error."""
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            lock = app_state.get("pending_hits_lock")
            if lock:
                with lock:
                    app_state["pending_hits"]["val1"] = {
                        "candidate_id": "val1", "score": 20, "sector": 20,
                        "multiplier": 1, "ring": "single",
                        "roi_x": 0, "roi_y": 0, "quality": 80, "timestamp": 0,
                    }
            resp = client.post("/api/hits/val1/correct", json={
                "score": -1, "sector": 99, "multiplier": 5, "ring": "bad",
            })
            data = resp.json()
            assert data["ok"] is False
            assert "Invalid" in data["error"]


# --- Game new_game edge cases ---

class TestNewGameEdgeCases:
    def test_new_game_invalid_mode_fallback(self):
        """Invalid mode should fall back to x01."""
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={
                "mode": "bogus", "players": ["A"],
            })
            assert resp.status_code == 200

    def test_new_game_invalid_players_fallback(self):
        """Non-list players should fall back to ['Player 1']."""
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={
                "mode": "free", "players": "not_a_list",
            })
            assert resp.status_code == 200

    def test_new_game_empty_players_fallback(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={
                "mode": "free", "players": [],
            })
            assert resp.status_code == 200

    def test_new_game_invalid_starting_score(self):
        """Out-of-range starting_score falls back to 501."""
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={
                "mode": "x01", "players": ["A"], "starting_score": 0,
            })
            assert resp.status_code == 200

    def test_new_game_no_engine(self):
        """No game engine returns error."""
        with TestClient(app) as client:
            saved = app_state.get("game_engine")
            app_state["game_engine"] = None
            try:
                resp = client.post("/api/game/new", json={
                    "mode": "free", "players": ["A"],
                })
                assert "error" in resp.json()
            finally:
                app_state["game_engine"] = saved

    def test_undo_no_engine(self):
        with TestClient(app) as client:
            saved = app_state.get("game_engine")
            app_state["game_engine"] = None
            try:
                resp = client.post("/api/game/undo")
                assert "error" in resp.json()
            finally:
                app_state["game_engine"] = saved

    def test_next_player_no_engine(self):
        with TestClient(app) as client:
            saved = app_state.get("game_engine")
            app_state["game_engine"] = None
            try:
                resp = client.post("/api/game/next-player")
                assert "error" in resp.json()
            finally:
                app_state["game_engine"] = saved

    def test_end_game_no_engine(self):
        with TestClient(app) as client:
            saved = app_state.get("game_engine")
            app_state["game_engine"] = None
            try:
                resp = client.post("/api/game/end")
                assert "error" in resp.json()
            finally:
                app_state["game_engine"] = saved

    def test_get_state_no_engine(self):
        with TestClient(app) as client:
            saved = app_state.get("game_engine")
            app_state["game_engine"] = None
            try:
                resp = client.get("/api/state")
                data = resp.json()
                assert data["phase"] == "idle"
            finally:
                app_state["game_engine"] = saved

    def test_manual_score_no_engine(self):
        with TestClient(app) as client:
            saved = app_state.get("game_engine")
            app_state["game_engine"] = None
            try:
                resp = client.post("/api/game/manual-score", json={
                    "score": 20, "sector": 20, "multiplier": 1, "ring": "single",
                })
                assert "error" in resp.json()
            finally:
                app_state["game_engine"] = saved


# --- Hit confirm/reject with no engine ---

class TestHitNoEngine:
    def test_confirm_no_engine(self):
        with TestClient(app) as client:
            saved = app_state.get("game_engine")
            app_state["game_engine"] = None
            try:
                lock = app_state.get("pending_hits_lock")
                if lock:
                    with lock:
                        app_state["pending_hits"]["ne1"] = {
                            "candidate_id": "ne1", "score": 20, "sector": 20,
                            "multiplier": 1, "ring": "single",
                        }
                resp = client.post("/api/hits/ne1/confirm")
                assert resp.json()["ok"] is False
            finally:
                app_state["game_engine"] = saved

    def test_correct_no_engine(self):
        with TestClient(app) as client:
            saved = app_state.get("game_engine")
            app_state["game_engine"] = None
            try:
                lock = app_state.get("pending_hits_lock")
                if lock:
                    with lock:
                        app_state["pending_hits"]["ne2"] = {
                            "candidate_id": "ne2", "score": 20, "sector": 20,
                            "multiplier": 1, "ring": "single",
                        }
                resp = client.post("/api/hits/ne2/correct", json={
                    "score": 20, "sector": 20, "multiplier": 1, "ring": "single",
                })
                assert resp.json()["ok"] is False
            finally:
                app_state["game_engine"] = saved


# --- Pending hits without lock ---

class TestPendingHitsNoLock:
    def test_get_pending_no_lock(self):
        with _SR("pending_hits_lock"):
            app_state["pending_hits_lock"] = None
            with TestClient(app) as client:
                resp = client.get("/api/hits/pending")
                assert resp.json()["hits"] == []

    def test_confirm_no_lock(self):
        with _SR("pending_hits_lock"):
            app_state["pending_hits_lock"] = None
            with TestClient(app) as client:
                resp = client.post("/api/hits/x/confirm")
                data = resp.json()
                assert data["ok"] is False

    def test_remove_darts_no_lock(self):
        with _SR("pending_hits_lock"):
            app_state["pending_hits_lock"] = None
            with TestClient(app) as client:
                resp = client.post("/api/game/remove-darts")
                assert resp.json()["ok"] is True


# --- Multi pipeline with running pipeline ---

class TestMultiRunning:
    def _make_multi(self):
        multi = MagicMock()
        pipe = _make_dummy_pipeline()
        multi.get_pipelines.return_value = {"cam_l": pipe, "cam_r": pipe}
        multi.get_camera_errors.return_value = {}
        multi.get_degraded_cameras.return_value = []
        multi._stereo_params = {}
        multi._board_transforms = {"cam_l": {}}
        multi.camera_configs = [
            {"camera_id": "cam_l"}, {"camera_id": "cam_r"},
        ]
        return multi

    def test_multi_intrinsics_status_running(self):
        with _SR("multi_pipeline"):
            multi = self._make_multi()
            app_state["multi_pipeline"] = multi
            with patch("src.cv.board_calibration.BoardCalibrationManager") as mock_bcm:
                inst = mock_bcm.return_value
                inst.has_valid_intrinsics.return_value = True
                with TestClient(app) as client:
                    resp = client.get("/api/multi/intrinsics-status")
                    data = resp.json()
                    assert data["ok"] is True
                    assert len(data["cameras"]) == 2

    def test_multi_camera_health_running(self):
        with _SR("multi_pipeline"):
            multi = self._make_multi()
            app_state["multi_pipeline"] = multi
            with patch("src.web.camera_health.CameraHealthMonitor") as mock_mon:
                mock_mon.return_value.check_health.return_value = [
                    {"camera_id": "cam_l", "healthy": True},
                ]
                with TestClient(app) as client:
                    resp = client.get("/api/multi/camera-health")
                    data = resp.json()
                    assert data["ok"] is True

    def test_multi_camera_reconnect_running(self):
        with _SR("multi_pipeline"):
            multi = self._make_multi()
            multi.reconnect_camera.return_value = {"ok": True}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.post("/api/multi/camera/cam_l/reconnect")
                assert resp.json()["ok"] is True

    def test_multi_cam_errors_running(self):
        with _SR("multi_pipeline"):
            multi = self._make_multi()
            multi.get_camera_errors.return_value = {"cam_l": "timeout"}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/errors")
                assert "cam_l" in resp.json()["errors"]

    def test_telemetry_stereo_success(self):
        with _SR("multi_pipeline"):
            multi = MagicMock()
            multi.get_triangulation_telemetry.return_value = {"pairs": 1, "hits": 5}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/stereo")
                data = resp.json()
                assert data["ok"] is True
                assert data["pairs"] == 1


# --- Telemetry edge cases ---

class TestTelemetryEdgeCases:
    def test_telemetry_rotate_exception(self):
        with _SR("telemetry_jsonl_writer"):
            writer = MagicMock()
            writer.force_rotate.side_effect = RuntimeError("disk full")
            app_state["telemetry_jsonl_writer"] = writer
            with TestClient(app) as client:
                resp = client.post("/api/telemetry/rotate")
                data = resp.json()
                assert data["ok"] is False

    def test_telemetry_export_not_initialized(self):
        with TestClient(app) as client:
            saved = app_state.get("telemetry")
            app_state["telemetry"] = None
            try:
                resp = client.get("/api/telemetry/export?format=json")
                assert resp.status_code == 200
                data = resp.json()
                assert data["ok"] is False
            finally:
                app_state["telemetry"] = saved

    def test_telemetry_export_csv_empty(self):
        with _SR("telemetry"):
            tel = MagicMock()
            tel.get_history.return_value = []
            tel.get_summary.return_value = {}
            app_state["telemetry"] = tel
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/export?format=csv")
                assert resp.status_code == 200


# --- Stats endpoint branches ---

class TestStatsBranches:
    def test_stats_pipeline_degraded(self):
        """Pipeline with high drops -> degraded state."""
        with _SR("pipeline", "pipeline_running", "multi_pipeline",
                 "detection_timestamps", "recent_detections"):
            pipe = _make_dummy_pipeline()
            pipe._dropped_frames = 100
            pipe.camera = MagicMock()
            pipe.camera.queue_pressure = 0.9
            app_state["pipeline"] = pipe
            app_state["pipeline_running"] = True
            app_state["multi_pipeline"] = None
            app_state["detection_timestamps"] = []
            app_state["recent_detections"] = []
            with TestClient(app) as client:
                resp = client.get("/api/stats")
                data = resp.json()
                assert data["pipeline_health"]["state"] == "degraded"

    def test_stats_pipeline_idle(self):
        with _SR("pipeline", "pipeline_running"):
            app_state["pipeline"] = None
            app_state["pipeline_running"] = False
            with TestClient(app) as client:
                resp = client.get("/api/stats")
                data = resp.json()
                assert data["pipeline_health"]["state"] == "idle"

    def test_stats_with_calibration_quality(self):
        """Stats with board calibration quality and detection rate."""
        import time
        with _SR("pipeline", "pipeline_running", "multi_pipeline",
                 "detection_timestamps", "recent_detections"):
            pipe = _make_dummy_pipeline()
            app_state["pipeline"] = pipe
            app_state["pipeline_running"] = True
            app_state["multi_pipeline"] = None
            app_state["detection_timestamps"] = [time.time(), time.time() - 10]
            app_state["recent_detections"] = [
                {"score": 20}, {"score": 60}, {"score": 1},
            ]
            with TestClient(app) as client:
                resp = client.get("/api/stats")
                data = resp.json()
                assert data["pipeline_health"]["calibration_quality"] > 0
                assert data["pipeline_health"]["detection_rate"] >= 2
                assert len(data["pipeline_health"]["last_hits"]) == 3


# --- Camera quality with multi pipeline ---

class TestCameraQualityMulti:
    def test_camera_quality_multi(self):
        with _SR("pipeline", "multi_pipeline"):
            app_state["pipeline"] = None
            multi = MagicMock()
            pipe = _make_dummy_pipeline()
            multi.get_pipelines.return_value = {"cam_l": pipe}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/camera/quality")
                data = resp.json()
                assert data["ok"] is True
                assert "cam_l" in data["cameras"]


# --- Camera health with multi pipeline ---

class TestCameraHealthMulti:
    def test_camera_health_with_multi(self):
        with _SR("pipeline", "multi_pipeline"):
            from src.cv.capture import ThreadedCamera
            app_state["pipeline"] = None
            multi = MagicMock()
            mock_cam = MagicMock(spec=ThreadedCamera)
            mock_cam.get_health.return_value = {"alive": True, "fps": 25.0}
            pipe = MagicMock()
            pipe.camera = mock_cam
            multi.get_pipelines.return_value = {"cam_l": pipe}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/camera/health")
                data = resp.json()
                assert data["ok"] is True
                assert "cam_l" in data["cameras"]

    def test_camera_health_single_pipeline(self):
        with _SR("pipeline", "multi_pipeline"):
            from src.cv.capture import ThreadedCamera
            mock_cam = MagicMock(spec=ThreadedCamera)
            mock_cam.get_health.return_value = {"alive": True}
            pipe = _make_dummy_pipeline()
            pipe.camera = mock_cam
            app_state["pipeline"] = pipe
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/camera/health")
                data = resp.json()
                assert data["ok"] is True
                assert "default" in data["cameras"]


# --- Capture config with camera ---

class TestCaptureConfigWithCamera:
    def test_get_capture_config_single(self):
        with _SR("pipeline", "multi_pipeline"):
            from src.cv.capture import ThreadedCamera
            mock_cam = MagicMock(spec=ThreadedCamera)
            mock_cam.get_capture_config.return_value = {
                "requested": {"width": 640, "height": 480, "fps": 30},
                "actual": {"width": 640, "height": 480, "fps": 30},
            }
            pipe = _make_dummy_pipeline()
            pipe.camera = mock_cam
            app_state["pipeline"] = pipe
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/capture/config")
                data = resp.json()
                assert data["ok"] is True
                assert "default" in data["cameras"]

    def test_set_capture_config_success(self):
        with _SR("pipeline", "multi_pipeline"):
            from src.cv.capture import ThreadedCamera
            mock_cam = MagicMock(spec=ThreadedCamera)
            mock_cam.get_capture_config.return_value = {
                "requested": {"width": 640, "height": 480, "fps": 30},
            }
            mock_cam.apply_settings.return_value = {
                "requested": {"width": 1280, "height": 720, "fps": 30},
                "actual": {"width": 1280, "height": 720, "fps": 30},
            }
            pipe = _make_dummy_pipeline()
            pipe.camera = mock_cam
            app_state["pipeline"] = pipe
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/capture/config", json={
                    "camera_id": "default", "width": 1280, "height": 720,
                })
                data = resp.json()
                assert data["ok"] is True

    def test_set_capture_config_runtime_error(self):
        with _SR("pipeline", "multi_pipeline"):
            from src.cv.capture import ThreadedCamera
            mock_cam = MagicMock(spec=ThreadedCamera)
            mock_cam.get_capture_config.return_value = {
                "requested": {"width": 640, "height": 480, "fps": 30},
            }
            mock_cam.apply_settings.side_effect = RuntimeError("unsupported")
            pipe = _make_dummy_pipeline()
            pipe.camera = mock_cam
            app_state["pipeline"] = pipe
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/capture/config", json={
                    "camera_id": "default", "width": 9999, "height": 9999,
                })
                data = resp.json()
                assert data["ok"] is False

    def test_set_capture_config_multi_camera(self):
        with _SR("pipeline", "multi_pipeline"):
            from src.cv.capture import ThreadedCamera
            mock_cam = MagicMock(spec=ThreadedCamera)
            mock_cam.get_capture_config.return_value = {
                "requested": {"width": 640, "height": 480, "fps": 30},
            }
            mock_cam.apply_settings.return_value = {
                "requested": {"width": 640, "height": 480, "fps": 60},
            }
            pipe = MagicMock()
            pipe.camera = mock_cam
            multi = MagicMock()
            multi.get_pipelines.return_value = {"cam_l": pipe}
            app_state["pipeline"] = None
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.post("/api/capture/config", json={
                    "camera_id": "cam_l", "fps": 60,
                })
                data = resp.json()
                assert data["ok"] is True


# --- Recording start with runtime error ---

class TestRecordingStartError:
    def test_start_recording_runtime_error(self):
        with TestClient(app) as client:
            saved_rec = app_state.get("recorder")
            saved_pipe = app_state.get("pipeline")
            rec = MagicMock()
            rec.is_recording = False
            rec.start.side_effect = RuntimeError("codec error")
            app_state["recorder"] = rec
            app_state["pipeline"] = None
            try:
                resp = client.post("/api/recording/start", json={})
                assert resp.json()["ok"] is False
            finally:
                app_state["recorder"] = saved_rec
                app_state["pipeline"] = saved_pipe

    def test_start_recording_no_content_type(self):
        """Start recording with no JSON content-type header."""
        with _SR("recorder", "pipeline"):
            rec = MagicMock()
            rec.is_recording = False
            rec.start.return_value = "out.mp4"
            rec.status.return_value = {"recording": True}
            app_state["recorder"] = rec
            app_state["pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/recording/start")
                assert resp.json()["ok"] is True


# --- Aruco calibration with frame from pipeline ---

class TestArucoWithFrame:
    def test_aruco_calibration_with_pipeline_frame(self):
        with _SR("pipeline", "latest_frame"):
            pipe = _make_dummy_pipeline()
            pipe.board_calibration.aruco_calibration_with_fallback.return_value = {
                "ok": True, "method": "aruco",
            }
            app_state["pipeline"] = pipe
            app_state["latest_frame"] = None
            with TestClient(app) as client:
                resp = client.post("/api/calibration/aruco")
                assert resp.json()["ok"] is True

    def test_board_aruco_with_pipeline_frame(self):
        with _SR("pipeline", "latest_frame"):
            pipe = _make_dummy_pipeline()
            pipe.board_calibration.aruco_calibration_with_fallback.return_value = {
                "ok": True,
            }
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/board/aruco")
                assert resp.json()["ok"] is True


# --- Multi/stop with restart_single ---

class TestMultiStopRestart:
    def test_multi_stop_with_restart(self):
        with _SR("multi_pipeline", "multi_pipeline_running", "pipeline_lock",
                 "multi_latest_frames", "pipeline", "pipeline_running"):
            multi = MagicMock()
            app_state["multi_pipeline"] = multi
            app_state["multi_pipeline_running"] = True
            app_state["pipeline_lock"] = threading.Lock()
            app_state["multi_latest_frames"] = {}

            def fake_start(state, camera_src=0):
                state["pipeline_running"] = True

            with patch("src.main.stop_pipeline_thread"), \
                 patch("src.main.start_single_pipeline", side_effect=fake_start):
                with TestClient(app) as client:
                    resp = client.post("/api/multi/stop",
                                       json={"restart_single": True, "single_src": 0})
                    data = resp.json()
                    assert data["ok"] is True
                    assert data.get("single_restarted") is True


# --- Charuco / Lens calibration ---

class TestCharucoCalibration:
    def test_charuco_no_pipeline(self):
        with _SR("pipeline"):
            app_state["pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/calibration/charuco", json={})
                assert resp.json()["ok"] is False

    def test_lens_charuco_no_camera(self):
        with _SR("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.camera = None
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/lens/charuco", json={})
                assert resp.json()["ok"] is False


# --- Multi readiness running with partial calibration ---

class TestMultiReadinessRunning:
    def test_readiness_running_partial(self):
        with _SR("multi_pipeline"):
            multi = MagicMock()
            pipe_a = _make_dummy_pipeline()
            pipe_a.camera_calibration.get_intrinsics.return_value = MagicMock()
            pipe_b = _make_dummy_pipeline()
            pipe_b.board_calibration.is_valid.return_value = False
            pipe_b.camera_calibration.get_intrinsics.return_value = None
            multi.get_pipelines.return_value = {"cam_l": pipe_a, "cam_r": pipe_b}
            multi._board_transforms = {"cam_l": {}}
            multi._stereo_params = {}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["ok"] is True
                assert data["running"] is True
                assert data["all_ready"] is False
                assert len(data["issues"]) > 0


# --- Single start stops existing running pipeline ---

class TestSingleStartStopsExisting:
    def test_single_start_stops_running_single(self):
        with _SR("pipeline", "pipeline_running", "pipeline_lock",
                 "multi_pipeline_running", "multi_pipeline"):
            pipe = _make_dummy_pipeline()
            app_state["pipeline"] = pipe
            app_state["pipeline_running"] = True
            app_state["multi_pipeline_running"] = False
            app_state["multi_pipeline"] = None
            app_state["pipeline_lock"] = threading.Lock()

            def fake_start(state, camera_src=0):
                state["pipeline_running"] = True
                state["pipeline"] = _make_dummy_pipeline()

            with patch("src.main.stop_pipeline_thread"), \
                 patch("src.main.start_single_pipeline", side_effect=fake_start):
                with TestClient(app) as client:
                    resp = client.post("/api/single/start", json={"src": 0})
                    assert resp.json()["ok"] is True


# --- Multi-cam telemetry without governor ---

class TestMultiCamTelemetryNoGovernor:
    def test_no_governor(self):
        with _SR("multi_pipeline"):
            multi = MagicMock(spec=["get_triangulation_telemetry", "get_fusion_config"])
            multi.get_triangulation_telemetry.return_value = {"pairs": 0}
            multi.get_fusion_config.return_value = {"method": "voting"}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                data = resp.json()
                assert data["active"] is True
                assert "governors" not in data
