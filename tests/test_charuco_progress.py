import pytest
import numpy as np
from starlette.testclient import TestClient
from fastapi import FastAPI

from src.web.routes import setup_routes


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
        corners = np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32)
        accepted = c.add_frame_if_diverse(corners, np.zeros((480, 640, 3), dtype=np.uint8))
        assert accepted is True
        assert c.frames_captured == 1

    def test_reject_duplicate_frame(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=2)
        corners = np.array([[100, 100], [200, 100], [200, 200], [100, 200]], dtype=np.float32)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        c.add_frame_if_diverse(corners, frame)
        accepted = c.add_frame_if_diverse(corners, frame)
        assert accepted is False
        assert c.frames_captured == 1

    def test_ready_when_enough_frames(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=2)
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        c.add_frame_if_diverse(np.array([[100, 100], [200, 100]], dtype=np.float32), f)
        c.add_frame_if_diverse(np.array([[300, 300], [400, 300]], dtype=np.float32), f)
        assert c.ready_to_calibrate is True

    def test_get_tips_returns_list(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=15)
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(3):
            corners = np.array([[100 + i, 100], [200 + i, 100]], dtype=np.float32)
            c.add_frame_if_diverse(corners, f)
        tips = c.get_tips(image_shape=(480, 640))
        assert isinstance(tips, list)

    def test_reset_clears_state(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=2)
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        c.add_frame_if_diverse(np.array([[100, 100]], dtype=np.float32), f)
        assert c.frames_captured == 1
        c.reset()
        assert c.frames_captured == 0

    def test_get_frames_returns_copies(self):
        from src.cv.camera_calibration import CharucoFrameCollector
        c = CharucoFrameCollector(frames_needed=15)
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        c.add_frame_if_diverse(np.array([[100, 100]], dtype=np.float32), f)
        frames = c.get_frames()
        assert len(frames) == 1


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

    def test_charuco_progress_endpoint_with_collector(self, client, app_state):
        from src.cv.camera_calibration import CharucoFrameCollector
        collector = CharucoFrameCollector(frames_needed=15)
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        collector.add_frame_if_diverse(np.array([[100, 100], [200, 100]], dtype=np.float32), f)
        app_state.setdefault("charuco_collectors", {})["cam_right"] = collector

        resp = client.get("/api/calibration/charuco-progress/cam_right")
        assert resp.status_code == 200
        data = resp.json()
        assert data["frames_captured"] == 1
        assert data["frames_needed"] == 15
        assert isinstance(data["tips"], list)
        assert data["ready_to_calibrate"] is False
