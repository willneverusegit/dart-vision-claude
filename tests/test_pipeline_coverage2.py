"""Additional pipeline.py coverage tests — targeting branches untested in test_pipeline_coverage.py.

Focus: process_frame() branches, start()/stop(), _check_camera_focus(),
detect_optical_center() with camera read, property proxies, init params.
"""

import time
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock

from src.cv.pipeline import DartPipeline, FRAME_STALE_THRESHOLD_S
from src.cv.detector import DartDetection


def _make_pipeline(**kwargs) -> DartPipeline:
    """Create a pipeline with sane defaults for testing."""
    return DartPipeline(camera_src=0, **kwargs)


def _fake_frame(h=480, w=640, channels=3, dtype=np.uint8):
    return np.zeros((h, w, channels), dtype=dtype)


def _setup_pipeline_with_camera():
    """Return a pipeline with mocked camera returning a valid frame."""
    p = _make_pipeline()
    mock_cam = MagicMock()
    mock_cam.read.return_value = (True, _fake_frame())
    p.camera = mock_cam
    return p


# --- Init params ---

class TestInitParams:
    def test_diff_threshold_passed_to_detector(self):
        p = DartPipeline(camera_src=0, diff_threshold=80)
        assert p.frame_diff_detector.diff_threshold == 80

    def test_diff_threshold_default(self):
        p = DartPipeline(camera_src=0)
        assert p.frame_diff_detector.diff_threshold == 30

    def test_marker_params_stored(self):
        p = DartPipeline(camera_src=0, marker_size_mm=100.0, marker_spacing_mm=365.0)
        assert p.marker_size_mm == 100.0
        assert p.marker_spacing_mm == 365.0


# --- Property proxies to MotionFilter ---

class TestMotionFilterProxies:
    def test_idle_frame_skip_threshold_getter(self):
        p = _make_pipeline()
        assert p._idle_frame_skip_threshold == p._motion_filter.idle_threshold

    def test_idle_frame_skip_threshold_setter(self):
        p = _make_pipeline()
        p._idle_frame_skip_threshold = 20
        assert p._motion_filter.idle_threshold == 20

    def test_no_motion_count_getter(self):
        p = _make_pipeline()
        assert p._no_motion_count == p._motion_filter._no_motion_count

    def test_no_motion_count_setter(self):
        p = _make_pipeline()
        p._no_motion_count = 5
        assert p._motion_filter._no_motion_count == 5

    def test_scoring_lock_frames_getter(self):
        p = _make_pipeline()
        assert p._scoring_lock_frames == p._motion_filter.scoring_lock_frames

    def test_scoring_lock_frames_setter(self):
        p = _make_pipeline()
        p._scoring_lock_frames = 30
        assert p._motion_filter.scoring_lock_frames == 30

    def test_scoring_lock_counter_getter(self):
        p = _make_pipeline()
        assert p._scoring_lock_counter == p._motion_filter._scoring_lock_counter

    def test_scoring_lock_counter_setter(self):
        p = _make_pipeline()
        p._scoring_lock_counter = 10
        assert p._motion_filter._scoring_lock_counter == 10


# --- start() ---

