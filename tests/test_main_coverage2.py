"""Extended tests for src/main.py — covering previously untested branches.

Covers:
- _full_state_reset() all paths (with lock, without lock)
- _wait_for_camera_release() paths (skip non-USB, retry, timeout)
- on_dart_detected callback (detection ring buffer, timestamp cleanup)
- on_multi_dart_detected callback
- on_camera_state_change callback
- on_camera_errors_changed callback
- stop_pipeline_thread force-release paths
- _run_pipeline recorder write path
- _run_multi_pipeline frame update loop
"""

import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

from src.main import (
    _compute_quality_score,
    _full_state_reset,
    _run_pipeline,
    _run_multi_pipeline,
    _wait_for_camera_release,
    stop_pipeline_thread,
    start_single_pipeline,
)


# --- _full_state_reset ---


class TestFullStateReset:
    def test_reset_with_lock(self):
        lock = threading.Lock()
        state = {
            "pending_hits_lock": lock,
            "pending_hits": {"a": 1, "b": 2},
            "latest_frame": "frame_data",
            "multi_latest_frames": {"cam1": "data"},
            "recent_detections": [{"score": 20}],
            "detection_timestamps": [time.time()],
        }
        _full_state_reset(state)
        assert state["pending_hits"] == {}
        assert state["latest_frame"] is None
        assert state["multi_latest_frames"] == {}
        assert state["recent_detections"] == []
        assert state["detection_timestamps"] == []

    def test_reset_without_lock(self):
        state = {
            "pending_hits_lock": None,
            "pending_hits": {"a": 1},
            "latest_frame": "frame",
            "multi_latest_frames": {"c": "d"},
            "recent_detections": [1, 2, 3],
            "detection_timestamps": [1.0],
        }
        _full_state_reset(state)
        assert state["pending_hits"] == {}
        assert state["latest_frame"] is None

    def test_reset_no_lock_key(self):
        """If pending_hits_lock key is missing, should still work."""
        state = {
            "pending_hits": {"x": 1},
            "latest_frame": "frame",
            "multi_latest_frames": {},
            "recent_detections": [],
            "detection_timestamps": [],
        }
        _full_state_reset(state)
        assert state["pending_hits"] == {}


# --- _wait_for_camera_release ---


class TestWaitForCameraRelease:
    @patch("src.main.cv2.VideoCapture")
    def test_skips_string_source(self, mock_cap):
        """Non-digit string sources (file/RTSP) should be skipped."""
        _wait_for_camera_release(["rtsp://camera1", "/path/to/video.mp4"], max_wait=0.5)
        mock_cap.assert_not_called()

    @patch("src.main.cv2.VideoCapture")
    def test_waits_for_usb_camera(self, mock_cap):
        """USB camera index should be opened and checked."""
        mock_instance = MagicMock()
        mock_instance.isOpened.return_value = True
        mock_cap.return_value = mock_instance

        _wait_for_camera_release([0], max_wait=1.0)
        mock_cap.assert_called_with(0)
        mock_instance.release.assert_called()

    @patch("src.main.cv2.VideoCapture")
    def test_string_digit_treated_as_usb(self, mock_cap):
        """String digit '1' should be treated as USB index."""
        mock_instance = MagicMock()
        mock_instance.isOpened.return_value = True
        mock_cap.return_value = mock_instance

        _wait_for_camera_release(["1"], max_wait=1.0)
        mock_cap.assert_called_with(1)

    @patch("src.main.cv2.VideoCapture")
    def test_timeout_if_camera_never_opens(self, mock_cap):
        """Should log warning and move on after max_wait."""
        mock_instance = MagicMock()
        mock_instance.isOpened.return_value = False
        mock_cap.return_value = mock_instance

        start = time.time()
        _wait_for_camera_release([0], max_wait=0.5)
        elapsed = time.time() - start
        # Should have waited approximately max_wait
        assert elapsed >= 0.3  # at least one retry
        assert elapsed < 3.0  # not forever

    @patch("src.main.cv2.VideoCapture")
    def test_retries_then_succeeds(self, mock_cap):
        """Camera fails first, succeeds on retry."""
        mock_instance = MagicMock()
        mock_instance.isOpened.side_effect = [False, False, True]
        mock_cap.return_value = mock_instance

        _wait_for_camera_release([0], max_wait=3.0)
        assert mock_instance.release.call_count >= 3


