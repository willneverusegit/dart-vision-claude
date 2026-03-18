"""Additional route tests to push routes.py coverage toward 80%."""

import threading
import numpy as np
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app, app_state


def _make_dummy_pipeline():
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
    pipe.camera = None
    pipe.get_geometry_info.return_value = {
        "center_px": [200, 200],
        "radii_px": [10, 19, 106, 116, 188, 200],
        "rotation_deg": 0,
        "lens_valid": False,
        "lens_method": None,
    }
    return pipe


def _save_and_restore(keys):
    """Context-manager-like helper returning saved values."""
    return {k: app_state.get(k) for k in keys}


def _restore(saved):
    for k, v in saved.items():
        app_state[k] = v


class TestGameUndoAndNextPlayer:
    def test_undo_throw(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
            client.post("/api/game/manual-score", json={
                "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
            })
            resp = client.post("/api/game/undo")
            assert resp.status_code == 200

    def test_next_player(self):
        with TestClient(app) as client:
            client.post("/api/game/new", json={"mode": "free", "players": ["A", "B"]})
            resp = client.post("/api/game/next-player")
            assert resp.status_code == 200

    def test_remove_darts(self):
        with TestClient(app) as client:
            resp = client.post("/api/game/remove-darts")
            assert resp.status_code == 200
            assert resp.json()["ok"] is True

    def test_new_game_board_not_calibrated(self):
        """Board calibration guard: should reject new game if board not calibrated."""
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.board_calibration.is_valid.return_value = False
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
                data = resp.json()
                assert data.get("ok") is False
        finally:
            _restore(saved)

    def test_new_game_with_event_manager(self):
        """New game broadcasts game_state via event_manager."""
        with TestClient(app) as client:
            saved = _save_and_restore(["pipeline", "event_manager"])
            app_state["pipeline"] = None
            em = MagicMock()
            app_state["event_manager"] = em
            try:
                resp = client.post("/api/game/new", json={"mode": "free", "players": ["A"]})
                assert resp.status_code == 200
                em.broadcast_sync.assert_called()
            finally:
                _restore(saved)


class TestCvParamsEndpoints:
    def test_get_cv_params_no_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/cv-params")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_get_cv_params_with_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.frame_diff_detector.get_params.return_value = {
            "settle_frames": 5, "diff_threshold": 30,
            "min_diff_area": 50, "max_diff_area": 5000,
            "min_elongation": 1.5,
        }
        pipe.motion_detector.threshold = 25
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.get("/api/cv-params")
                data = resp.json()
                assert data["ok"] is True
                assert "settle_frames" in data
                assert data["motion_threshold"] == 25
        finally:
            _restore(saved)

    def test_set_cv_params_no_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/cv-params", json={"settle_frames": 10})
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_set_cv_params_with_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.frame_diff_detector.set_params.return_value = {
            "settle_frames": 10, "diff_threshold": 30,
            "min_diff_area": 50, "max_diff_area": 5000,
            "min_elongation": 1.5,
        }
        pipe.motion_detector.threshold = 25
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/cv-params", json={
                    "settle_frames": 10, "min_elongation": 2.0,
                    "motion_threshold": 30, "unknown_key": 99,
                })
                data = resp.json()
                assert data["ok"] is True
        finally:
            _restore(saved)

    def test_set_cv_params_value_error(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.frame_diff_detector.set_params.side_effect = ValueError("bad param")
        pipe.motion_detector.threshold = 25
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/cv-params", json={"settle_frames": -1})
                data = resp.json()
                assert data["ok"] is False
                assert "bad param" in data["error"]
        finally:
            _restore(saved)


class TestDiagnosticsToggle:
    def test_toggle_no_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/diagnostics/toggle", json={"path": None})
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_toggle_with_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.frame_diff_detector.toggle_diagnostics.return_value = True
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/diagnostics/toggle", json={"path": "diagnostics/"})
                data = resp.json()
                assert data["ok"] is True
                assert data["diagnostics_enabled"] is True
        finally:
            _restore(saved)


class TestRecordingEndpoints:
    def test_start_recording_no_recorder(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["recorder"])
            app_state["recorder"] = None
            try:
                resp = client.post("/api/recording/start", json={})
                assert resp.json()["ok"] is False
            finally:
                _restore(saved)

    def test_start_recording_already_recording(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["recorder"])
            rec = MagicMock()
            rec.is_recording = True
            rec.status.return_value = {"recording": True, "frames": 100}
            app_state["recorder"] = rec
            try:
                resp = client.post("/api/recording/start", json={})
                assert resp.json()["ok"] is False
            finally:
                _restore(saved)

    def test_start_recording_success(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["recorder", "pipeline"])
            rec = MagicMock()
            rec.is_recording = False
            rec.start.return_value = "testvids/test.mp4"
            rec.status.return_value = {"recording": True, "frames": 0}
            app_state["recorder"] = rec
            app_state["pipeline"] = _make_dummy_pipeline()
            try:
                resp = client.post("/api/recording/start", json={"fps": 25.0})
                data = resp.json()
                assert data["ok"] is True
                assert data["output_path"] == "testvids/test.mp4"
            finally:
                _restore(saved)

    def test_stop_recording_no_recorder(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["recorder"])
            app_state["recorder"] = None
            try:
                resp = client.post("/api/recording/stop")
                assert resp.json()["ok"] is False
            finally:
                _restore(saved)

    def test_stop_recording_success(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["recorder"])
            rec = MagicMock()
            rec.stop.return_value = {"stopped": True, "frames": 100}
            app_state["recorder"] = rec
            try:
                resp = client.post("/api/recording/stop")
                assert resp.json()["ok"] is True
            finally:
                _restore(saved)

    def test_recording_status_no_recorder(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["recorder"])
            app_state["recorder"] = None
            try:
                resp = client.get("/api/recording/status")
                assert resp.json()["recording"] is False
            finally:
                _restore(saved)

    def test_recording_status_with_recorder(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["recorder"])
            rec = MagicMock()
            rec.status.return_value = {"recording": True, "frames": 50}
            app_state["recorder"] = rec
            try:
                resp = client.get("/api/recording/status")
                assert resp.json()["recording"] is True
            finally:
                _restore(saved)


class TestLensInfo:
    def test_lens_info_no_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/lens/info")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_lens_info_with_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.camera_calibration.get_config.return_value = {
            "lens_valid": True, "lens_method": "charuco",
            "lens_image_size": [640, 480], "lens_reprojection_error": 0.5,
        }
        board_spec = MagicMock()
        board_spec.to_api_payload.return_value = {"squares_x": 5, "squares_y": 7}
        pipe.camera_calibration.get_charuco_board_spec.return_value = board_spec
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.get("/api/calibration/lens/info")
                data = resp.json()
                assert data["ok"] is True
                assert data["valid"] is True
        finally:
            _restore(saved)


