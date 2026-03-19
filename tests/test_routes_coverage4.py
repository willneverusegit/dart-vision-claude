"""Tests to increase routes.py coverage — P64: target 80%+ coverage.

Covers: single/start, single/stop, multi/start success, WebSocket,
multi/stop, multi/last-config, multi/status, multi/errors,
multi/intrinsics-status, multi/camera-health, multi/degraded,
multi/readiness (running), telemetry endpoints, stereo/reload,
board geometry, camera quality, multi-cam API endpoints.
"""

import threading
import numpy as np
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app, app_state


def _make_dummy_pipeline():
    """Create a mock pipeline with common attributes."""
    pipe = MagicMock()
    pipe.board_calibration.is_valid.return_value = True
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
    pipe.get_geometry_info.return_value = {
        "center_px": [200, 200],
        "radii_px": [10, 19, 106, 116, 188, 200],
        "rotation_deg": 0,
        "lens_valid": False,
        "lens_method": None,
    }
    pipe.frame_diff_detector._sharpness_tracker.get_quality_report.return_value = {
        "sharpness": 80.0, "brightness": 120.0
    }
    return pipe


class _SaveRestore:
    """Context manager to save/restore app_state keys."""
    def __init__(self, *keys):
        self._keys = keys
        self._saved = {}

    def __enter__(self):
        for k in self._keys:
            self._saved[k] = app_state.get(k)
        return self

    def __exit__(self, *exc):
        for k in self._keys:
            if self._saved[k] is None:
                app_state.pop(k, None)
            else:
                app_state[k] = self._saved[k]


# ---- Single Pipeline Start/Stop ----

class TestSinglePipeline:
    def test_single_start_success(self):
        with _SaveRestore("pipeline", "pipeline_running", "pipeline_lock",
                          "multi_pipeline_running", "multi_pipeline"):
            app_state["pipeline"] = None
            app_state["pipeline_running"] = False
            app_state["multi_pipeline_running"] = False
            app_state["multi_pipeline"] = None
            app_state["pipeline_lock"] = threading.Lock()

            def fake_start(state, camera_src=0):
                state["pipeline_running"] = True
                state["pipeline"] = _make_dummy_pipeline()

            with patch("src.main.stop_pipeline_thread") as mock_stop, \
                 patch("src.main.start_single_pipeline", side_effect=fake_start):
                with TestClient(app) as client:
                    resp = client.post("/api/single/start", json={"src": 0})
                    data = resp.json()
                    assert data["ok"] is True
                    assert data["src"] == 0

    def test_single_start_failure(self):
        with _SaveRestore("pipeline", "pipeline_running", "pipeline_lock",
                          "multi_pipeline_running", "multi_pipeline"):
            app_state["pipeline"] = None
            app_state["pipeline_running"] = False
            app_state["multi_pipeline_running"] = False
            app_state["multi_pipeline"] = None
            app_state["pipeline_lock"] = threading.Lock()

            with patch("src.main.stop_pipeline_thread"), \
                 patch("src.main.start_single_pipeline"):
                with TestClient(app) as client:
                    resp = client.post("/api/single/start", json={"src": 0})
                    data = resp.json()
                    assert data["ok"] is False

    def test_single_start_stops_multi_first(self):
        with _SaveRestore("pipeline", "pipeline_running", "pipeline_lock",
                          "multi_pipeline_running", "multi_pipeline",
                          "multi_latest_frames"):
            app_state["pipeline"] = None
            app_state["pipeline_running"] = False
            app_state["multi_pipeline_running"] = True
            app_state["multi_pipeline"] = MagicMock()
            app_state["multi_latest_frames"] = {"cam_left": None}
            app_state["pipeline_lock"] = threading.Lock()

            def fake_start(state, camera_src=0):
                state["pipeline_running"] = True
                state["pipeline"] = _make_dummy_pipeline()

            with patch("src.main.stop_pipeline_thread"), \
                 patch("src.main.start_single_pipeline", side_effect=fake_start):
                with TestClient(app) as client:
                    resp = client.post("/api/single/start", json={"src": 1})
                    data = resp.json()
                    assert data["ok"] is True

    def test_single_stop_success(self):
        with _SaveRestore("pipeline", "pipeline_running", "pipeline_lock"):
            pipe = _make_dummy_pipeline()
            app_state["pipeline"] = pipe
            app_state["pipeline_running"] = True
            app_state["pipeline_lock"] = threading.Lock()

            with patch("src.main.stop_pipeline_thread"):
                with TestClient(app) as client:
                    resp = client.post("/api/single/stop")
                    data = resp.json()
                    assert data["ok"] is True

    def test_single_stop_not_running(self):
        with _SaveRestore("pipeline", "pipeline_running"):
            app_state["pipeline"] = None
            app_state["pipeline_running"] = False
            with TestClient(app) as client:
                resp = client.post("/api/single/stop")
                data = resp.json()
                assert data["ok"] is False