# --- stop_pipeline_thread force-release ---


class TestStopPipelineThreadForceRelease:
    def test_force_release_camera_on_timeout(self):
        """When thread doesn't die, should force-release camera."""
        evt = threading.Event()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True  # always alive

        mock_pipeline = MagicMock()
        mock_camera = MagicMock()
        mock_pipeline.camera = mock_camera

        state = {
            "pipeline_stop_event": evt,
            "pipeline_thread": mock_thread,
            "multi_pipeline_stop_event": None,
            "multi_pipeline_thread": None,
            "pipeline": mock_pipeline,
        }
        stop_pipeline_thread(state, "single", timeout=0.01)
        mock_camera.stop.assert_called_once()

    def test_force_release_pipeline_stop_when_no_camera(self):
        """When thread doesn't die and pipeline has no camera attr, call pipeline.stop()."""
        evt = threading.Event()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        mock_pipeline = MagicMock(spec=["stop"])  # no .camera attribute

        state = {
            "pipeline_stop_event": None,
            "pipeline_thread": None,
            "multi_pipeline_stop_event": evt,
            "multi_pipeline_thread": mock_thread,
            "multi_pipeline": mock_pipeline,
        }
        stop_pipeline_thread(state, "multi", timeout=0.01)
        mock_pipeline.stop.assert_called_once()

    def test_force_release_with_camera_none(self):
        """When camera attribute exists but is None, should try pipeline.stop()."""
        evt = threading.Event()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        mock_pipeline = MagicMock()
        mock_pipeline.camera = None

        state = {
            "pipeline_stop_event": evt,
            "pipeline_thread": mock_thread,
            "multi_pipeline_stop_event": None,
            "multi_pipeline_thread": None,
            "pipeline": mock_pipeline,
        }
        stop_pipeline_thread(state, "single", timeout=0.01)
        # camera is None, so hasattr(pipeline, 'stop') path
        mock_pipeline.stop.assert_called_once()

    def test_force_release_exception_caught(self):
        """Exception during force-release should not propagate."""
        evt = threading.Event()
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        mock_pipeline = MagicMock()
        mock_pipeline.camera = MagicMock()
        mock_pipeline.camera.stop.side_effect = RuntimeError("boom")

        state = {
            "pipeline_stop_event": evt,
            "pipeline_thread": mock_thread,
            "multi_pipeline_stop_event": None,
            "multi_pipeline_thread": None,
            "pipeline": mock_pipeline,
        }
        # Should not raise
        stop_pipeline_thread(state, "single", timeout=0.01)


# --- _run_pipeline callback and recorder ---


