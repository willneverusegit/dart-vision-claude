"""Tests for camera reconnect logic, health tracking, and state transitions (P2)."""

import time
import threading
import numpy as np
from unittest.mock import MagicMock, patch, call

from src.cv.capture import ThreadedCamera, CameraState


def _make_mock_cap(opened=True, read_ok=True):
    """Create a mock VideoCapture that returns configurable frames."""
    mock = MagicMock()
    mock.isOpened.return_value = opened
    mock.get.side_effect = lambda prop: {3: 640.0, 4: 480.0, 5: 30.0}.get(prop, 0.0)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock.read.return_value = (read_ok, frame if read_ok else None)
    return mock


class TestCameraState:
    """Test CameraState enum values."""

    def test_state_values(self):
        assert CameraState.CONNECTED.value == "connected"
        assert CameraState.RECONNECTING.value == "reconnecting"
        assert CameraState.DISCONNECTED.value == "disconnected"


class TestHealthTracking:
    """Test health status properties and get_health() method."""

    @patch("cv2.VideoCapture")
    def test_initial_state_connected(self, MockCap):
        MockCap.return_value = _make_mock_cap()
        cam = ThreadedCamera(src=0)
        assert cam.state == CameraState.CONNECTED
        assert cam._reconnect_attempts == 0
        assert cam._total_reconnects == 0

    @patch("cv2.VideoCapture")
    def test_get_health_dict(self, MockCap):
        MockCap.return_value = _make_mock_cap()
        cam = ThreadedCamera(src=0)
        health = cam.get_health()
        assert health["state"] == "connected"
        assert health["reconnect_attempts"] == 0
        assert health["total_reconnects"] == 0
        assert health["is_running"] is False
        assert health["src"] == 0
        assert "seconds_since_last_frame" in health

    @patch("cv2.VideoCapture")
    def test_seconds_since_last_frame(self, MockCap):
        MockCap.return_value = _make_mock_cap()
        cam = ThreadedCamera(src=0)
        # Initially should be very small (just created)
        assert cam.seconds_since_last_frame < 1.0

    @patch("cv2.VideoCapture")
    def test_state_change_callback(self, MockCap):
        MockCap.return_value = _make_mock_cap()
        cam = ThreadedCamera(src=0)
        changes = []
        cam.on_state_change(lambda src, old, new: changes.append((src, old, new)))

        # Simulate state change
        cam._set_state(CameraState.RECONNECTING)
        assert len(changes) == 1
        assert changes[0] == (0, CameraState.CONNECTED, CameraState.RECONNECTING)

    @patch("cv2.VideoCapture")
    def test_state_change_same_state_no_callback(self, MockCap):
        MockCap.return_value = _make_mock_cap()
        cam = ThreadedCamera(src=0)
        changes = []
        cam.on_state_change(lambda src, old, new: changes.append(1))

        cam._set_state(CameraState.CONNECTED)  # same as initial
        assert len(changes) == 0

    @patch("cv2.VideoCapture")
    def test_callback_error_doesnt_crash(self, MockCap):
        MockCap.return_value = _make_mock_cap()
        cam = ThreadedCamera(src=0)

        def bad_callback(src, old, new):
            raise ValueError("boom")

        cam.on_state_change(bad_callback)
        # Should not raise
        cam._set_state(CameraState.RECONNECTING)
        assert cam.state == CameraState.RECONNECTING