# ---- Multi Pipeline Start ----

class TestMultiPipelineStart:
    def test_multi_start_already_running(self):
        with _SaveRestore("multi_pipeline_running"):
            app_state["multi_pipeline_running"] = True
            with TestClient(app) as client:
                resp = client.post("/api/multi/start", json={
                    "cameras": [
                        {"camera_id": "cam_left", "src": 0},
                        {"camera_id": "cam_right", "src": 1},
                    ]
                })
                data = resp.json()
                assert data["ok"] is False
                assert "already running" in data["error"]

    def test_multi_start_too_few_cameras(self):
        with _SaveRestore("multi_pipeline_running"):
            app_state["multi_pipeline_running"] = False
            with TestClient(app) as client:
                resp = client.post("/api/multi/start", json={
                    "cameras": [{"camera_id": "cam_left", "src": 0}]
                })
                data = resp.json()
                assert data["ok"] is False

    def test_multi_start_duplicate_camera_id(self):
        with _SaveRestore("multi_pipeline_running"):
            app_state["multi_pipeline_running"] = False
            with TestClient(app) as client:
                resp = client.post("/api/multi/start", json={
                    "cameras": [
                        {"camera_id": "cam_left", "src": 0},
                        {"camera_id": "cam_left", "src": 1},
                    ]
                })
                data = resp.json()
                assert data["ok"] is False
                assert "Doppelte" in data["error"]

    def test_multi_start_missing_camera_id(self):
        with _SaveRestore("multi_pipeline_running"):
            app_state["multi_pipeline_running"] = False
            with TestClient(app) as client:
                resp = client.post("/api/multi/start", json={
                    "cameras": [
                        {"src": 0},
                        {"camera_id": "cam_right", "src": 1},
                    ]
                })
                data = resp.json()
                assert data["ok"] is False


# ---- Multi Pipeline Stop / Status / Errors ----