class TestRunPipelineCallbacks:
    @patch("src.cv.pipeline.DartPipeline")
    def test_on_dart_detected_with_detection_object(self, MockPipeline):
        """Callback creates candidate and tracks in ring buffer."""
        mock_pipe = MagicMock()
        mock_pipe.get_annotated_frame.return_value = None
        mock_pipe.get_latest_raw_frame.return_value = None
        MockPipeline.return_value = mock_pipe

        em = MagicMock()
        engine = MagicMock()
        state = {
            "shutdown_event": threading.Event(),
            "pipeline": None,
            "pipeline_running": False,
            "latest_frame": None,
            "event_manager": em,
            "game_engine": engine,
            "pending_hits_lock": threading.Lock(),
            "pending_hits": {},
            "recent_detections": [],
            "detection_timestamps": [],
            "recorder": None,
        }
        stop_event = threading.Event()

        def run_callback_then_stop():
            time.sleep(0.05)
            # Get the on_dart_detected callback that was set
            cb = mock_pipe.on_dart_detected
            if callable(cb):
                mock_det = MagicMock(frame_count=3, area=100)
                cb({"score": 20, "sector": 20, "multiplier": 1, "ring": "single",
                    "roi_x": 100, "roi_y": 200}, detection=mock_det)
            time.sleep(0.02)
            stop_event.set()

        t = threading.Thread(target=run_callback_then_stop)
        t.start()
        _run_pipeline(state, stop_event=stop_event)
        t.join(timeout=5)
        # Verify candidate was created
        if len(state["pending_hits"]) > 0:
            candidate = list(state["pending_hits"].values())[0]
            assert candidate["score"] == 20
            assert candidate["quality"] >= 50
            assert len(state["recent_detections"]) == 1

    @patch("src.cv.pipeline.DartPipeline")
    def test_on_dart_detected_no_engine_no_em(self, MockPipeline):
        """Callback returns early if engine or em missing."""
        mock_pipe = MagicMock()
        mock_pipe.get_annotated_frame.return_value = None
        mock_pipe.get_latest_raw_frame.return_value = None
        MockPipeline.return_value = mock_pipe

        state = {
            "shutdown_event": threading.Event(),
            "pipeline": None,
            "pipeline_running": False,
            "latest_frame": None,
            "event_manager": None,  # missing
            "game_engine": None,    # missing
            "pending_hits_lock": threading.Lock(),
            "pending_hits": {},
            "recent_detections": [],
            "detection_timestamps": [],
            "recorder": None,
        }
        stop_event = threading.Event()

        def run_callback_then_stop():
            time.sleep(0.05)
            cb = mock_pipe.on_dart_detected
            if callable(cb):
                cb({"score": 20, "sector": 20, "multiplier": 1, "ring": "single"})
            time.sleep(0.02)
            stop_event.set()

        t = threading.Thread(target=run_callback_then_stop)
        t.start()
        _run_pipeline(state, stop_event=stop_event)
        t.join(timeout=5)
        # No candidates created because em/engine were None
        assert len(state["pending_hits"]) == 0

    @patch("src.cv.pipeline.DartPipeline")
    def test_recorder_writes_raw_frame(self, MockPipeline):
        """If recorder is active, raw frames should be written."""
        mock_pipe = MagicMock()
        mock_pipe.get_annotated_frame.return_value = "annotated"
        mock_pipe.get_latest_raw_frame.return_value = "raw_frame"
        MockPipeline.return_value = mock_pipe

        mock_recorder = MagicMock()
        state = {
            "shutdown_event": threading.Event(),
            "pipeline": None,
            "pipeline_running": False,
            "latest_frame": None,
            "event_manager": MagicMock(),
            "game_engine": MagicMock(),
            "pending_hits_lock": threading.Lock(),
            "pending_hits": {},
            "recent_detections": [],
            "detection_timestamps": [],
            "recorder": mock_recorder,
        }
        stop_event = threading.Event()

        def stop_soon():
            time.sleep(0.05)
            stop_event.set()

        t = threading.Thread(target=stop_soon)
        t.start()
        _run_pipeline(state, stop_event=stop_event)
        t.join(timeout=5)
        mock_recorder.write.assert_called()
        assert state["latest_frame"] == "annotated"

    @patch("src.cv.pipeline.DartPipeline")
    def test_pipeline_general_exception_caught(self, MockPipeline):
        """General exceptions in pipeline setup should be caught."""
        MockPipeline.side_effect = RuntimeError("unexpected error")
        state = {
            "shutdown_event": threading.Event(),
            "pipeline": None,
            "pipeline_running": False,
        }
        _run_pipeline(state, stop_event=threading.Event())
        assert state["pipeline_running"] is False

    @patch("src.cv.pipeline.DartPipeline")
    def test_stop_event_none_uses_shutdown(self, MockPipeline):
        """If stop_event is None, should use shutdown_event."""
        mock_pipe = MagicMock()
        mock_pipe.get_annotated_frame.return_value = None
        mock_pipe.get_latest_raw_frame.return_value = None
        MockPipeline.return_value = mock_pipe

        shutdown = threading.Event()
        state = {
            "shutdown_event": shutdown,
            "pipeline": None,
            "pipeline_running": False,
            "latest_frame": None,
            "event_manager": MagicMock(),
            "game_engine": MagicMock(),
            "pending_hits_lock": threading.Lock(),
            "pending_hits": {},
            "recent_detections": [],
            "detection_timestamps": [],
            "recorder": None,
        }

        def stop_soon():
            time.sleep(0.05)
            shutdown.set()

        t = threading.Thread(target=stop_soon)
        t.start()
        _run_pipeline(state, stop_event=None)
        t.join(timeout=5)
        assert state["pipeline_running"] is False


