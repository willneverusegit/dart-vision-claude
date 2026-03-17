"""Tests for src/cv/pipeline.py to increase coverage from 44% to 60%+."""

import numpy as np
from unittest.mock import MagicMock, patch

from src.cv.pipeline import DartPipeline


class TestDartPipelineInit:
    def test_default_init(self):
        p = DartPipeline(camera_src=0)
        assert p.camera_src == 0
        assert p.camera is None
        assert p.geometry is None
        assert p._dropped_frames == 0
        assert p._optical_center is None

    def test_init_with_capture_params(self):
        p = DartPipeline(camera_src=0, capture_width=320, capture_height=240, capture_fps=15)
        assert p._capture_width == 320
        assert p._capture_height == 240
        assert p._capture_fps == 15

    def test_backward_compat_aliases(self):
        p = DartPipeline(camera_src=0)
        assert p.roi is p.roi_processor
        assert p.detector is p.dart_detector
        assert p.calibration is p.board_calibration


class TestDartPipelineStop:
    def test_stop_no_camera(self):
        p = DartPipeline(camera_src=0)
        p.camera = None
        p.stop()  # Should not crash

    def test_stop_with_camera(self):
        p = DartPipeline(camera_src=0)
        p.camera = MagicMock()
        p.stop()
        p.camera.stop.assert_called_once()

    def test_stop_debug_mode(self):
        p = DartPipeline(camera_src=0, debug=True)
        p.camera = MagicMock()
        with patch("cv2.destroyAllWindows"):
            p.stop()


class TestDartPipelineBuildCamera:
    def test_build_threaded_camera(self):
        p = DartPipeline(camera_src=0)
        with patch("src.cv.pipeline.ThreadedCamera") as MockCam:
            MockCam.return_value = MagicMock()
            cam = p._build_camera_source()
            MockCam.assert_called_once_with(src=0, width=None, height=None, fps=None)

    def test_build_with_capture_params(self):
        p = DartPipeline(camera_src=0, capture_width=320, capture_height=240, capture_fps=15)
        with patch("src.cv.pipeline.ThreadedCamera") as MockCam:
            MockCam.return_value = MagicMock()
            p._build_camera_source()
            MockCam.assert_called_once_with(src=0, width=320, height=240, fps=15)

    def test_build_replay_camera(self, tmp_path):
        video = tmp_path / "test.avi"
        video.write_bytes(b"\x00" * 100)
        p = DartPipeline(camera_src=str(video))
        with patch("src.cv.pipeline.ReplayCamera") as MockReplay:
            MockReplay.return_value = MagicMock()
            cam = p._build_camera_source()
            MockReplay.assert_called_once()


class TestDartPipelineRefresh:
    def test_refresh_remapper(self):
        p = DartPipeline(camera_src=0)
        p.refresh_remapper()
        assert p.geometry is not None

    def test_refresh_geometry_with_optical_center(self):
        p = DartPipeline(camera_src=0)
        p._optical_center = (210.0, 195.0)
        p._refresh_geometry()
        assert p.geometry is not None
        assert p.geometry.optical_center_px == (210.0, 195.0)


class TestDartPipelineProcessFrame:
    def test_process_no_motion(self):
        p = DartPipeline(camera_src=0)
        mock_cam = MagicMock()
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cam.read.return_value = (True, fake_frame)
        p.camera = mock_cam
        result = p.process_frame()
        assert result is None  # no motion on static frame

    def test_process_no_camera(self):
        p = DartPipeline(camera_src=0)
        p.camera = None
        assert p.process_frame() is None

    def test_process_read_fails(self):
        p = DartPipeline(camera_src=0)
        p.camera = MagicMock()
        p.camera.read.return_value = (False, None)
        assert p.process_frame() is None