class TestMultiPipelineOps:
    def _make_multi(self):
        multi = MagicMock()
        pipe = _make_dummy_pipeline()
        multi.get_pipelines.return_value = {"cam_left": pipe, "cam_right": pipe}
        multi.get_camera_errors.return_value = {}
        multi.get_degraded_cameras.return_value = []
        multi._stereo_params = {}
        multi._board_transforms = {}
        multi.camera_configs = [
            {"camera_id": "cam_left"}, {"camera_id": "cam_right"}
        ]
        multi.get_triangulation_telemetry.return_value = {"hits": 0}
        multi.get_fusion_config.return_value = {"method": "voting"}
        return multi

    def test_multi_stop(self):
        with _SaveRestore("multi_pipeline", "multi_pipeline_running",
                          "pipeline_lock", "multi_latest_frames",
                          "pipeline", "pipeline_running"):
            multi = self._make_multi()
            app_state["multi_pipeline"] = multi
            app_state["multi_pipeline_running"] = True
            app_state["pipeline_lock"] = threading.Lock()
            app_state["multi_latest_frames"] = {}

            with patch("src.main.stop_pipeline_thread"), \
                 patch("src.main.start_single_pipeline"):
                with TestClient(app) as client:
                    resp = client.post("/api/multi/stop", json={"restart_single": False})
                    assert resp.json()["ok"] is True

    def test_multi_stop_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/multi/stop")
                assert resp.json()["ok"] is False

    def test_multi_status_running(self):
        with _SaveRestore("multi_pipeline", "multi_pipeline_running"):
            multi = self._make_multi()
            app_state["multi_pipeline"] = multi
            app_state["multi_pipeline_running"] = True
            with TestClient(app) as client:
                resp = client.get("/api/multi/status")
                data = resp.json()
                assert data["running"] is True
                assert len(data["cameras"]) == 2

    def test_multi_status_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/status")
                data = resp.json()
                assert data["running"] is False

    def test_multi_errors_running(self):
        with _SaveRestore("multi_pipeline"):
            multi = self._make_multi()
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi/errors")
                assert resp.json()["ok"] is True

    def test_multi_errors_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/errors")
                assert resp.json()["ok"] is True

    def test_multi_degraded(self):
        with _SaveRestore("multi_pipeline"):
            multi = self._make_multi()
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi/degraded")
                assert resp.json()["ok"] is True

    def test_multi_degraded_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/degraded")
                assert resp.json()["degraded"] == []

    def test_multi_last_config(self):
        with patch("src.utils.config.get_last_cameras", return_value=[]):
            with TestClient(app) as client:
                resp = client.get("/api/multi/last-config")
                assert resp.json()["ok"] is True

    def test_multi_intrinsics_status_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/intrinsics-status")
                assert resp.json()["ok"] is False

    def test_multi_camera_health_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/camera-health")
                assert resp.json()["ok"] is False

    def test_multi_readiness_running(self):
        with _SaveRestore("multi_pipeline"):
            multi = self._make_multi()
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["ok"] is True
                assert data["running"] is True

    def test_multi_readiness_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with patch("src.utils.config.load_multi_cam_config",
                       return_value={"last_cameras": []}):
                with TestClient(app) as client:
                    resp = client.get("/api/multi/readiness")
                    data = resp.json()
                    assert data["running"] is False

    def test_multi_camera_reconnect_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/multi/camera/cam_left/reconnect")
                assert resp.json()["ok"] is False

    def test_multi_camera_reconnect_running(self):
        with _SaveRestore("multi_pipeline"):
            multi = self._make_multi()
            multi.reconnect_camera.return_value = {"ok": True}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.post("/api/multi/camera/cam_left/reconnect")
                assert resp.json()["ok"] is True


# ---- WebSocket ----