class TestReconnectLoop:
    """Test the capture loop reconnect behavior."""

    @patch("cv2.VideoCapture")
    @patch("time.sleep")
    def test_reconnect_on_frame_failure(self, mock_sleep, MockCap):
        """When frame read fails, camera should enter RECONNECTING state and retry."""
        mock_cap = _make_mock_cap(read_ok=False)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        cam._running = True

        # Simulate: 3 failed reads, then stop
        call_count = [0]
        original_read = mock_cap.read

        def counting_read():
            call_count[0] += 1
            if call_count[0] >= 3:
                cam._running = False
            return (False, None)

        mock_cap.read.side_effect = lambda: counting_read()

        # New VideoCapture for reconnect also fails
        mock_cap_new = _make_mock_cap(opened=True, read_ok=False)
        mock_cap_new.read.side_effect = lambda: counting_read()
        MockCap.return_value = mock_cap_new

        cam._capture_loop()

        assert cam._reconnect_attempts > 0
        assert cam.state in (CameraState.RECONNECTING, CameraState.DISCONNECTED)

    @patch("cv2.VideoCapture")
    @patch("time.sleep")
    def test_reconnect_then_recover(self, mock_sleep, MockCap):
        """After failed reads, successful read should restore CONNECTED state."""
        mock_cap = _make_mock_cap()
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        cam._running = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        call_count = [0]

        def read_sequence():
            call_count[0] += 1
            if call_count[0] <= 2:
                return (False, None)  # First 2 reads fail
            if call_count[0] == 3:
                return (True, frame)  # 3rd read succeeds
            cam._running = False
            return (True, frame)

        mock_cap.read.side_effect = lambda: read_sequence()

        # Reconnect returns same mock
        MockCap.return_value = mock_cap

        cam._capture_loop()

        assert cam.state == CameraState.CONNECTED
        assert cam._total_reconnects == 1
        assert cam._reconnect_attempts == 0

    @patch("cv2.VideoCapture")
    @patch("time.sleep")
    def test_disconnected_when_reopen_fails(self, mock_sleep, MockCap):
        """If VideoCapture cannot reopen, state should go to DISCONNECTED."""
        mock_cap = _make_mock_cap(read_ok=False)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        cam._running = True

        call_count = [0]

        def counting_read():
            call_count[0] += 1
            if call_count[0] >= 2:
                cam._running = False
            return (False, None)

        mock_cap.read.side_effect = lambda: counting_read()

        # Reconnect: new cap cannot open
        mock_cap_bad = MagicMock()
        mock_cap_bad.isOpened.return_value = False
        mock_cap_bad.read.side_effect = lambda: counting_read()
        MockCap.return_value = mock_cap_bad

        cam._capture_loop()

        assert cam.state == CameraState.DISCONNECTED

    @patch("cv2.VideoCapture")
    @patch("time.sleep")
    def test_exponential_backoff_delay(self, mock_sleep, MockCap):
        """Reconnect delays should increase exponentially."""
        mock_cap = _make_mock_cap(read_ok=False)
        MockCap.return_value = mock_cap

        cam = ThreadedCamera(src=0)
        cam._running = True

        call_count = [0]

        def counting_read():
            call_count[0] += 1
            if call_count[0] >= 4:
                cam._running = False
            return (False, None)

        mock_cap.read.side_effect = lambda: counting_read()

        cam._capture_loop()

        # Check sleep was called with increasing delays
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert len(delays) >= 2
        assert delays[0] == 1.0
        assert delays[1] == 2.0


class TestHealthAPI:
    """Test the /api/camera/health endpoint integration."""

    @patch("cv2.VideoCapture")
    def test_health_after_state_changes(self, MockCap):
        MockCap.return_value = _make_mock_cap()
        cam = ThreadedCamera(src=0)

        # Simulate reconnecting
        cam._set_state(CameraState.RECONNECTING)
        cam._reconnect_attempts = 3

        health = cam.get_health()
        assert health["state"] == "reconnecting"
        assert health["reconnect_attempts"] == 3

    @patch("cv2.VideoCapture")
    def test_multiple_state_change_callbacks(self, MockCap):
        MockCap.return_value = _make_mock_cap()
        cam = ThreadedCamera(src=0)

        cb1_calls = []
        cb2_calls = []
        cam.on_state_change(lambda s, o, n: cb1_calls.append(n))
        cam.on_state_change(lambda s, o, n: cb2_calls.append(n))

        cam._set_state(CameraState.DISCONNECTED)
        assert len(cb1_calls) == 1
        assert len(cb2_calls) == 1
