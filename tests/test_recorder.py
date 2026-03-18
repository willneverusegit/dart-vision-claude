"""Tests for VideoRecorder."""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from src.cv.recorder import VideoRecorder


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def recorder(tmp_dir):
    return VideoRecorder(output_dir=tmp_dir)


def _dummy_frame(w=640, h=480):
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestVideoRecorder:
    def test_start_creates_file(self, recorder, tmp_dir):
        path = recorder.start(filename="test.mp4", frame_size=(640, 480))
        assert path.endswith("test.mp4")
        assert recorder.is_recording
        recorder.stop()

    def test_auto_filename(self, recorder):
        path = recorder.start(frame_size=(640, 480))
        assert "rec_" in path
        assert path.endswith(".mp4")
        recorder.stop()

    def test_write_increments_frame_count(self, recorder):
        recorder.start(frame_size=(640, 480))
        assert recorder.frame_count == 0
        recorder.write(_dummy_frame())
        assert recorder.frame_count == 1
        recorder.write(_dummy_frame())
        assert recorder.frame_count == 2
        recorder.stop()

    def test_write_noop_when_not_recording(self, recorder):
        recorder.write(_dummy_frame())
        assert recorder.frame_count == 0

    def test_stop_returns_summary(self, recorder):
        recorder.start(frame_size=(640, 480))
        for _ in range(5):
            recorder.write(_dummy_frame())
        summary = recorder.stop()
        assert summary["stopped"] is True
        assert summary["frame_count"] == 5
        assert "output_path" in summary
        assert not recorder.is_recording

    def test_stop_without_start(self, recorder):
        result = recorder.stop()
        assert result["stopped"] is False

    def test_double_start_raises(self, recorder):
        recorder.start(frame_size=(640, 480))
        with pytest.raises(RuntimeError, match="laeuft bereits"):
            recorder.start(frame_size=(640, 480))
        recorder.stop()

    def test_status(self, recorder):
        status = recorder.status()
        assert status["recording"] is False
        recorder.start(frame_size=(640, 480))
        status = recorder.status()
        assert status["recording"] is True
        assert status["frame_count"] == 0
        recorder.stop()

    def test_output_file_exists(self, recorder, tmp_dir):
        recorder.start(filename="out.mp4", frame_size=(320, 240))
        for _ in range(10):
            recorder.write(_dummy_frame(320, 240))
        recorder.stop()
        assert os.path.exists(os.path.join(tmp_dir, "out.mp4"))
        assert os.path.getsize(os.path.join(tmp_dir, "out.mp4")) > 0