class TestStart:
    def test_start_initializes_camera_and_calls_refresh(self):
        p = _make_pipeline()
        mock_cam = MagicMock()
        mock_cam.read.return_value = (True, _fake_frame())

        with patch.object(p, "_build_camera_source", return_value=mock_cam):
            p.start()

        mock_cam.start.assert_called_once()
        assert p.camera is mock_cam

    def test_start_restores_homography(self):
        p = _make_pipeline()
        mock_cam = MagicMock()
        mock_cam.read.return_value = (True, _fake_frame())

        fake_pose = MagicMock()
        fake_pose.homography = np.eye(3)

        with patch.object(p, "_build_camera_source", return_value=mock_cam), \
             patch.object(p.board_calibration, "get_pose", return_value=fake_pose), \
             patch.object(p.roi_processor, "set_homography_matrix") as mock_set_h:
            p.start()

        mock_set_h.assert_called_once()

    def test_start_restores_optical_center(self):
        p = _make_pipeline()
        mock_cam = MagicMock()
        mock_cam.read.return_value = (True, _fake_frame())

        with patch.object(p, "_build_camera_source", return_value=mock_cam), \
             patch.object(p.board_calibration, "get_optical_center", return_value=(200.0, 195.0)):
            p.start()

        assert p._optical_center == (200.0, 195.0)

    def test_start_no_homography(self):
        p = _make_pipeline()
        mock_cam = MagicMock()
        mock_cam.read.return_value = (True, _fake_frame())

        fake_pose = MagicMock()
        fake_pose.homography = None

        with patch.object(p, "_build_camera_source", return_value=mock_cam), \
             patch.object(p.board_calibration, "get_pose", return_value=fake_pose), \
             patch.object(p.roi_processor, "set_homography_matrix") as mock_set_h:
            p.start()

        mock_set_h.assert_not_called()


# --- _check_camera_focus() ---

class TestCheckCameraFocus:
    def test_no_camera(self):
        p = _make_pipeline()
        p.camera = None
        p._check_camera_focus()  # should not crash

    def test_read_fails(self):
        p = _make_pipeline()
        p.camera = MagicMock()
        p.camera.read.return_value = (False, None)
        p._check_camera_focus()  # should not crash

    def test_low_focus_quality(self):
        p = _make_pipeline()
        p.camera = MagicMock()
        # Create a very blurry frame (all zeros -> Laplacian variance = 0)
        p.camera.read.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))
        p._focus_quality_threshold = 50.0
        p._check_camera_focus()  # should log warning, not crash

    def test_good_focus_quality(self):
        p = _make_pipeline()
        p.camera = MagicMock()
        # Create a frame with high-frequency content (good focus)
        frame = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        p.camera.read.return_value = (True, frame)
        p._focus_quality_threshold = 0.1  # very low threshold so random noise passes
        p._check_camera_focus()  # should log OK

    def test_grayscale_frame(self):
        p = _make_pipeline()
        p.camera = MagicMock()
        # 2D grayscale frame — tests the len(shape)==3 branch
        frame = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        p.camera.read.return_value = (True, frame)
        p._focus_quality_threshold = 0.1
        p._check_camera_focus()


# --- process_frame() branches ---

