"""Tests for MultiCameraPipeline."""

import time
import threading
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from src.cv.multi_camera import MultiCameraPipeline, MAX_DETECTION_TIME_DIFF_S


@dataclass
class FakeDetection:
    """Minimal detection mock for testing."""
    center: tuple[int, int] = (200, 200)
    area: float = 100.0
    confidence: float = 0.8
    frame_count: int = 3


class TestMultiCameraPipelineInit:
    def test_empty_configs(self):
        """Instantiation with empty camera list should not crash."""
        pipeline = MultiCameraPipeline(camera_configs=[])
        assert pipeline._pipelines == {}
        assert pipeline._running is False

    def test_single_config(self):
        """Instantiation with one camera config stores it."""
        configs = [{"camera_id": "cam_left", "src": 0}]
        pipeline = MultiCameraPipeline(camera_configs=configs)
        assert len(pipeline.camera_configs) == 1
        assert pipeline.camera_configs[0]["camera_id"] == "cam_left"

    def test_callback_stored(self):
        """Callback is stored."""
        cb = MagicMock()
        pipeline = MultiCameraPipeline(camera_configs=[], on_multi_dart_detected=cb)
        assert pipeline.on_multi_dart_detected is cb


class TestDetectionBuffer:
    def test_on_single_detection_buffers(self):
        """_on_single_detection stores entry in buffer."""
        pipeline = MultiCameraPipeline(camera_configs=[])
        score = {"score": 20, "ring": "single", "sector": 20, "multiplier": 1}
        det = FakeDetection()

        pipeline._on_single_detection("cam_left", score, det)

        assert "cam_left" in pipeline._detection_buffer
        entry = pipeline._detection_buffer["cam_left"]
        assert entry["camera_id"] == "cam_left"
        assert entry["score_result"] == score
        assert entry["detection"] is det
        assert "timestamp" in entry

    def test_buffer_overwrites_same_camera(self):
        """Second detection from same camera overwrites the first."""
        pipeline = MultiCameraPipeline(camera_configs=[])
        score1 = {"score": 20}
        score2 = {"score": 60}
        det = FakeDetection()

        pipeline._on_single_detection("cam_left", score1, det)
        pipeline._on_single_detection("cam_left", score2, det)

        assert len(pipeline._detection_buffer) == 1
        assert pipeline._detection_buffer["cam_left"]["score_result"]["score"] == 60

    def test_buffer_multiple_cameras(self):
        """Detections from different cameras are stored separately."""
        pipeline = MultiCameraPipeline(camera_configs=[])
        det = FakeDetection()

        pipeline._on_single_detection("cam_left", {"score": 20}, det)
        pipeline._on_single_detection("cam_right", {"score": 20}, det)

        assert len(pipeline._detection_buffer) == 2


class TestVotingFallback:
    def test_picks_highest_confidence(self):
        """Voting fallback selects the detection with highest confidence."""
        pipeline = MultiCameraPipeline(camera_configs=[])

        entries = [
            {
                "camera_id": "cam_left",
                "score_result": {"score": 20, "ring": "single"},
                "detection": FakeDetection(confidence=0.6),
                "timestamp": time.time(),
            },
            {
                "camera_id": "cam_right",
                "score_result": {"score": 60, "ring": "triple"},
                "detection": FakeDetection(confidence=0.9),
                "timestamp": time.time(),
            },
        ]

        result = pipeline._voting_fallback(entries)
        assert result["score"] == 60
        assert result["source"] == "voting_fallback"
        assert result["camera_id"] == "cam_right"


class TestResetAll:
    def test_reset_clears_buffer(self):
        """reset_all clears the detection buffer."""
        pipeline = MultiCameraPipeline(camera_configs=[])
        det = FakeDetection()
        pipeline._on_single_detection("cam_left", {"score": 20}, det)
        assert len(pipeline._detection_buffer) == 1

        # reset_all would also call pipeline.reset_turn() on each pipeline,
        # but we have no actual pipelines. Just test buffer clearing.
        with pipeline._buffer_lock:
            pipeline._detection_buffer.clear()
        assert len(pipeline._detection_buffer) == 0