class TestVerifyRingsWithROI:
    def test_verify_rings_no_roi(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.get_roi_preview.return_value = None
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/verify-rings")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_verify_rings_success(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.board_calibration.verify_rings.return_value = {"ok": True, "deviations": []}
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/verify-rings")
                assert resp.json()["ok"] is True
        finally:
            _restore(saved)


class TestOpticalCenterDetect:
    def test_detect_optical_center_success(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.detect_optical_center.return_value = (200.5, 199.3)
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center")
                data = resp.json()
                assert data["ok"] is True
                assert data["optical_center"] == [200.5, 199.3]
        finally:
            _restore(saved)

    def test_detect_optical_center_fails(self):
        saved = _save_and_restore(["pipeline"])
        pipe = _make_dummy_pipeline()
        pipe.detect_optical_center.return_value = None
        app_state["pipeline"] = pipe
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/optical-center")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)


class TestTelemetryHistory:
    def test_telemetry_history_not_initialized(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["telemetry"])
            app_state["telemetry"] = None
            try:
                resp = client.get("/api/telemetry/history")
                assert resp.json()["ok"] is False
            finally:
                _restore(saved)

    def test_telemetry_history_success(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["telemetry"])
            tel = MagicMock()
            tel.get_history.return_value = [{"fps": 30.0}]
            tel.get_alerts.return_value = []
            tel.get_summary.return_value = {"avg_fps": 30.0}
            app_state["telemetry"] = tel
            try:
                resp = client.get("/api/telemetry/history?last_n=10")
                data = resp.json()
                assert data["ok"] is True
                assert len(data["history"]) == 1
            finally:
                _restore(saved)

    def test_telemetry_history_clamped(self):
        with TestClient(app) as client:
            saved = _save_and_restore(["telemetry"])
            tel = MagicMock()
            tel.get_history.return_value = []
            tel.get_alerts.return_value = []
            tel.get_summary.return_value = {}
            app_state["telemetry"] = tel
            try:
                resp = client.get("/api/telemetry/history?last_n=999")
                assert resp.json()["ok"] is True
                tel.get_history.assert_called_with(last_n=300)
            finally:
                _restore(saved)


class TestTelemetryStereo:
    def test_stereo_no_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/stereo")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_stereo_no_method(self):
        saved = _save_and_restore(["multi_pipeline"])
        multi = MagicMock(spec=[])  # no get_triangulation_telemetry
        app_state["multi_pipeline"] = multi
        try:
            with TestClient(app) as client:
                resp = client.get("/api/telemetry/stereo")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)


class TestMultiCamErrorsAndTelemetry:
    def test_multi_cam_errors_no_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/errors")
                assert resp.json()["errors"] == {}
        finally:
            _restore(saved)

    def test_multi_cam_telemetry_no_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                assert resp.json()["active"] is False
        finally:
            _restore(saved)

    def test_multi_cam_telemetry_with_governor(self):
        saved = _save_and_restore(["multi_pipeline"])
        multi = MagicMock()
        multi.get_triangulation_telemetry.return_value = {"pairs": 1}
        multi.get_fusion_config.return_value = {"method": "voting"}
        multi.get_governor_stats.return_value = {"fps_limit": 30}
        app_state["multi_pipeline"] = multi
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi-cam/telemetry")
                data = resp.json()
                assert data["active"] is True
                assert "governors" in data
        finally:
            _restore(saved)


class TestMultiEndpointsMisc:
    def test_multi_errors_endpoint(self):
        saved = _save_and_restore(["multi_pipeline"])
        multi = MagicMock()
        multi.get_camera_errors.return_value = {"cam_a": "timeout"}
        app_state["multi_pipeline"] = multi
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/errors")
                assert resp.json()["ok"] is True
        finally:
            _restore(saved)

    def test_multi_errors_no_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/errors")
                assert resp.json()["ok"] is True
        finally:
            _restore(saved)

    def test_multi_intrinsics_status_no_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/intrinsics-status")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_multi_camera_health_no_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/camera-health")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_multi_camera_reconnect_no_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/multi/camera/cam_a/reconnect")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_multi_degraded_no_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/degraded")
                data = resp.json()
                assert data["ok"] is True
                assert data["degraded"] == []
        finally:
            _restore(saved)

    def test_multi_degraded_with_multi(self):
        saved = _save_and_restore(["multi_pipeline"])
        multi = MagicMock()
        multi.get_degraded_cameras.return_value = ["cam_b"]
        app_state["multi_pipeline"] = multi
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/degraded")
                assert resp.json()["degraded"] == ["cam_b"]
        finally:
            _restore(saved)

    def test_multi_last_config(self):
        with TestClient(app) as client:
            resp = client.get("/api/multi/last-config")
            data = resp.json()
            assert data["ok"] is True
            assert "cameras" in data

    def test_multi_readiness_not_running(self):
        saved = _save_and_restore(["multi_pipeline"])
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/readiness")
                data = resp.json()
                assert data["ok"] is True
                assert data["running"] is False
        finally:
            _restore(saved)

    def test_multi_start_duplicate_camera_id(self):
        with TestClient(app) as client:
            resp = client.post("/api/multi/start", json={
                "cameras": [
                    {"camera_id": "a", "src": 0},
                    {"camera_id": "a", "src": 1},
                ]
            })
            data = resp.json()
            assert data["ok"] is False
            assert "Doppelte" in data["error"]