class TestProcessFrameBranches:
    def test_stale_frame_dropped(self):
        """Frame is dropped when processing takes too long."""
        p = _setup_pipeline_with_camera()
        original_monotonic = time.monotonic

        call_count = [0]

        def mock_monotonic():
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: t_capture
                return 100.0
            else:
                # Second call: stale check — far in the future
                return 100.0 + FRAME_STALE_THRESHOLD_S + 0.1
            return original_monotonic()

        with patch("src.cv.pipeline.time.monotonic", side_effect=mock_monotonic):
            result = p.process_frame()

        assert result is None
        assert p._dropped_frames == 1

    def test_idle_frame_skip(self):
        """Every 2nd frame is skipped when pipeline is idle."""
        p = _setup_pipeline_with_camera()
        p._idle_frame_skip_enabled = True
        p._motion_filter._no_motion_count = 100  # well above idle threshold
        p._frame_counter = 1  # next increment makes it 2 (even -> skip)

        result = p.process_frame()
        assert result is None

    def test_bounce_out_detection(self):
        """Bounce-out detection returns None and does not score."""
        p = _setup_pipeline_with_camera()

        bounce_detection = DartDetection(
            center=(200, 200), area=500.0, confidence=0.8,
            frame_count=3, bounce_out=True
        )

        with patch.object(p.frame_diff_detector, "update", return_value=bounce_detection), \
             patch.object(p.motion_detector, "detect", return_value=(np.zeros((400, 400), dtype=np.uint8), True)):
            result = p.process_frame()

        assert result is None

    def test_exclusion_zone_rejection(self):
        """Detection in exclusion zone is rejected."""
        p = _setup_pipeline_with_camera()

        detection = DartDetection(
            center=(200, 200), area=500.0, confidence=0.8, frame_count=3
        )

        with patch.object(p.frame_diff_detector, "update", return_value=detection), \
             patch.object(p.motion_detector, "detect", return_value=(np.zeros((400, 400), dtype=np.uint8), True)), \
             patch.object(p.dart_detector._cooldown, "is_in_exclusion_zone", return_value=True):
            result = p.process_frame()

        assert result is None

    def test_successful_detection_and_scoring(self):
        """Full detection -> scoring -> callback path."""
        callback = MagicMock()
        p = DartPipeline(camera_src=0, on_dart_detected=callback)
        mock_cam = MagicMock()
        mock_cam.read.return_value = (True, _fake_frame())
        p.camera = mock_cam

        detection = DartDetection(
            center=(200, 200), area=500.0, confidence=0.8, frame_count=3
        )

        fake_hit = MagicMock()
        fake_score = {"ring": "triple", "score": 60, "sector": 20, "multiplier": 3}

        with patch.object(p.frame_diff_detector, "update", return_value=detection), \
             patch.object(p.motion_detector, "detect", return_value=(np.zeros((400, 400), dtype=np.uint8), True)), \
             patch.object(p.dart_detector._cooldown, "is_in_exclusion_zone", return_value=False), \
             patch.object(p.board_calibration, "get_geometry") as mock_geom:
            mock_geom_inst = MagicMock()
            mock_geom_inst.point_to_score.return_value = fake_hit
            mock_geom_inst.hit_to_dict.return_value = fake_score
            mock_geom.return_value = mock_geom_inst
            p.geometry = mock_geom_inst

            result = p.process_frame()

        assert result == fake_score
        callback.assert_called_once()
        assert detection.raw_center is not None

    def test_detection_with_tip_sets_raw_tip(self):
        """When detection has a tip, raw_tip is computed."""
        p = _setup_pipeline_with_camera()

        detection = DartDetection(
            center=(200, 200), area=500.0, confidence=0.8, frame_count=3,
            tip=(195, 210)
        )

        fake_hit = MagicMock()
        fake_score = {"ring": "single", "score": 20, "sector": 20, "multiplier": 1}

        with patch.object(p.frame_diff_detector, "update", return_value=detection), \
             patch.object(p.motion_detector, "detect", return_value=(np.zeros((400, 400), dtype=np.uint8), True)), \
             patch.object(p.dart_detector._cooldown, "is_in_exclusion_zone", return_value=False):
            p.geometry = MagicMock()
            p.geometry.point_to_score.return_value = fake_hit
            p.geometry.hit_to_dict.return_value = fake_score

            result = p.process_frame()

        assert result == fake_score
        assert detection.raw_tip is not None
        assert detection.raw_center is not None

    def test_detection_without_tip(self):
        """When detection has no tip, raw_tip stays None."""
        p = _setup_pipeline_with_camera()

        detection = DartDetection(
            center=(200, 200), area=500.0, confidence=0.8, frame_count=3,
            tip=None
        )

        with patch.object(p.frame_diff_detector, "update", return_value=detection), \
             patch.object(p.motion_detector, "detect", return_value=(np.zeros((400, 400), dtype=np.uint8), True)), \
             patch.object(p.dart_detector._cooldown, "is_in_exclusion_zone", return_value=False):
            p.geometry = MagicMock()
            p.geometry.point_to_score.return_value = MagicMock()
            p.geometry.hit_to_dict.return_value = {"ring": "miss", "score": 0, "sector": 0, "multiplier": 0}

            result = p.process_frame()

        assert result is not None
        assert detection.raw_tip is None

    def test_no_detection_returns_none(self):
        """When frame_diff_detector returns None, process_frame returns None."""
        p = _setup_pipeline_with_camera()

        with patch.object(p.frame_diff_detector, "update", return_value=None), \
             patch.object(p.motion_detector, "detect", return_value=(np.zeros((400, 400), dtype=np.uint8), False)):
            result = p.process_frame()

        assert result is None


# --- detect_optical_center() ---

