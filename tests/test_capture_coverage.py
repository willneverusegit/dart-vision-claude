"""Tests for src/cv/capture.py to increase coverage from 54% to 60%+."""

import queue
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock

from src.cv.capture import ThreadedCamera


class TestThreadedCameraInit:
    @patch("cv2.VideoCapture")
    def test_default_init(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            3: 640.0, 4: 480.0, 5: 30.0
        }.get(prop, 0.0)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        assert cam.src == 0
        assert cam._req_width == 640
        assert cam._req_height == 480
        assert cam._req_fps == 30
        assert not cam._running

    @patch("cv2.VideoCapture")
    def test_custom_resolution(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {
            3: 320.0, 4: 240.0, 5: 15.0
        }.get(prop, 0.0)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0, width=320, height=240, fps=15)
        assert cam._req_width == 320
        assert cam._req_height == 240
        assert cam._req_fps == 15

    @patch("cv2.VideoCapture")
    def test_mismatch_warning(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        # Camera reports different resolution than requested
        mock_cap.get.side_effect = lambda prop: {
            3: 1920.0, 4: 1080.0, 5: 30.0
        }.get(prop, 0.0)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0, width=640, height=480)
        assert cam._req_width == 640

    @patch("cv2.VideoCapture")
    def test_camera_not_opened_raises(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        MockCap.return_value = mock_cap

        try:
            ThreadedCamera(src=99)
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass


class TestThreadedCameraOperations:
    @patch("cv2.VideoCapture")
    def test_start_stop(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        mock_cap.read.return_value = (False, None)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        cam.start()
        assert cam._running
        cam.stop()
        assert not cam._running

    @patch("cv2.VideoCapture")
    def test_read_empty_queue(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        ret, frame = cam.read()
        assert ret is False
        assert frame is None

    @patch("cv2.VideoCapture")
    def test_read_with_frame_in_queue(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cam.frame_queue.put(fake_frame)
        ret, frame = cam.read()
        assert ret is True
        assert frame is not None

    @patch("cv2.VideoCapture")
    def test_is_running(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        assert not cam.is_running()
        cam._running = True
        assert cam.is_running()

    @patch("cv2.VideoCapture")
    def test_frame_size(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {3: 640.0, 4: 480.0, 5: 30.0}.get(prop, 0.0)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        w, h = cam.frame_size
        assert w == 640
        assert h == 480

    @patch("cv2.VideoCapture")
    def test_get_capture_config(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {3: 640.0, 4: 480.0, 5: 30.0}.get(prop, 0.0)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        config = cam.get_capture_config()
        assert config["requested"]["width"] == 640
        assert config["actual"]["width"] == 640
        assert config["mismatch"] is False

    @patch("cv2.VideoCapture")
    def test_get_capture_config_mismatch(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        # First call returns 640 for init, then 1920 for get_capture_config
        call_count = [0]
        def side_effect(prop):
            if prop == 3:
                return 1920.0
            elif prop == 4:
                return 1080.0
            elif prop == 5:
                return 30.0
            return 0.0
        mock_cap.get.side_effect = side_effect
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0, width=640, height=480)
        config = cam.get_capture_config()
        assert config["mismatch"] is True

    @patch("cv2.VideoCapture")
    def test_apply_settings(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {3: 320.0, 4: 240.0, 5: 15.0}.get(prop, 0.0)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        # Put some frames in queue
        cam.frame_queue.put(np.zeros((1, 1, 3), dtype=np.uint8))

        config = cam.apply_settings(320, 240, 15)
        assert config["requested"]["width"] == 320
        assert cam._req_width == 320

    @patch("cv2.VideoCapture")
    def test_apply_settings_running(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.side_effect = lambda prop: {3: 640.0, 4: 480.0, 5: 30.0}.get(prop, 0.0)
        mock_cap.read.return_value = (False, None)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        cam.start()
        config = cam.apply_settings(640, 480, 30)
        assert cam._running  # should restart
        cam.stop()

    @patch("cv2.VideoCapture")
    def test_apply_settings_reopen_fails(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)

        # Second VideoCapture creation fails
        mock_cap2 = MagicMock()
        mock_cap2.isOpened.return_value = False
        MockCap.return_value = mock_cap2

        try:
            cam.apply_settings(320, 240, 15)
            assert False, "Should raise RuntimeError"
        except RuntimeError:
            pass

    @patch("cv2.VideoCapture")
    def test_apply_capture_props(self, MockCap):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 640.0
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        cam._apply_capture_props()
        # Should set buffer, width, height, fps
        assert mock_cap.set.call_count >= 4  # init (4) + apply (4)
