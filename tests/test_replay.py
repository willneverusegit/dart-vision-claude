"""Unit tests for ReplayCamera deterministic clip playback."""

from __future__ import annotations

import numpy as np

from src.cv.replay import ReplayCamera


class _FakeCapture:
    def __init__(self, frames: list[np.ndarray | None]):
        self._frames = frames
        self._idx = 0
        self._released = False
        self._frame_width = 640
        self._frame_height = 480

    def isOpened(self) -> bool:  # noqa: N802 - OpenCV API compatibility
        return True

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self._idx >= len(self._frames):
            return False, None
        frame = self._frames[self._idx]
        self._idx += 1
        if frame is None:
            return False, None
        return True, frame

    def set(self, prop: int, value: float) -> bool:  # noqa: ARG002
        # Only CAP_PROP_POS_FRAMES is used in ReplayCamera for loop seek.
        self._idx = 0
        return True

    def get(self, prop: int) -> float:
        # CAP_PROP_FRAME_WIDTH / CAP_PROP_FRAME_HEIGHT constants are enough for tests.
        if int(prop) == 3:
            return float(self._frame_width)
        if int(prop) == 4:
            return float(self._frame_height)
        return 0.0

    def release(self) -> None:
        self._released = True


def test_replay_camera_reads_frames(monkeypatch):
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    fake = _FakeCapture([frame, None])
    monkeypatch.setattr("src.cv.replay.cv2.VideoCapture", lambda _: fake)

    cam = ReplayCamera("demo.mp4", loop=False)
    ok1, f1 = cam.read()
    ok2, f2 = cam.read()

    assert ok1 and f1 is not None
    assert not ok2 and f2 is None


def test_replay_camera_loops(monkeypatch):
    frame = np.ones((10, 10, 3), dtype=np.uint8)
    fake = _FakeCapture([frame, None, frame])
    monkeypatch.setattr("src.cv.replay.cv2.VideoCapture", lambda _: fake)

    cam = ReplayCamera("loop.mp4", loop=True)
    ok1, _ = cam.read()
    ok2, _ = cam.read()

    assert ok1
    assert ok2


def test_replay_camera_frame_size_and_stop(monkeypatch):
    frame = np.ones((10, 10, 3), dtype=np.uint8)
    fake = _FakeCapture([frame])
    monkeypatch.setattr("src.cv.replay.cv2.VideoCapture", lambda _: fake)

    cam = ReplayCamera("size.mp4")
    assert cam.frame_size == (640, 480)
    cam.stop()
    assert not cam.is_running()
