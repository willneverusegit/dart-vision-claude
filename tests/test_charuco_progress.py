import numpy as np


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
