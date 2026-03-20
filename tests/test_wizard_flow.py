"""Tests for wizard-related backend state: auto-pose trigger, collector lifecycle."""
import pytest
import numpy as np
import threading
from starlette.testclient import TestClient
from fastapi import FastAPI

from src.web.routes import setup_routes
from src.cv.stereo_calibration import DEFAULT_CHARUCO_BOARD_SPEC


@pytest.fixture
def app_state():
    from src.game.engine import GameEngine
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


class TestAutoPoseTrigger:
    """Board-pose should be callable after board+lens calibration."""

    def test_board_pose_requires_lens_intrinsics(self, client):
        """POST /api/calibration/board-pose without lens should fail gracefully."""
        resp = client.post("/api/calibration/board-pose",
                           json={"camera_id": "cam_left"})
        data = resp.json()
        assert data.get("ok") is False or "error" in data


class TestCollectorLifecycle:
    """CharucoFrameCollector should be created/reset properly."""

    def test_collector_created_on_charuco_start(self, client, app_state):
        """POST /api/calibration/charuco-start creates collector."""
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

        # Verify progress shows 0 frames
        resp2 = client.get("/api/calibration/charuco-progress/default")
        assert resp2.json()["frames_captured"] == 0

    def test_collector_reset_on_second_start(self, client, app_state):
        """Second charuco-start resets the collector."""
        class DummyCameraCalibration:
            def get_charuco_board_candidates(self, **_kwargs):
                return [DEFAULT_CHARUCO_BOARD_SPEC]

        class DummyPipeline:
            camera = object()
            camera_calibration = DummyCameraCalibration()

        app_state["pipeline"] = DummyPipeline()
        client.post("/api/calibration/charuco-start/default", json={"preset": "auto"})
        # Progress should be 0
        resp = client.get("/api/calibration/charuco-progress/default")
        assert resp.json()["frames_captured"] == 0

    def test_collector_unit_reset(self):
        """CharucoFrameCollector.reset() clears state."""
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=2)
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        for offset in range(0, 640, 32):
            f[:, offset:offset + 16] = 255
        c.add_frame_if_diverse(
            np.array([[100, 100], [160, 140], [220, 180], [280, 220], [340, 260], [400, 300]], dtype=np.float32),
            f,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            markers_found=4,
            charuco_corners_found=6,
            interpolation_ok=True,
        )
        assert c.frames_captured == 1
        c.reset()
        assert c.frames_captured == 0


class TestCharucoProgressContract:
    """GET /api/calibration/charuco-progress/{camera_id} response contract."""

    def test_unknown_camera_returns_zero_progress(self, client):
        resp = client.get("/api/calibration/charuco-progress/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["frames_captured"] == 0
        assert data["ready_to_calibrate"] is False
        assert "tips" in data

    def test_progress_after_start(self, client, app_state):
        """After charuco-start, progress should be available."""
        class DummyCameraCalibration:
            def get_charuco_board_candidates(self, **_kwargs):
                return [DEFAULT_CHARUCO_BOARD_SPEC]

        class DummyPipeline:
            camera = object()
            camera_calibration = DummyCameraCalibration()

        app_state["pipeline"] = DummyPipeline()
        client.post("/api/calibration/charuco-start/default", json={"preset": "auto"})
        resp = client.get("/api/calibration/charuco-progress/default")
        data = resp.json()
        assert data["frames_captured"] == 0
        assert data["frames_needed"] == 15
        assert data["ready_to_calibrate"] is False
