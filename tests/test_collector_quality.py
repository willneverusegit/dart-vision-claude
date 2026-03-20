import numpy as np

from src.cv.camera_calibration import CharucoFrameCollector
from src.cv.stereo_calibration import DEFAULT_CHARUCO_BOARD_SPEC


def _sharp_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[::16, :] = 255
    frame[:, ::16] = 255
    return frame


def _corners(offset_x: float = 0.0, offset_y: float = 0.0):
    return np.array(
        [
            [100 + offset_x, 100 + offset_y],
            [200 + offset_x, 100 + offset_y],
            [300 + offset_x, 120 + offset_y],
            [120 + offset_x, 220 + offset_y],
            [220 + offset_x, 240 + offset_y],
            [320 + offset_x, 260 + offset_y],
        ],
        dtype=np.float32,
    )


def test_rejects_blurry_frame_with_reason():
    collector = CharucoFrameCollector(frames_needed=3)
    accepted = collector.add_frame_if_diverse(
        _corners(),
        np.zeros((480, 640, 3), dtype=np.uint8),
        board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        markers_found=4,
        charuco_corners_found=6,
        interpolation_ok=True,
    )
    assert accepted is False
    assert collector.last_reject_reason == "bild_unscharf"
    assert collector.last_sharpness == 0.0


def test_manual_capture_uses_lower_diversity_threshold():
    frame = _sharp_frame()
    collector = CharucoFrameCollector(frames_needed=2, capture_mode="manual")
    first = collector.add_frame_if_diverse(
        _corners(),
        frame,
        board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        markers_found=4,
        charuco_corners_found=6,
        interpolation_ok=True,
    )
    second = collector.add_frame_if_diverse(
        _corners(20, 0),
        frame,
        board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        markers_found=4,
        charuco_corners_found=6,
        interpolation_ok=True,
    )
    assert first is True
    assert second is True


def test_auto_capture_keeps_stricter_diversity_threshold():
    frame = _sharp_frame()
    collector = CharucoFrameCollector(frames_needed=2, capture_mode="auto")
    collector.add_frame_if_diverse(
        _corners(),
        frame,
        board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        markers_found=4,
        charuco_corners_found=6,
        interpolation_ok=True,
    )
    second = collector.add_frame_if_diverse(
        _corners(20, 0),
        frame,
        board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        markers_found=4,
        charuco_corners_found=6,
        interpolation_ok=True,
    )
    assert second is False
    assert collector.last_reject_reason == "zu_aehnlich"