class TestDartPipelineHelpers:
    def test_get_annotated_frame(self):
        p = DartPipeline(camera_src=0)
        p._last_annotated_frame = "frame"
        assert p.get_annotated_frame() == "frame"

    def test_get_latest_raw_frame(self):
        p = DartPipeline(camera_src=0)
        p._last_raw_frame = "raw"
        assert p.get_latest_raw_frame() == "raw"

    def test_get_roi_preview_no_frame(self):
        p = DartPipeline(camera_src=0)
        p._last_raw_frame = None
        assert p.get_roi_preview() is None

    def test_get_roi_preview_with_frame(self):
        p = DartPipeline(camera_src=0)
        p._last_raw_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        roi = p.get_roi_preview()
        assert roi is not None

    def test_get_field_overlay_no_frame(self):
        p = DartPipeline(camera_src=0)
        p._last_raw_frame = None
        assert p.get_field_overlay() is None

    def test_get_field_overlay_with_frame(self):
        p = DartPipeline(camera_src=0)
        p._last_raw_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        overlay = p.get_field_overlay()
        assert overlay is not None

    def test_get_geometry_info(self):
        p = DartPipeline(camera_src=0)
        info = p.get_geometry_info()
        assert "lens_valid" in info

    def test_reset_turn(self):
        p = DartPipeline(camera_src=0)
        callback = MagicMock()
        p.on_dart_removed = callback
        p.reset_turn()
        callback.assert_called_once()

    def test_reset_turn_no_callback(self):
        p = DartPipeline(camera_src=0)
        p.on_dart_removed = None
        p.reset_turn()  # should not crash


class TestDetectOpticalCenter:
    def test_no_frame_no_camera(self):
        p = DartPipeline(camera_src=0)
        p._last_raw_frame = None
        p.camera = None
        assert p.detect_optical_center() is None

    def test_camera_read_fails(self):
        p = DartPipeline(camera_src=0)
        p._last_raw_frame = None
        p.camera = MagicMock()
        p.camera.read.return_value = (False, None)
        assert p.detect_optical_center() is None

    def test_with_frame(self):
        p = DartPipeline(camera_src=0)
        p._last_raw_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = p.detect_optical_center()
        assert result is not None
        assert len(result) == 2


class TestUpdateAnnotatedFrame:
    def test_basic_annotation(self):
        p = DartPipeline(camera_src=0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        roi = np.zeros((400, 400), dtype=np.uint8)
        p._update_annotated_frame(frame, roi, None)
        assert p._last_annotated_frame is not None

    def test_annotation_with_detection(self):
        p = DartPipeline(camera_src=0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        roi = np.zeros((400, 400), dtype=np.uint8)
        det = MagicMock()
        det.center = (200, 200)
        score = {"ring": "triple", "score": 60}
        p._update_annotated_frame(frame, roi, None, det, score)
        assert p._last_annotated_frame is not None

    def test_annotation_with_motion_overlay(self):
        p = DartPipeline(camera_src=0)
        p.show_overlay_motion = True
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        roi = np.zeros((400, 400), dtype=np.uint8)
        motion = np.zeros((400, 400), dtype=np.uint8)
        p._update_annotated_frame(frame, roi, motion)
        assert p._last_annotated_frame is not None


class TestCompositeOverlay:
    def test_negative_coords(self):
        p = DartPipeline(camera_src=0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        overlay = np.zeros((100, 100), dtype=np.uint8)
        p._composite_overlay(frame, overlay, -1, 0, 100, "TEST")
        # Should return without modification

    def test_out_of_bounds(self):
        p = DartPipeline(camera_src=0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        overlay = np.zeros((100, 100), dtype=np.uint8)
        p._composite_overlay(frame, overlay, 600, 400, 100, "TEST")
        # Should return without modification

    def test_valid_overlay(self):
        p = DartPipeline(camera_src=0)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        overlay = np.zeros((100, 100), dtype=np.uint8)
        p._composite_overlay(frame, overlay, 10, 10, 50, "TEST")
        # Should succeed


class TestDrawFieldOverlay:
    def test_draw_field_overlay_with_optical_center(self):
        p = DartPipeline(camera_src=0)
        p._optical_center = (200.0, 200.0)
        overlay = np.zeros((400, 400, 3), dtype=np.uint8)
        p._draw_field_overlay(overlay)

    def test_draw_field_overlay_without_center(self):
        p = DartPipeline(camera_src=0)
        p._optical_center = None
        overlay = np.zeros((400, 400, 3), dtype=np.uint8)
        p._draw_field_overlay(overlay)