class TestWebSocket:
    def test_ws_ping_pong(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                # Drain initial game_state message if present
                init = ws.receive_json()
                assert init["type"] == "game_state"
                # Now send ping
                ws.send_json({"command": "ping"})
                resp = ws.receive_json()
                assert resp["type"] == "pong"

    def test_ws_get_state(self):
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                # Drain initial game_state
                init = ws.receive_json()
                assert init["type"] == "game_state"
                # Send get_state command
                ws.send_json({"command": "get_state"})
                data = ws.receive_json()
                assert data["type"] == "game_state"

    def test_ws_with_pending_hits(self):
        with _SaveRestore("pending_hits_lock", "pending_hits"):
            lock = threading.Lock()
            app_state["pending_hits_lock"] = lock
            app_state["pending_hits"] = {
                "hit1": {"score": 20, "sector": 20, "multiplier": 1, "ring": "single"}
            }
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as ws:
                    # Drain initial game_state
                    init = ws.receive_json()
                    assert init["type"] == "game_state"
                    # Next should be hit_candidate
                    data = ws.receive_json()
                    assert data["type"] == "hit_candidate"


# ---- Telemetry ----

class TestTelemetryEndpoints:
    def test_telemetry_stereo_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/stereo")
                assert resp.json()["ok"] is False

    def test_telemetry_stereo_no_method(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock(spec=[])  # no attributes
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/stereo")
                assert resp.json()["ok"] is False

    def test_telemetry_status_no_writer(self):
        with _SaveRestore("telemetry_jsonl_writer"):
            app_state["telemetry_jsonl_writer"] = None
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/status")
                data = resp.json()
                assert data["active"] is False

    def test_telemetry_status_with_writer(self):
        with _SaveRestore("telemetry_jsonl_writer"):
            writer = MagicMock()
            writer.filepath = "/tmp/test.jsonl"
            writer.session_id = "abc123"
            writer._retain_days = 7
            writer.check_file_size.return_value = {"size_mb": 1.5}
            app_state["telemetry_jsonl_writer"] = writer
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/status")
                data = resp.json()
                assert data["active"] is True

    def test_telemetry_rotate_no_writer(self):
        with _SaveRestore("telemetry_jsonl_writer"):
            app_state["telemetry_jsonl_writer"] = None
            with TestClient(app) as client:
                resp = client.post("/api/telemetry/rotate")
                assert resp.json()["ok"] is False

    def test_telemetry_rotate_success(self):
        with _SaveRestore("telemetry_jsonl_writer"):
            writer = MagicMock()
            writer.cleanup_old_files.return_value = 2
            app_state["telemetry_jsonl_writer"] = writer
            with TestClient(app) as client:
                resp = client.post("/api/telemetry/rotate")
                data = resp.json()
                assert data["ok"] is True
                assert data["old_files_deleted"] == 2

    def test_telemetry_export_csv(self):
        with _SaveRestore("telemetry"):
            tel = MagicMock()
            tel.get_history.return_value = [{"fps": 30, "ts": 1000}]
            tel.get_summary.return_value = {"avg_fps": 30}
            app_state["telemetry"] = tel
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/export?format=csv")
                assert resp.status_code == 200
                assert "text/csv" in resp.headers["content-type"]

    def test_telemetry_export_json(self):
        with _SaveRestore("telemetry", "session_id", "telemetry_jsonl_writer"):
            tel = MagicMock()
            tel.get_history.return_value = []
            tel.get_summary.return_value = {}
            app_state["telemetry"] = tel
            app_state["session_id"] = "test123"
            app_state["telemetry_jsonl_writer"] = None
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/export?format=json")
                assert resp.status_code == 200

    def test_telemetry_export_json_with_writer(self):
        """Test telemetry export JSON path with a jsonl_writer present."""
        with _SaveRestore("telemetry", "session_id", "telemetry_jsonl_writer"):
            tel = MagicMock()
            tel.get_history.return_value = [{"fps": 30}]
            tel.get_summary.return_value = {"avg_fps": 30}
            writer = MagicMock()
            writer.check_file_size.return_value = {"size_mb": 0.5}
            app_state["telemetry"] = tel
            app_state["session_id"] = "test456"
            app_state["telemetry_jsonl_writer"] = writer
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/export?format=json")
                assert resp.status_code == 200


# ---- Multi-Cam Errors & Telemetry ----

class TestMultiCamAPI:
    def test_multi_cam_errors_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/errors")
                assert "errors" in resp.json()

    def test_multi_cam_telemetry_not_running(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                assert resp.json()["active"] is False

    def test_multi_cam_telemetry_running(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi.get_triangulation_telemetry.return_value = {"hits": 0}
            multi.get_fusion_config.return_value = {"method": "voting"}
            multi.get_governor_stats.return_value = {"cpu": 50}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                data = resp.json()
                assert data["active"] is True
                assert "governors" in data


# ---- Stereo Calibration Reload ----

class TestStereoReload:
    def test_reload_no_multi(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                assert resp.json()["ok"] is False

    def test_reload_no_method(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock(spec=[])  # no reload_stereo_params
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                assert resp.json()["ok"] is False

    def test_reload_success(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi._stereo_params = {"pair1": {}}
            multi._board_transforms = {"cam1": {}}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                data = resp.json()
                assert data["ok"] is True
                assert data["stereo_pairs"] == 1


# ---- Camera Quality ----

class TestCameraQuality:
    def test_camera_quality_with_pipeline(self):
        with _SaveRestore("pipeline", "multi_pipeline"):
            pipe = _make_dummy_pipeline()
            app_state["pipeline"] = pipe
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/camera/quality")
                data = resp.json()
                assert data["ok"] is True
                assert "default" in data["cameras"]

    def test_camera_quality_no_pipeline(self):
        with _SaveRestore("pipeline", "multi_pipeline"):
            app_state["pipeline"] = None
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/camera/quality")
                assert resp.json()["ok"] is False


# ---- Board Geometry ----

class TestBoardGeometry:
    def test_board_geometry_no_pipeline(self):
        with _SaveRestore("pipeline"):
            app_state["pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/board/geometry")
                assert resp.json()["ok"] is False

    def test_board_geometry_success(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.get("/api/board/geometry")
                data = resp.json()
                assert data["ok"] is True
                assert "center_px" in data


# ---- Multi-Cam Calibration Status ----

class TestMultiCamCalibrationStatus:
    def test_calibration_status(self):
        with patch("src.cv.camera_calibration.CameraCalibrationManager") as mock_cam, \
             patch("src.cv.board_calibration.BoardCalibrationManager") as mock_board, \
             patch("src.utils.config.load_multi_cam_config",
                   return_value={"last_cameras": [], "pairs": {}}):
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/calibration/status")
                data = resp.json()
                assert "cameras" in data

    def test_calibration_validate_missing_params(self):
        with TestClient(app) as client:
            resp = client.post("/api/multi-cam/calibration/validate",
                               json={"cam_a": "", "cam_b": ""})
            assert resp.status_code == 400

    def test_calibration_validate_success(self):
        with patch("src.cv.stereo_calibration.validate_stereo_prerequisites",
                   return_value={"ready": True, "errors": []}):
            with TestClient(app) as client:
                resp = client.post("/api/multi-cam/calibration/validate",
                                   json={"cam_a": "cam_left", "cam_b": "cam_right"})
                data = resp.json()
                assert data["ready"] is True


class TestCalibrationEndpointsWithMultiCam:
    def _setup_multi(self):
        left = _make_dummy_pipeline()
        right = _make_dummy_pipeline()
        multi = MagicMock()
        multi.get_pipelines.return_value = {
            "cam_left": left,
            "cam_right": right,
        }
        return multi, left, right

    def test_calibration_info_uses_selected_multi_camera(self):
        with _SaveRestore("pipeline", "multi_pipeline", "active_camera_ids"):
            multi, left, right = self._setup_multi()
            left.board_calibration.get_config.return_value = {"valid": False, "method": None}
            right.board_calibration.get_config.return_value = {
                "valid": True,
                "method": "aruco",
                "mm_per_px": 0.85,
                "radii_px": [10, 19, 106, 116, 188, 200],
                "center_px": [200, 200],
                "schema_version": 3,
            }
            right.camera_calibration.get_config.return_value = {
                "lens_valid": True,
                "lens_method": "charuco",
            }
            app_state["pipeline"] = None
            app_state["multi_pipeline"] = multi
            app_state["active_camera_ids"] = ["cam_left", "cam_right"]
            with TestClient(app) as client:
                resp = client.get("/api/calibration/info?camera_id=cam_right")
                data = resp.json()
                assert data["ok"] is True
                assert data["camera_id"] == "cam_right"
                assert data["board_valid"] is True
                assert data["board_method"] == "aruco"
                assert data["lens_valid"] is True

    def test_board_manual_uses_selected_multi_camera(self):
        with _SaveRestore("pipeline", "multi_pipeline", "active_camera_ids"):
            multi, left, right = self._setup_multi()
            right.board_calibration.manual_calibration.return_value = {"ok": True}
            app_state["pipeline"] = None
            app_state["multi_pipeline"] = multi
            app_state["active_camera_ids"] = ["cam_left", "cam_right"]
            with TestClient(app) as client:
                resp = client.post(
                    "/api/calibration/board/manual",
                    json={
                        "camera_id": "cam_right",
                        "points": [[0, 0], [1, 0], [1, 1], [0, 1]],
                    },
                )
                data = resp.json()
                assert data["ok"] is True
                assert data["camera_id"] == "cam_right"
                right.board_calibration.manual_calibration.assert_called_once()
                left.board_calibration.manual_calibration.assert_not_called()
                right.refresh_remapper.assert_called_once()

    def test_calibration_frame_uses_selected_multi_camera(self):
        with _SaveRestore("pipeline", "multi_pipeline", "active_camera_ids"):
            multi, _, right = self._setup_multi()
            right.get_latest_raw_frame.return_value = np.full((24, 32, 3), 255, dtype=np.uint8)
            app_state["pipeline"] = None
            app_state["multi_pipeline"] = multi
            app_state["active_camera_ids"] = ["cam_left", "cam_right"]
            with TestClient(app) as client:
                resp = client.get("/api/calibration/frame?camera_id=cam_right")
                data = resp.json()
                assert data["ok"] is True
                assert data["camera_id"] == "cam_right"
                assert data["image"].startswith("data:image/jpeg;base64,")

    def test_board_aruco_uses_selected_multi_camera(self):
        with _SaveRestore("pipeline", "multi_pipeline", "active_camera_ids"):
            multi, left, right = self._setup_multi()
            right.board_calibration.aruco_calibration_with_fallback.return_value = {"ok": True}
            app_state["pipeline"] = None
            app_state["multi_pipeline"] = multi
            app_state["active_camera_ids"] = ["cam_left", "cam_right"]
            with TestClient(app) as client:
                resp = client.post("/api/calibration/board/aruco", json={"camera_id": "cam_right"})
                data = resp.json()
                assert data["ok"] is True
                assert data["camera_id"] == "cam_right"
                right.board_calibration.aruco_calibration_with_fallback.assert_called_once()
                left.board_calibration.aruco_calibration_with_fallback.assert_not_called()

    def test_lens_info_uses_selected_multi_camera(self):
        with _SaveRestore("pipeline", "multi_pipeline", "active_camera_ids"):
            multi, left, right = self._setup_multi()
            board_spec = MagicMock()
            board_spec.to_api_payload.return_value = {"preset": "40x20"}
            right.camera_calibration.get_charuco_board_spec.return_value = board_spec
            right.camera_calibration.get_config.return_value = {
                "lens_valid": True,
                "lens_method": "charuco",
                "lens_image_size": [640, 480],
                "lens_reprojection_error": 0.12,
            }
            app_state["pipeline"] = None
            app_state["multi_pipeline"] = multi
            app_state["active_camera_ids"] = ["cam_left", "cam_right"]
            with TestClient(app) as client:
                resp = client.get("/api/calibration/lens/info?camera_id=cam_right")
                data = resp.json()
                assert data["ok"] is True
                assert data["camera_id"] == "cam_right"
                assert data["valid"] is True
                assert data["charuco_board"]["preset"] == "40x20"


# ---- Optical Center Manual ----

class TestOpticalCenterManual:
    def test_set_optical_center_no_pipeline(self):
        with _SaveRestore("pipeline"):
            app_state["pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={"x": 200, "y": 200})
                assert resp.json()["ok"] is False

    def test_set_optical_center_no_board(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.board_calibration.is_valid.return_value = False
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={"x": 200, "y": 200})
                assert resp.json()["ok"] is False

    def test_set_optical_center_missing_xy(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={"x": 200})
                assert resp.json()["ok"] is False

    def test_set_optical_center_invalid_type(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={"x": "abc", "y": 200})
                assert resp.json()["ok"] is False

    def test_set_optical_center_success(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center/manual",
                                   json={"x": 200.5, "y": 200.5})
                data = resp.json()
                assert data["ok"] is True
                assert data["optical_center"] == [200.5, 200.5]


class TestBoardPoseResultImage:
    def test_board_pose_returns_result_image_on_error_with_frame(self):
        """POST /api/calibration/board-pose error path (no ArUco on blank frame) — shape check."""
        pipe = _make_dummy_pipeline()

        cam_mtx = np.eye(3, dtype=np.float64)
        cam_mtx[0, 0] = 500
        cam_mtx[1, 1] = 500
        cam_mtx[0, 2] = 320
        cam_mtx[1, 2] = 240
        dist = np.zeros(5, dtype=np.float64)
        intr_mock = MagicMock()
        intr_mock.camera_matrix = cam_mtx
        intr_mock.dist_coeffs = dist
        pipe.camera_calibration.get_intrinsics.return_value = intr_mock

        pipe.board_calibration.get_calibration.return_value = {
            "radii_px": [10, 20, 80, 100, 160, 170],
        }

        multi = MagicMock()
        multi.get_pipelines.return_value = {"cam_left": pipe}

        with _SaveRestore("pipeline", "pipeline_running", "multi_pipeline_running", "multi_pipeline"):
            app_state["pipeline"] = None
            app_state["pipeline_running"] = False
            app_state["multi_pipeline_running"] = True
            app_state["multi_pipeline"] = multi

            with TestClient(app) as client:
                resp = client.post("/api/calibration/board-pose",
                                   json={"camera_id": "cam_left"})
        data = resp.json()
        # Blank frame → no ArUco markers detected → error response
        assert data["ok"] is False
        assert "error" in data

    def test_board_pose_no_camera_id(self):
        """Missing camera_id returns error immediately."""
        with _SaveRestore("multi_pipeline", "multi_pipeline_running"):
            multi = MagicMock()
            app_state["multi_pipeline"] = multi
            app_state["multi_pipeline_running"] = True
            with TestClient(app) as client:
                resp = client.post("/api/calibration/board-pose", json={})
        assert resp.json()["ok"] is False
        assert "camera_id" in resp.json()["error"]

    def test_board_pose_no_multi_pipeline(self):
        """No multi pipeline → error."""
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/calibration/board-pose",
                                   json={"camera_id": "cam_left"})
        assert resp.json()["ok"] is False

    def test_board_pose_success_returns_result_image(self):
        """Success path with mocked solvePnP and ArUco detection returns result_image."""
        pipe = _make_dummy_pipeline()

        cam_mtx = np.eye(3, dtype=np.float64)
        cam_mtx[0, 0] = 500
        cam_mtx[1, 1] = 500
        cam_mtx[0, 2] = 320
        cam_mtx[1, 2] = 240
        dist = np.zeros(5, dtype=np.float64)
        intr_mock = MagicMock()
        intr_mock.camera_matrix = cam_mtx
        intr_mock.dist_coeffs = dist
        pipe.camera_calibration.get_intrinsics.return_value = intr_mock
        pipe.board_calibration.get_calibration.return_value = {
            "radii_px": [10, 20, 80, 100, 160, 170],
        }

        multi = MagicMock()
        multi.get_pipelines.return_value = {"cam_left": pipe}

        # Build fake corners: 4 markers with IDs 0-3 at predictable positions
        def _corner(cx, cy, sz=20):
            return np.array([[
                [cx - sz, cy - sz],
                [cx + sz, cy - sz],
                [cx + sz, cy + sz],
                [cx - sz, cy + sz],
            ]], dtype=np.float32)

        fake_corners = [_corner(160, 120), _corner(480, 120), _corner(480, 360), _corner(160, 360)]
        fake_ids = np.array([[0], [1], [2], [3]])

        rvec_val = np.zeros((3, 1), dtype=np.float64)
        tvec_val = np.array([[0.0], [0.0], [1.0]], dtype=np.float64)

        with _SaveRestore("pipeline", "pipeline_running", "multi_pipeline_running", "multi_pipeline"):
            app_state["pipeline"] = None
            app_state["pipeline_running"] = False
            app_state["multi_pipeline_running"] = True
            app_state["multi_pipeline"] = multi

            with patch("cv2.aruco.ArucoDetector") as mock_detector_cls, \
                 patch("cv2.solvePnP", return_value=(True, rvec_val, tvec_val)), \
                 patch("cv2.projectPoints", return_value=(
                     np.array([[[160, 120]], [[480, 120]], [[480, 360]], [[160, 360]]], dtype=np.float32),
                     None,
                 )), \
                 patch("src.utils.config.save_board_transform"):
                mock_det = MagicMock()
                mock_det.detectMarkers.return_value = (fake_corners, fake_ids, None)
                mock_detector_cls.return_value = mock_det

                with TestClient(app) as client:
                    resp = client.post("/api/calibration/board-pose",
                                       json={"camera_id": "cam_left"})

        data = resp.json()
        assert data["ok"] is True, data
        assert "result_image" in data
        assert data["result_image"].startswith("data:image/jpeg;base64,")
        assert "quality_info" in data
        assert "reprojection_error_px" in data["quality_info"]
        assert "description" in data["quality_info"]


class TestCalibrationResultImage:
    def test_aruco_returns_result_image(self):
        pipe = _make_dummy_pipeline()
        pipe.board_calibration.aruco_calibration_with_fallback.return_value = {
            "ok": True,
            "homography": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "mm_per_px": 0.5,
            "corners_px": [[100, 100], [540, 100], [540, 380], [100, 380]],
            "radii_px": [10, 20, 80, 100, 160, 170],
            "detected_ids": [0, 1, 2, 3],
            "detection_method": "raw",
        }
        save = {}
        for k in ["pipeline", "pipeline_running", "multi_pipeline_running", "multi_pipeline"]:
            save[k] = app_state.get(k)
        try:
            app_state["pipeline"] = pipe
            app_state["pipeline_running"] = True
            app_state["multi_pipeline_running"] = False
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/calibration/aruco")
            assert resp.status_code == 200
            data = resp.json()
            assert data["ok"] is True
            assert "result_image" in data
            assert data["result_image"].startswith("data:image/jpeg;base64,")
            assert "quality_info" in data
            assert data["quality_info"]["markers_found"] == 4
        finally:
            for k, v in save.items():
                if v is None:
                    app_state.pop(k, None)
                else:
                    app_state[k] = v

    def test_lens_calibration_returns_result_image(self):
        """Lens calibration should include result_image on success."""
        pipe = _make_dummy_pipeline()
        pipe.camera = MagicMock()  # camera must be truthy
        pipe.camera_calibration.get_charuco_board_spec.return_value = MagicMock()
        pipe.camera_calibration.charuco_calibration.return_value = {
            "ok": True,
            "camera_matrix": np.eye(3).tolist(),
            "dist_coeffs": [0, 0, 0, 0, 0],
            "reprojection_error": 0.5,
            "image_size": [640, 480],
        }

        save = {}
        for k in ["pipeline", "pipeline_running", "multi_pipeline_running", "multi_pipeline"]:
            save[k] = app_state.get(k)
        try:
            app_state["pipeline"] = pipe
            app_state["pipeline_running"] = True
            app_state["multi_pipeline_running"] = False
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/calibration/lens/charuco")
            data = resp.json()
            assert data["ok"] is True
            assert "result_image" in data
            assert data["result_image"].startswith("data:image/jpeg;base64,")
            assert "quality_info" in data
            assert data["quality_info"]["reprojection_error"] == 0.5
        finally:
            for k, v in save.items():
                if v is None:
                    app_state.pop(k, None)
                else:
                    app_state[k] = v