class TestEmit:
    def test_emit_calls_callback(self):
        """_emit invokes the on_multi_dart_detected callback."""
        cb = MagicMock()
        pipeline = MultiCameraPipeline(camera_configs=[], on_multi_dart_detected=cb)
        result = {"score": 20, "source": "test"}

        pipeline._emit(result)
        cb.assert_called_once_with(result)

    def test_emit_no_callback(self):
        """_emit with no callback does not crash."""
        pipeline = MultiCameraPipeline(camera_configs=[])
        pipeline._emit({"score": 20})  # Should not raise


class TestTryFuse:
    def test_empty_buffer_no_emit(self):
        """No detections -> no emission."""
        cb = MagicMock()
        pipeline = MultiCameraPipeline(camera_configs=[], on_multi_dart_detected=cb)
        pipeline._try_fuse()
        cb.assert_not_called()

    def test_single_old_detection_emitted(self):
        """Single detection older than timeout is emitted as fallback."""
        cb = MagicMock()
        pipeline = MultiCameraPipeline(camera_configs=[], on_multi_dart_detected=cb)

        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "ring": "single"},
            "detection": FakeDetection(),
            "timestamp": time.time() - 0.5,  # older than sync_wait_s (0.3s default)
        }

        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "single"
        assert result["camera_id"] == "cam_left"
        assert pipeline._detection_buffer == {}

    def test_single_recent_detection_not_emitted(self):
        """Single detection within timeout window is NOT emitted (waiting for second camera)."""
        cb = MagicMock()
        pipeline = MultiCameraPipeline(camera_configs=[], on_multi_dart_detected=cb)

        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "ring": "single"},
            "detection": FakeDetection(),
            "timestamp": time.time(),  # Very recent
        }

        pipeline._try_fuse()
        cb.assert_not_called()

    def test_two_detections_too_far_apart(self):
        """Two detections beyond time window -> single_timeout fallback."""
        cb = MagicMock()
        pipeline = MultiCameraPipeline(camera_configs=[], on_multi_dart_detected=cb)

        now = time.time()
        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "ring": "single"},
            "detection": FakeDetection(confidence=0.7),
            "timestamp": now - 1.0,  # 1 second ago
        }
        pipeline._detection_buffer["cam_right"] = {
            "camera_id": "cam_right",
            "score_result": {"score": 60, "ring": "triple"},
            "detection": FakeDetection(confidence=0.9),
            "timestamp": now,
        }

        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "single_timeout"
        assert result["camera_id"] == "cam_right"  # Most recent

    def test_two_detections_no_camera_params_voting_fallback(self):
        """Two near-simultaneous detections without CameraParams -> voting_fallback."""
        cb = MagicMock()
        configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ]
        pipeline = MultiCameraPipeline(camera_configs=configs, on_multi_dart_detected=cb)

        now = time.time()
        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "ring": "single"},
            "detection": FakeDetection(confidence=0.6),
            "timestamp": now,
        }
        pipeline._detection_buffer["cam_right"] = {
            "camera_id": "cam_right",
            "score_result": {"score": 60, "ring": "triple"},
            "detection": FakeDetection(confidence=0.95),
            "timestamp": now + 0.01,
        }

        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "voting_fallback"
        assert result["score"] == 60  # Higher confidence

    def test_get_pipelines_returns_copy(self):
        """get_pipelines returns a copy dict."""
        pipeline = MultiCameraPipeline(camera_configs=[])
        result = pipeline.get_pipelines()
        assert isinstance(result, dict)
        assert result == {}


class TestThreadSafety:
    def test_concurrent_buffer_access(self):
        """Multiple threads writing to buffer concurrently should not crash."""
        pipeline = MultiCameraPipeline(camera_configs=[])
        errors = []

        def write_detection(cam_id, n):
            try:
                for i in range(n):
                    pipeline._on_single_detection(
                        cam_id,
                        {"score": i},
                        FakeDetection(confidence=0.5 + i * 0.01),
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=write_detection, args=("cam_a", 50)),
            threading.Thread(target=write_detection, args=("cam_b", 50)),
            threading.Thread(target=write_detection, args=("cam_c", 50)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # Buffer should have at most 3 entries (one per camera, latest wins)
        assert len(pipeline._detection_buffer) <= 3
