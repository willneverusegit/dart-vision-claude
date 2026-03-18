"""E2E tests for real test video replay through the pipeline.

Skips automatically if testvids/ directory is absent (CI-friendly).
"""

from __future__ import annotations

import glob
import os

import pytest

TESTVIDS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "testvids")
VIDEO_FILES = sorted(glob.glob(os.path.join(TESTVIDS_DIR, "*.mp4")))

pytestmark = pytest.mark.skipif(
    not VIDEO_FILES,
    reason="testvids/ directory absent or empty — skipping real video tests",
)


@pytest.fixture
def _import_pipeline():
    """Lazy import to avoid slow module load when skipping."""
    from src.cv.pipeline import DartPipeline
    return DartPipeline


@pytest.mark.parametrize("video_path", VIDEO_FILES,
                         ids=[os.path.basename(v) for v in VIDEO_FILES])
def test_video_replay_no_crash(video_path: str, _import_pipeline) -> None:
    """Pipeline processes at least some frames from each video without crashing."""
    DartPipeline = _import_pipeline
    darts: list[dict] = []

    pipeline = DartPipeline(
        camera_src=video_path,
        on_dart_detected=lambda score, detection=None: darts.append(score),
        marker_size_mm=100.0,  # Test videos use 100mm markers
        marker_spacing_mm=365.0,  # 480mm frame - 100mm marker - ~15mm margins
    )

    frames = 0
    max_frames = 100  # Keep tests fast

    try:
        pipeline.start()
        prev_frame_id = id(pipeline._last_raw_frame)
        for _ in range(max_frames):
            pipeline.process_frame()
            cur = pipeline._last_raw_frame
            if cur is not None and id(cur) != prev_frame_id:
                frames += 1
                prev_frame_id = id(cur)
    finally:
        pipeline.stop()

    assert frames > 0, f"No frames read from {os.path.basename(video_path)}"


@pytest.mark.parametrize("video_path", VIDEO_FILES[:1],
                         ids=[os.path.basename(v) for v in VIDEO_FILES[:1]])
def test_replay_camera_reads_frames(video_path: str) -> None:
    """ReplayCamera can open and read frames from test videos."""
    from src.cv.replay import ReplayCamera

    cam = ReplayCamera(video_path, loop=False)
    cam.start()
    try:
        ok, frame = cam.read()
        assert ok, "First frame read failed"
        assert frame is not None
        assert frame.shape[0] > 0 and frame.shape[1] > 0
    finally:
        cam.stop()