class TestCameraHealth:
    def test_camera_health_no_cameras(self):
        saved = _save_and_restore(["pipeline", "multi_pipeline"])
        app_state["pipeline"] = None
        app_state["multi_pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.get("/api/camera/health")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)


class TestManualCalibration:
    def test_manual_calibration_no_pipeline(self):
        saved = _save_and_restore(["pipeline"])
        app_state["pipeline"] = None
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/manual",
                                   json={"points": [[0,0],[1,0],[1,1],[0,1]]})
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)


class TestStereoReloadWithMethod:
    def test_stereo_reload_no_method(self):
        saved = _save_and_restore(["multi_pipeline"])
        multi = MagicMock(spec=[])  # no reload_stereo_params
        app_state["multi_pipeline"] = multi
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_stereo_reload_exception(self):
        saved = _save_and_restore(["multi_pipeline"])
        multi = MagicMock()
        multi.reload_stereo_params.side_effect = RuntimeError("fail")
        app_state["multi_pipeline"] = multi
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                assert resp.json()["ok"] is False
        finally:
            _restore(saved)

    def test_stereo_reload_success(self):
        saved = _save_and_restore(["multi_pipeline"])
        multi = MagicMock()
        multi._stereo_params = {"a": 1}
        multi._board_transforms = {"b": 2, "c": 3}
        app_state["multi_pipeline"] = multi
        try:
            with TestClient(app) as client:
                resp = client.post("/api/calibration/stereo/reload")
                data = resp.json()
                assert data["ok"] is True
                assert data["stereo_pairs"] == 1
                assert data["board_transforms"] == 2
        finally:
            _restore(saved)
