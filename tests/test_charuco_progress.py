import pytest
import numpy as np
from starlette.testclient import TestClient
from fastapi import FastAPI

from src.web.routes import setup_routes
from src.cv.stereo_calibration import DEFAULT_CHARUCO_BOARD_SPEC


def _sharp_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[::16, :] = 255
    frame[:, ::16] = 255
    return frame


def _corners(offset_x: float = 0.0, offset_y: float = 0.0):
    return np.array(
        [
            [100 + offset_x, 100 + offset_y],
            [200 + offset_x, 100 + offset_y],
            [300 + offset_x, 120 + offset_y],
            [120 + offset_x, 220 + offset_y],
            [220 + offset_x, 240 + offset_y],
            [320 + offset_x, 260 + offset_y],
        ],
        dtype=np.float32,
    )


@pytest.fixture
def app_state():
    from src.game.engine import GameEngine
    import threading
    return {
        "game_engine": GameEngine(),
        "event_manager": None,
        "pipeline": None,
        "pending_hits": {},
        "pending_hits_lock": threading.Lock(),
    }


@pytest.fixture
def client(app_state):
    router = setup_routes(app_state)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestCharucoFrameCollector:
    def test_initial_state(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=15)
        assert c.frames_captured == 0
        assert c.ready_to_calibrate is False

    def test_add_diverse_frame(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=15)
        corners = _corners()
        accepted = c.add_frame_if_diverse(
            corners,
            _sharp_frame(),
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        assert accepted is True
        assert c.frames_captured == 1

    def test_reject_duplicate_frame(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=2)
        corners = _corners()
        frame = _sharp_frame()
        c.add_frame_if_diverse(
            corners,
            frame,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        accepted = c.add_frame_if_diverse(
            corners,
            frame,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        assert accepted is False
        assert c.frames_captured == 1

    def test_ready_when_enough_frames(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=2)
        f = _sharp_frame()
        c.add_frame_if_diverse(
            _corners(),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        c.add_frame_if_diverse(
            _corners(180, 120),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        assert c.ready_to_calibrate is True

    def test_get_tips_returns_list(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=15)
        f = _sharp_frame()
        for i in range(3):
            corners = _corners(i * 60, 0)
            c.add_frame_if_diverse(
                corners,
                f,
                board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
                markers_found=4,
                charuco_corners_found=6,
                interpolation_ok=True,
            )
        tips = c.get_tips(image_shape=(480, 640))
        assert isinstance(tips, list)

    def test_reset_clears_state(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=2)
        f = _sharp_frame()
        c.add_frame_if_diverse(
            _corners(),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        assert c.frames_captured == 1
        c.reset()
        assert c.frames_captured == 0

    def test_get_frames_returns_copies(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=15)
        f = _sharp_frame()
        c.add_frame_if_diverse(
            _corners(),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        frames = c.get_frames()
        assert len(frames) == 1

    def test_rejects_raw_markers_without_interpolation(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=2)
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        accepted = c.add_frame_if_diverse(
            np.array([[100, 100], [200, 100]], dtype=np.float32),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=12,
            charuco_corners_found=0,
            interpolation_ok=False,
            warning="Rohmarker erkannt, aber kein passendes ChArUco-Layout interpoliert.",
        )
        assert accepted is False
        assert c.frames_captured == 0
        assert c.last_markers_found == 12
        assert c.last_charuco_corners_found == 0


class TestCharucoProgressEndpoint:
    def test_charuco_progress_endpoint_no_collector(self, client):
        resp = client.get("/api/calibration/charuco-progress/cam_left")
        assert resp.status_code == 200
        data = resp.json()
        assert "frames_captured" in data
        assert "frames_needed" in data
        assert "tips" in data
        assert "ready_to_calibrate" in data
        assert data["frames_captured"] == 0
        assert data["ready_to_calibrate"] is False
        assert "board_visible" in data
        assert "corners_found" in data
        assert data["board_visible"] is False
        assert data["corners_found"] == 0
        assert data["markers_found"] == 0
        assert data["charuco_corners_found"] == 0
        assert data["interpolation_ok"] is False
        assert data["usable_frames"] == 0
        assert data["mode"] is None
        assert data["capture_mode"] is None
        assert data["sharpness"] == 0.0
        assert data["reject_reason"] is None

    def test_charuco_progress_endpoint_with_collector(self, client, app_state):
        from src.cv.camera_calibration import CharucoFrameCollector
        collector = CharucoFrameCollector(frames_needed=15)
        f = _sharp_frame()
        collector.add_frame_if_diverse(
            _corners(),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        app_state.setdefault("charuco_collectors", {})["cam_right"] = collector

        resp = client.get("/api/calibration/charuco-progress/cam_right")
        assert resp.status_code == 200
        data = resp.json()
        assert data["frames_captured"] == 1
        assert data["usable_frames"] == 1
        assert data["frames_needed"] == 15
        assert isinstance(data["tips"], list)
        assert data["ready_to_calibrate"] is False
        assert "board_visible" in data
        assert "corners_found" in data
        assert isinstance(data["board_visible"], bool)
        assert isinstance(data["corners_found"], int)
        assert data["resolved_preset"] == DEFAULT_CHARUCO_BOARD_SPEC.preset_name
        assert data["mode"] == "handheld"
        assert data["capture_mode"] == "auto"
        assert data["sharpness"] > 0

    def test_charuco_progress_preserves_raw_marker_warning(self, client, app_state):
        from src.cv.camera_calibration import CharucoFrameCollector

        collector = CharucoFrameCollector(frames_needed=15)
        collector.update_detection(
            board_spec=None,
            markers_found=14,
            charuco_corners_found=0,
            interpolation_ok=False,
            warning="Rohmarker erkannt, aber kein passendes ChArUco-Layout interpoliert.",
        )
        app_state.setdefault("charuco_collectors", {})["cam_left"] = collector

        resp = client.get("/api/calibration/charuco-progress/cam_left")
        data = resp.json()
        assert data["board_visible"] is True
        assert data["markers_found"] == 14
        assert data["charuco_corners_found"] == 0
        assert data["interpolation_ok"] is False
        assert "interpoliert" in data["warning"]


class TestCharucoAutoCapture:
    def test_collector_integration_with_feed(self):
        """Collector should accumulate diverse frames."""
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=3)
        f = _sharp_frame()
        for i in range(3):
            corners = _corners(i * 140, 0)
            c.add_frame_if_diverse(
                corners,
                f,
                board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
                markers_found=4,
                charuco_corners_found=6,
                interpolation_ok=True,
            )
        assert c.frames_captured == 3
        assert c.ready_to_calibrate is True

    def test_charuco_start_endpoint(self, client, app_state):
        class DummyCameraCalibration:
            def get_charuco_board_candidates(self, **_kwargs):
                return [DEFAULT_CHARUCO_BOARD_SPEC]

        class DummyPipeline:
            camera = object()
            camera_calibration = DummyCameraCalibration()

        app_state["pipeline"] = DummyPipeline()
        resp = client.post("/api/calibration/charuco-start/default", json={"preset": "auto"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["frames_needed"] == 15
        assert data["mode"] == "handheld"
        assert data["capture_mode"] == "auto"

    def test_manual_capture_endpoint_records_frame(self, client, app_state, monkeypatch):
        class DummyCameraCalibration:
            def get_charuco_board_candidates(self, **_kwargs):
                return [DEFAULT_CHARUCO_BOARD_SPEC]

        class DummyPipeline:
            camera = object()
            camera_calibration = DummyCameraCalibration()

            def get_latest_raw_frame(self):
                return _sharp_frame()

        app_state["pipeline"] = DummyPipeline()
        start = client.post(
            "/api/calibration/charuco-start/default",
            json={"preset": "auto", "mode": "stationary"},
        )
        assert start.status_code == 200

        monkeypatch.setattr(
            "src.cv.stereo_calibration.detect_charuco_board",
            lambda _frame, **_kwargs: type(
                "Detection",
                (),
                {
                    "board_spec": DEFAULT_CHARUCO_BOARD_SPEC,
                    "charuco_corners": _corners().reshape(-1, 1, 2),
                    "charuco_ids": np.arange(6, dtype=np.int32).reshape(-1, 1),
                    "markers_found": 4,
                    "charuco_corners_found": 6,
                    "interpolation_ok": True,
                    "warning": None,
                },
            )(),
        )

        resp = client.post("/api/calibration/capture-frame/default")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["accepted"] is True
        assert data["mode"] == "stationary"
        assert data["capture_mode"] == "manual"
        assert data["frames_captured"] == 1

    def test_charuco_start_resets_existing_collector(self, client, app_state):
        from src.cv.camera_calibration import CharucoFrameCollector
        # Pre-populate a collector with some frames
        collector = CharucoFrameCollector(frames_needed=15)
        f = _sharp_frame()
        collector.add_frame_if_diverse(
            _corners(),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        app_state.setdefault("charuco_collectors", {})["default"] = collector

        class DummyCameraCalibration:
            def get_charuco_board_candidates(self, **_kwargs):
                return [DEFAULT_CHARUCO_BOARD_SPEC]

        class DummyPipeline:
            camera = object()
            camera_calibration = DummyCameraCalibration()

        app_state["pipeline"] = DummyPipeline()

        # Start should reset it
        resp = client.post(
            "/api/calibration/charuco-start/default",
            json={"preset": "auto", "mode": "stationary"},
        )
        assert resp.status_code == 200
        # The new collector in app_state should be fresh
        new_collector = app_state["charuco_collectors"]["default"]
        assert new_collector.frames_captured == 0
        assert new_collector.capture_mode == "manual"


class TestCharucoOverlay:
    """Unit tests for frame-count overlay rendering in MJPEG feed."""

    def test_puttext_in_progress(self):
        """Overlay text for in-progress collection renders without error."""
        import cv2
        from src.cv.camera_calibration import CharucoFrameCollector

        collector = CharucoFrameCollector(frames_needed=15)
        f = _sharp_frame()
        collector.add_frame_if_diverse(
            _corners(),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        progress_text = f"{collector.usable_frames}/{collector.frames_needed} Frames"
        assert collector.ready_to_calibrate is False
        color = (0, 255, 136)
        frame = frame.copy()
        cv2.putText(frame, progress_text, (10, frame.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
        assert frame is not None
        assert progress_text == "1/15 Frames"

    def test_puttext_ready_to_calibrate(self):
        """Overlay shows 'Bereit!' suffix and green color when ready."""
        import cv2
        from src.cv.camera_calibration import CharucoFrameCollector

        collector = CharucoFrameCollector(frames_needed=2)
        f = _sharp_frame()
        collector.add_frame_if_diverse(
            _corners(),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        collector.add_frame_if_diverse(
            _corners(180, 120),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )

        assert collector.ready_to_calibrate is True
        progress_text = f"{collector.usable_frames}/{collector.frames_needed} Frames"
        progress_text += " - Bereit!"
        color = (0, 255, 0)

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame = frame.copy()
        cv2.putText(frame, progress_text, (10, frame.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
        assert frame is not None
        assert "Bereit!" in progress_text

    def test_no_overlay_without_collector(self):
        """No overlay is applied when no collector is present."""
        import cv2

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        collectors = {}
        collector = collectors.get("cam_left")
        assert collector is None
        # Frame should remain unchanged (no putText called)
        original = frame.copy()
        assert np.array_equal(frame, original)