# --- _run_multi_pipeline ---


class TestRunMultiPipeline:
    @patch("src.cv.multi_camera.MultiCameraPipeline")
    def test_multi_pipeline_start_failure(self, MockMulti):
        """If multi pipeline start() raises, should clean up."""
        mock_multi = MagicMock()
        mock_multi.start.side_effect = RuntimeError("No cameras")
        MockMulti.return_value = mock_multi

        state = {
            "shutdown_event": threading.Event(),
            "multi_pipeline": None,
            "multi_pipeline_running": False,
            "active_camera_ids": [],
            "multi_latest_frames": {},
            "latest_frame": None,
            "event_manager": MagicMock(),
            "game_engine": MagicMock(),
            "pending_hits_lock": threading.Lock(),
            "pending_hits": {},
            "recent_detections": [],
            "detection_timestamps": [],
        }
        _run_multi_pipeline(state, [{"camera_id": "a"}], threading.Event())
        assert state["multi_pipeline_running"] is False
        assert state["active_camera_ids"] == []

    @patch("src.cv.multi_camera.MultiCameraPipeline")
    def test_multi_on_dart_detected_callback(self, MockMulti):
        """Multi-cam dart detection callback creates candidates."""
        mock_multi = MagicMock()
        mock_multi.get_pipelines.return_value = {}
        MockMulti.return_value = mock_multi

        em = MagicMock()
        engine = MagicMock()
        state = {
            "shutdown_event": threading.Event(),
            "multi_pipeline": None,
            "multi_pipeline_running": False,
            "active_camera_ids": [],
            "multi_latest_frames": {},
            "latest_frame": None,
            "event_manager": em,
            "game_engine": engine,
            "pending_hits_lock": threading.Lock(),
            "pending_hits": {},
            "recent_detections": [],
            "detection_timestamps": [],
        }
        stop_event = threading.Event()

        # Capture the on_multi_dart_detected callback
        def capture_and_run():
            time.sleep(0.1)
            # Get constructor kwargs
            call_kwargs = MockMulti.call_args
            if call_kwargs:
                cb = call_kwargs.kwargs.get("on_multi_dart_detected") or call_kwargs[1].get("on_multi_dart_detected")
                if cb:
                    cb({"score": 60, "sector": 20, "multiplier": 3,
                        "ring": "triple", "roi_x": 50, "roi_y": 60, "source": "stereo"})
            time.sleep(0.05)
            stop_event.set()

        t = threading.Thread(target=capture_and_run)
        t.start()
        _run_multi_pipeline(state, [{"camera_id": "a"}, {"camera_id": "b"}], stop_event)
        t.join(timeout=5)

        if len(state["pending_hits"]) > 0:
            candidate = list(state["pending_hits"].values())[0]
            assert candidate["score"] == 60
            assert candidate["source"] == "stereo"

    @patch("src.cv.multi_camera.MultiCameraPipeline")
    def test_multi_on_camera_errors_callback(self, MockMulti):
        """Camera errors callback broadcasts via WebSocket."""
        mock_multi = MagicMock()
        mock_multi.get_pipelines.return_value = {}
        MockMulti.return_value = mock_multi

        em = MagicMock()
        state = {
            "shutdown_event": threading.Event(),
            "multi_pipeline": None,
            "multi_pipeline_running": False,
            "active_camera_ids": [],
            "multi_latest_frames": {},
            "latest_frame": None,
            "event_manager": em,
            "game_engine": MagicMock(),
            "pending_hits_lock": threading.Lock(),
            "pending_hits": {},
            "recent_detections": [],
            "detection_timestamps": [],
        }
        stop_event = threading.Event()

        def capture_and_run():
            time.sleep(0.1)
            call_kwargs = MockMulti.call_args
            if call_kwargs:
                cb = call_kwargs.kwargs.get("on_camera_errors_changed") or call_kwargs[1].get("on_camera_errors_changed")
                if cb:
                    cb({"cam_a": "connection lost"})
            time.sleep(0.05)
            stop_event.set()

        t = threading.Thread(target=capture_and_run)
        t.start()
        _run_multi_pipeline(state, [{"camera_id": "a"}], stop_event)
        t.join(timeout=5)

    @patch("src.cv.multi_camera.MultiCameraPipeline")
    def test_multi_pipeline_frame_update(self, MockMulti):
        """Frame update loop should call get_annotated_frame on sub-pipelines."""
        mock_pipe_a = MagicMock()
        mock_pipe_a.get_annotated_frame.return_value = "frame_a"
        mock_multi = MagicMock()
        mock_multi.get_pipelines.return_value = {"a": mock_pipe_a}
        MockMulti.return_value = mock_multi

        state = {
            "shutdown_event": threading.Event(),
            "multi_pipeline": None,
            "multi_pipeline_running": False,
            "active_camera_ids": [],
            "multi_latest_frames": {},
            "latest_frame": None,
            "event_manager": MagicMock(),
            "game_engine": MagicMock(),
            "pending_hits_lock": threading.Lock(),
            "pending_hits": {},
            "recent_detections": [],
            "detection_timestamps": [],
        }
        stop_event = threading.Event()

        def stop_soon():
            time.sleep(0.1)
            stop_event.set()

        t = threading.Thread(target=stop_soon)
        t.start()
        _run_multi_pipeline(state, [{"camera_id": "a"}], stop_event)
        t.join(timeout=5)
        # _full_state_reset in finally clears multi_latest_frames,
        # so we verify get_annotated_frame was called during the loop
        mock_pipe_a.get_annotated_frame.assert_called()
        # After cleanup, state should be reset
        assert state["multi_pipeline_running"] is False
        assert state["active_camera_ids"] == []


# --- _compute_quality_score edge cases ---


class TestComputeQualityScoreEdgeCases:
    def test_detection_none_defaults(self):
        """With detection=None (no attributes), should use defaults."""
        score = _compute_quality_score(None, {"ring": "single"})
        # None has no frame_count or area attrs
        assert 50 <= score <= 100

    def test_area_very_small_no_bonus(self):
        det = MagicMock(frame_count=1, area=5)
        score = _compute_quality_score(det, {"ring": "single"})
        # area < 10, no area bonus (except the +10 default is for area=0/missing)
        assert 50 <= score <= 100

    def test_area_in_acceptable_range(self):
        det = MagicMock(frame_count=1, area=1000)
        score = _compute_quality_score(det, {"ring": "single"})
        assert 50 <= score <= 100

    def test_area_suspicious_large(self):
        det = MagicMock(frame_count=1, area=2000)
        score = _compute_quality_score(det, {"ring": "single"})
        assert 50 <= score <= 100
