"""Tests to increase routes.py coverage — targeting untested endpoints and branches."""

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


# ---- CV Params ----

class TestCVParams:
    def test_get_cv_params_no_pipeline(self):
        with _SaveRestore("pipeline"):
            app_state["pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/cv-params")
                assert resp.json()["ok"] is False

    def test_get_cv_params_with_pipeline(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.frame_diff_detector.get_params.return_value = {
                "settle_frames": 5, "diff_threshold": 25,
                "min_diff_area": 50, "max_diff_area": 5000,
                "min_elongation": 1.5,
            }
            pipe.motion_detector.threshold = 30
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.get("/api/cv-params")
                data = resp.json()
                assert data["ok"] is True
                assert data["motion_threshold"] == 30

    def test_set_cv_params_no_pipeline(self):
        with _SaveRestore("pipeline"):
            app_state["pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/cv-params", json={"diff_threshold": 30})
                assert resp.json()["ok"] is False

    def test_set_cv_params_success(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.frame_diff_detector.set_params.return_value = {
                "settle_frames": 5, "diff_threshold": 30,
            }
            pipe.motion_detector.threshold = 25
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/cv-params", json={
                    "diff_threshold": 30, "motion_threshold": 25
                })
                data = resp.json()
                assert data["ok"] is True

    def test_set_cv_params_value_error(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.frame_diff_detector.set_params.side_effect = ValueError("bad value")
            pipe.motion_detector.threshold = 25
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/cv-params", json={"diff_threshold": -1})
                data = resp.json()
                assert data["ok"] is False

    def test_set_cv_params_with_elongation(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.frame_diff_detector.set_params.return_value = {"min_elongation": 2.0}
            pipe.motion_detector.threshold = 25
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/cv-params", json={"min_elongation": "2.0"})
                assert resp.json()["ok"] is True


# ---- Diagnostics Toggle ----

class TestDiagnosticsToggle:
    def test_toggle_no_pipeline(self):
        with _SaveRestore("pipeline"):
            app_state["pipeline"] = None
            with TestClient(app) as client:
                resp = client.post("/api/diagnostics/toggle", json={"path": "diagnostics"})
                assert resp.json()["ok"] is False

    def test_toggle_with_pipeline(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.frame_diff_detector.toggle_diagnostics.return_value = True
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/diagnostics/toggle", json={"path": "diagnostics"})
                data = resp.json()
                assert data["ok"] is True
                assert data["diagnostics_enabled"] is True


# ---- Recording ----

class TestRecordingEndpoints:
    def test_recording_status_no_recorder(self):
        with TestClient(app) as client:
            app_state["recorder"] = None
            resp = client.get("/api/recording/status")
            assert resp.json()["recording"] is False

    def test_recording_status_with_recorder(self):
        with TestClient(app) as client:
            rec = MagicMock()
            rec.status.return_value = {"recording": True, "frames": 100}
            app_state["recorder"] = rec
            resp = client.get("/api/recording/status")
            assert resp.json()["recording"] is True

    def test_start_recording_no_recorder(self):
        with TestClient(app) as client:
            app_state["recorder"] = None
            resp = client.post("/api/recording/start",
                               json={"filename": "test.mp4"})
            assert resp.json()["ok"] is False

    def test_start_recording_already_recording(self):
        with TestClient(app) as client:
            rec = MagicMock()
            rec.is_recording = True
            rec.status.return_value = {"recording": True}
            app_state["recorder"] = rec
            resp = client.post("/api/recording/start", json={})
            assert resp.json()["ok"] is False

    def test_start_recording_success(self):
        with TestClient(app) as client:
            rec = MagicMock()
            rec.is_recording = False
            rec.start.return_value = "output.mp4"
            rec.status.return_value = {"recording": True, "frames": 0}
            app_state["recorder"] = rec
            app_state["pipeline"] = _make_dummy_pipeline()
            resp = client.post("/api/recording/start", json={"fps": 25.0})
            data = resp.json()
            assert data["ok"] is True
            assert data["output_path"] == "output.mp4"

    def test_start_recording_runtime_error(self):
        with TestClient(app) as client:
            rec = MagicMock()
            rec.is_recording = False
            rec.start.side_effect = RuntimeError("disk full")
            app_state["recorder"] = rec
            app_state["pipeline"] = None
            resp = client.post("/api/recording/start", json={})
            assert resp.json()["ok"] is False

    def test_stop_recording_no_recorder(self):
        with TestClient(app) as client:
            app_state["recorder"] = None
            resp = client.post("/api/recording/stop")
            assert resp.json()["ok"] is False

    def test_stop_recording_success(self):
        with TestClient(app) as client:
            rec = MagicMock()
            rec.stop.return_value = {"stopped": True, "frames": 100, "path": "out.mp4"}
            app_state["recorder"] = rec
            resp = client.post("/api/recording/stop")
            assert resp.json()["ok"] is True


# ---- Multi Readiness ----

class TestMultiReadiness:
    def test_readiness_no_multi(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["ok"] is True
                assert data["running"] is False

    def test_readiness_with_multi(self):
        with _SaveRestore("multi_pipeline"):
            pipe_a = _make_dummy_pipeline()
            pipe_a.camera_calibration.get_intrinsics.return_value = MagicMock()
            pipe_b = _make_dummy_pipeline()
            pipe_b.camera_calibration.get_intrinsics.return_value = None

            multi = MagicMock()
            multi.get_pipelines.return_value = {"cam_a": pipe_a, "cam_b": pipe_b}
            multi._board_transforms = {"cam_a": {}}
            multi._stereo_params = {}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["ok"] is True
                assert data["running"] is True
                assert len(data["cameras"]) == 2


# ---- Multi Last Config ----

class TestMultiLastConfig:
    def test_last_config(self):
        with TestClient(app) as client:
            resp = client.get("/api/multi/last-config")
            data = resp.json()
            assert data["ok"] is True
            assert "cameras" in data


# ---- Multi Errors ----

class TestMultiErrors:
    def test_errors_no_multi(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/errors")
                data = resp.json()
                assert data["ok"] is True
                assert data["errors"] == {}

    def test_errors_with_multi(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi.get_camera_errors.return_value = {"cam_a": "timeout"}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi/errors")
                assert resp.json()["errors"]["cam_a"] == "timeout"


# ---- Multi Intrinsics Status ----

class TestMultiIntrinsicsStatus:
    def test_no_multi(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/intrinsics-status")
                assert resp.json()["ok"] is False

    def test_with_multi(self, monkeypatch):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi.camera_configs = [{"camera_id": "cam_a"}]
            app_state["multi_pipeline"] = multi
            monkeypatch.setattr(
                "src.cv.board_calibration.BoardCalibrationManager.has_valid_intrinsics",
                lambda self: True,
            )
            with TestClient(app) as client:
                resp = client.get("/api/multi/intrinsics-status")
                data = resp.json()
                assert data["ok"] is True
                assert data["cameras"][0]["has_intrinsics"] is True


# ---- Multi Camera Health ----

class TestMultiCameraHealth:
    def test_no_multi(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi/camera-health")
                assert resp.json()["ok"] is False

    def test_with_multi(self, monkeypatch):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            app_state["multi_pipeline"] = multi
            monkeypatch.setattr(
                "src.web.camera_health.CameraHealthMonitor.check_health",
                lambda self, m: [{"camera_id": "cam_a", "healthy": True}],
            )
            with TestClient(app) as client:
                resp = client.get("/api/multi/camera-health")
                data = resp.json()
                assert data["ok"] is True
                assert len(data["cameras"]) == 1


# ---- Camera Health ----

class TestCameraHealthEndpoint:
    def test_no_cameras(self):
        with _SaveRestore("pipeline", "multi_pipeline"):
            app_state["pipeline"] = None
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/camera/health")
                assert resp.json()["ok"] is False


# ---- Telemetry History ----

class TestTelemetryHistory:
    def test_no_telemetry(self):
        with TestClient(app) as client:
            app_state["telemetry"] = None
            resp = client.get("/api/telemetry/history")
            assert resp.json()["ok"] is False

    def test_with_telemetry(self):
        from src.utils.telemetry import TelemetryHistory, TelemetrySample
        with TestClient(app) as client:
            th = TelemetryHistory()
            th.record(TelemetrySample(timestamp=1.0, fps=30.0, queue_pressure=0.1,
                                      dropped_frames=0, memory_mb=100.0, cpu_percent=25.0))
            app_state["telemetry"] = th
            resp = client.get("/api/telemetry/history?last_n=10")
            data = resp.json()
            assert data["ok"] is True
            assert "history" in data
            assert "alerts" in data
            assert "summary" in data


# ---- Telemetry Stereo ----

class TestTelemetryStereo:
    def test_no_multi(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/stereo")
                assert resp.json()["ok"] is False

    def test_no_method(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock(spec=[])  # no get_triangulation_telemetry
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/stereo")
                assert resp.json()["ok"] is False

    def test_with_data(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi.get_triangulation_telemetry.return_value = {"total": 10, "success": 8}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/stereo")
                data = resp.json()
                assert data["ok"] is True
                assert data["total"] == 10


# ---- Multi-Cam Errors ----

class TestMultiCamErrors:
    def test_no_multi(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/errors")
                assert resp.json()["errors"] == {}

    def test_with_multi(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi.get_camera_errors.return_value = {"cam_x": "error"}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/errors")
                assert resp.json()["errors"]["cam_x"] == "error"


# ---- Multi-Cam Telemetry ----

class TestMultiCamTelemetry:
    def test_no_multi(self):
        with _SaveRestore("multi_pipeline"):
            app_state["multi_pipeline"] = None
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                data = resp.json()
                assert data["active"] is False

    def test_with_multi(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi.get_triangulation_telemetry.return_value = {"total": 5}
            multi.get_fusion_config.return_value = {"method": "voting"}
            multi.get_governor_stats.return_value = {"fps_limit": 30}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                data = resp.json()
                assert data["active"] is True
                assert "triangulation" in data
                assert "governors" in data

    def test_with_multi_no_governors(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock(spec=["get_triangulation_telemetry", "get_fusion_config", "get_pipelines", "get_camera_errors"])
            multi.get_triangulation_telemetry.return_value = {}
            multi.get_fusion_config.return_value = {}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                data = resp.json()
                assert data["active"] is True
                assert "governors" not in data


# ---- Multi-Cam Calibration Status ----

class TestMultiCamCalibrationStatus:
    def test_calibration_status(self):
        with TestClient(app) as client:
            resp = client.get("/api/multi-cam/calibration/status")
            data = resp.json()
            assert "cameras" in data
            assert "pairs" in data


# ---- Multi-Cam Calibration Validate ----

class TestMultiCamCalibrationValidate:
    def test_missing_params(self):
        with TestClient(app) as client:
            resp = client.post("/api/multi-cam/calibration/validate", json={})
            assert resp.status_code == 400

    def test_with_params(self, monkeypatch):
        monkeypatch.setattr(
            "src.cv.stereo_calibration.validate_stereo_prerequisites",
            lambda a, b: {"ready": True, "errors": [], "warnings": []},
        )
        with TestClient(app) as client:
            resp = client.post("/api/multi-cam/calibration/validate",
                               json={"cam_a": "a", "cam_b": "b"})
            data = resp.json()
            assert data["ready"] is True


# ---- Validate Score Input edge cases ----

class TestManualScoreValidation:
    def test_invalid_score_type(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": "abc", "sector": 20, "multiplier": 1, "ring": "single"
            })
            assert "error" in resp.json()

    def test_invalid_sector(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": 20, "sector": 99, "multiplier": 1, "ring": "single"
            })
            assert "error" in resp.json()

    def test_invalid_multiplier(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": 20, "sector": 20, "multiplier": 5, "ring": "single"
            })
            assert "error" in resp.json()

    def test_invalid_ring(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            resp = client.post("/api/game/manual-score", json={
                "score": 20, "sector": 20, "multiplier": 1, "ring": "invalid_ring"
            })
            assert "error" in resp.json()


# ---- New Game edge cases ----

class TestNewGameEdgeCases:
    def test_invalid_mode_defaults_to_x01(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={"mode": "invalid_mode"})
            assert resp.status_code == 200

    def test_invalid_players_defaults(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={
                "mode": "free", "players": "not_a_list"
            })
            data = resp.json()
            assert len(data["players"]) == 1

    def test_invalid_starting_score_defaults(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/new", json={
                "mode": "x01", "starting_score": -5
            })
            data = resp.json()
            assert data["players"][0]["score"] == 501

    def test_board_not_calibrated_blocks_game(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.board_calibration.is_valid.return_value = False
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/game/new", json={"mode": "x01"})
                data = resp.json()
                assert data["ok"] is False


# ---- Verify Rings with pipeline ----

class TestVerifyRings:
    def test_verify_rings_success(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.board_calibration.verify_rings.return_value = {"ok": True, "deviations": []}
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/verify-rings")
                assert resp.json()["ok"] is True

    def test_verify_rings_no_roi(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.get_roi_preview.return_value = None
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/verify-rings")
                assert resp.json()["ok"] is False


# ---- Optical Center detect success ----

class TestOpticalCenterDetect:
    def test_detect_success(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.detect_optical_center.return_value = (200.5, 199.3)
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center")
                data = resp.json()
                assert data["ok"] is True
                assert data["optical_center"] == [200.5, 199.3]

    def test_detect_failure(self):
        with _SaveRestore("pipeline"):
            pipe = _make_dummy_pipeline()
            pipe.detect_optical_center.return_value = None
            app_state["pipeline"] = pipe
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center")
                assert resp.json()["ok"] is False


# ---- Stereo Reload success ----

class TestStereoReloadSuccess:
    def test_reload_success(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi._stereo_params = {"a": {}}
            multi._board_transforms = {"a": {}}
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                data = resp.json()
                assert data["ok"] is True

    def test_reload_no_method(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock(spec=["get_pipelines", "get_camera_errors"])
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                assert resp.json()["ok"] is False

    def test_reload_exception(self):
        with _SaveRestore("multi_pipeline"):
            multi = MagicMock()
            multi.reload_stereo_params.side_effect = RuntimeError("failed")
            app_state["multi_pipeline"] = multi
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                assert resp.json()["ok"] is False


# ---- Correct hit with invalid score input ----

class TestCorrectHitValidation:
    def test_correct_hit_invalid_score(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            lock = app_state.get("pending_hits_lock")
            if lock:
                with lock:
                    app_state["pending_hits"]["val_test"] = {
                        "candidate_id": "val_test",
                        "score": 20, "sector": 20, "multiplier": 1, "ring": "single",
                        "roi_x": 0, "roi_y": 0, "quality": 50, "timestamp": 0,
                    }
            resp = client.post("/api/hits/val_test/correct", json={
                "score": "not_a_number"
            })
            assert resp.json()["ok"] is False


# ---- Duplicate camera_id in multi start ----

class TestMultiStartDuplicateId:
    def test_duplicate_camera_id(self):
        with TestClient(app) as client:
            resp = client.post("/api/multi/start", json={
                "cameras": [
                    {"camera_id": "cam_a", "src": 0},
                    {"camera_id": "cam_a", "src": 1},
                ]
            })
            assert resp.json()["ok"] is False
            assert "Doppelte" in resp.json()["error"]