class TestDetectOpticalCenterExtra:
    def test_camera_read_success(self):
        """When _last_raw_frame is None but camera reads successfully."""
        p = _make_pipeline()
        p._last_raw_frame = None
        p.camera = MagicMock()
        frame = _fake_frame()
        p.camera.read.return_value = (True, frame)

        result = p.detect_optical_center()
        assert result is not None
        assert p._last_raw_frame is frame

    def test_with_grayscale_roi(self):
        """When remapper returns a grayscale image, it should be converted to BGR."""
        p = _make_pipeline()
        p._last_raw_frame = _fake_frame()

        gray_roi = np.zeros((400, 400), dtype=np.uint8)
        with patch.object(p.remapper, "remap", return_value=gray_roi):
            result = p.detect_optical_center()
            assert result is not None


# --- _refresh_geometry() ---

class TestRefreshGeometry:
    def test_without_optical_center(self):
        p = _make_pipeline()
        p._optical_center = None
        p._refresh_geometry()
        assert p.geometry is not None
        # optical_center_px should be the default from BoardGeometry


# --- get_roi_preview() grayscale branch ---

class TestGetRoiPreviewGrayscale:
    def test_grayscale_roi_converted_to_bgr(self):
        p = _make_pipeline()
        p._last_raw_frame = _fake_frame()

        gray_roi = np.zeros((400, 400), dtype=np.uint8)
        with patch.object(p.remapper, "remap", return_value=gray_roi):
            roi = p.get_roi_preview()
            assert roi is not None
            assert len(roi.shape) == 3  # should be BGR


# --- _draw_field_overlay() radii fallback ---

class TestDrawFieldOverlayRadiiFallback:
    def test_invalid_radii_uses_fallback(self):
        p = _make_pipeline()
        p._optical_center = (200.0, 200.0)
        overlay = np.zeros((400, 400, 3), dtype=np.uint8)

        with patch.object(p.board_calibration, "get_radii_px", return_value=[]):
            p._draw_field_overlay(overlay)
            # Should not crash — uses fallback radius = min(cx, cy)

    def test_radii_with_zero_outer(self):
        p = _make_pipeline()
        overlay = np.zeros((400, 400, 3), dtype=np.uint8)

        with patch.object(p.board_calibration, "get_radii_px", return_value=[10, 20, 30, 40, 50, 0]):
            p._draw_field_overlay(overlay)
            # Zero outer radius -> fallback


# --- _update_annotated_frame() marker overlay branch ---

class TestAnnotatedFrameMarkerOverlay:
    def test_marker_overlay_enabled(self):
        p = _make_pipeline()
        p.show_overlay_markers = True
        frame = _fake_frame()
        roi = np.zeros((400, 400), dtype=np.uint8)

        # _draw_marker_overlay should be called
        with patch.object(p, "_draw_marker_overlay") as mock_draw:
            p._update_annotated_frame(frame, roi, None)
            mock_draw.assert_called_once()


# --- _draw_marker_overlay() ---

class TestDrawMarkerOverlay:
    def test_no_markers_detected(self):
        p = _make_pipeline()
        frame = _fake_frame(h=480, w=640)
        p._draw_marker_overlay(frame)
        # Should complete without error, showing "Keine Marker erkannt"

    def test_exception_handling(self):
        p = _make_pipeline()
        frame = "not_a_frame"  # will cause exception
        p._draw_marker_overlay(frame)
        # Should catch exception and log debug


# --- _composite_overlay() edge cases ---

class TestCompositeOverlayEdge:
    def test_grayscale_overlay(self):
        p = _make_pipeline()
        frame = _fake_frame()
        overlay = np.zeros((100, 100), dtype=np.uint8)  # 2D
        p._composite_overlay(frame, overlay, 10, 10, 50, "TEST")

    def test_bgr_overlay(self):
        p = _make_pipeline()
        frame = _fake_frame()
        overlay = np.zeros((100, 100, 3), dtype=np.uint8)  # 3D
        p._composite_overlay(frame, overlay, 10, 10, 50, "TEST")
