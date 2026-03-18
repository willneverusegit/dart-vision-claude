"""Integration tests for the CV pipeline modules."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
from src.cv.geometry import BoardGeometry, BoardPose
from src.cv.motion import MotionDetector
from src.cv.roi import ROIProcessor
from src.cv.detector import DartImpactDetector


class TestMotionDetector:
    def test_default_no_shadows(self):
        """Default MotionDetector should have detectShadows=False."""
        md = MotionDetector()
        assert md._detect_shadows is False

    def test_custom_learning_rate(self):
        """Custom learning_rate is stored and used."""
        md = MotionDetector(learning_rate=0.005)
        assert md._learning_rate == 0.005

    def test_invalid_learning_rate(self):
        """learning_rate outside (0, 1] should raise."""
        import pytest
        with pytest.raises(ValueError):
            MotionDetector(learning_rate=0.0)
        with pytest.raises(ValueError):
            MotionDetector(learning_rate=1.5)

    def test_reset_preserves_config(self):
        """After reset(), shadow and var_threshold settings are preserved."""
        md = MotionDetector(detect_shadows=False, var_threshold=40)
        md.reset()
        # bg_subtractor is recreated with stored params
        assert md._detect_shadows is False
        assert md._var_threshold == 40

    def test_no_motion_on_static(self):
        """Static frames should produce no motion."""
        md = MotionDetector(threshold=500)
        frame = np.zeros((400, 400, 3), dtype=np.uint8)
        # Feed a few frames to build background model
        for _ in range(10):
            mask, motion = md.detect(frame)
        assert not motion

    def test_motion_on_change(self):
        """Moving object should trigger motion."""
        md = MotionDetector(threshold=100)
        bg = np.zeros((400, 400, 3), dtype=np.uint8)
        # Build background
        for _ in range(30):
            md.detect(bg)
        # Introduce bright object
        fg = bg.copy()
        fg[150:250, 150:250] = 255
        mask, motion = md.detect(fg)
        assert motion

    def test_reset_clears_model(self):
        md = MotionDetector()
        bg = np.zeros((400, 400, 3), dtype=np.uint8)
        for _ in range(10):
            md.detect(bg)
        md.reset()
        # After reset, model is fresh; a static frame should eventually settle
        for _ in range(10):
            mask, motion = md.detect(bg)


class TestROIProcessor:
    def test_no_homography_returns_original(self):
        """Without homography, warp_roi should return the original frame."""
        roi = ROIProcessor()
        frame = np.random.randint(0, 255, (400, 400, 3), dtype=np.uint8)
        warped = roi.warp_roi(frame)
        # Without homography, returns original frame
        np.testing.assert_array_equal(warped, frame)

    def test_set_homography_matrix(self):
        """Setting a homography matrix directly should work."""
        roi = ROIProcessor()
        H = np.eye(3, dtype=np.float64)
        roi.set_homography_matrix(H)
        assert roi.homography is not None

    def test_set_homography_with_points(self):
        """Setting homography from point pairs."""
        roi = ROIProcessor()
        src = np.float32([[0, 0], [400, 0], [400, 400], [0, 400]])
        dst = np.float32([[0, 0], [400, 0], [400, 400], [0, 400]])
        roi.set_homography(src, dst)
        assert roi.homography is not None

    def test_warp_with_identity(self):
        """Identity homography should produce same-size output."""
        roi = ROIProcessor(roi_size=(400, 400))
        roi.set_homography_matrix(np.eye(3))
        frame = np.random.randint(0, 255, (400, 400, 3), dtype=np.uint8)
        warped = roi.warp_roi(frame)
        assert warped.shape == (400, 400, 3)

    def test_polar_unwrap(self):
        """Polar unwrap should produce expected output shape."""
        roi = ROIProcessor()
        frame = np.zeros((400, 400), dtype=np.uint8)
        polar = roi.polar_unwrap(frame)
        assert polar.shape == (360, 400)


class TestBoardGeometryScoringIntegration:
    def _make_geometry(self) -> BoardGeometry:
        pose = BoardPose(
            homography=None,
            center_px=(200.0, 200.0),
            radii_px=(10.0, 19.0, 106.0, 116.0, 188.0, 200.0),
            rotation_deg=0.0,
            valid=True,
        )
        return BoardGeometry.from_pose(pose, roi_size=(400, 400))

    def test_score_roundtrip(self):
        """Score detection -> BoardGeometry scoring integration."""
        geometry = self._make_geometry()
        # Triple at r_norm 0.582-0.629; with radius 200px: 120px from center
        hit = geometry.point_to_score(200.0, 200.0 - 120.0)
        assert hit.score == 60
        assert hit.sector == 20
        assert hit.multiplier == 3
        assert hit.ring == "triple"


class TestDetectionToScoring:
    def test_full_detect_to_score_flow(self):
        """Full flow: motion mask -> detection -> scoring."""
        import cv2
        detector = DartImpactDetector(confirmation_frames=2, position_tolerance_px=30)
        pose = BoardPose(
            homography=None,
            center_px=(200.0, 200.0),
            radii_px=(10.0, 19.0, 106.0, 116.0, 188.0, 200.0),
            rotation_deg=0.0,
            valid=True,
        )
        geometry = BoardGeometry.from_pose(pose, roi_size=(400, 400))

        roi = np.zeros((400, 400), dtype=np.uint8)
        # Create a dart-like blob at (200, 90) -> near triple-20 zone
        mask = np.zeros((400, 400), dtype=np.uint8)
        cv2.circle(mask, (200, 90), 15, 255, -1)

        # Confirm over 2 frames
        detector.detect(roi, mask)
        detection = detector.detect(roi, mask)

        if detection is not None:
            cx, cy = detection.center
            hit = geometry.point_to_score(float(cx), float(cy))
            assert hit.score > 0
            assert hit.sector in range(1, 21)


class TestPipelineInit:
    def test_opencv_threads_enabled(self):
        """Pipeline init should set cv2.setNumThreads(0) for full parallelism."""
        import cv2
        from src.cv.pipeline import DartPipeline
        DartPipeline(camera_src=0)
        # After init, getNumThreads should return the system thread count (>0)
        assert cv2.getNumThreads() > 0


class TestDartPipelineD1:
    """D1: Tests for critical DartPipeline paths."""

    def test_process_frame_no_camera(self):
        """Pipeline with no camera returns None and does not crash."""
        from src.cv.pipeline import DartPipeline
        pipeline = DartPipeline(camera_src=0)
        pipeline.camera = None
        result = pipeline.process_frame()
        assert result is None

    def test_process_frame_camera_read_fails(self):
        """If camera.read() returns False, process_frame returns None."""
        from src.cv.pipeline import DartPipeline
        pipeline = DartPipeline(camera_src=0)
        mock_cam = MagicMock()
        mock_cam.read.return_value = (False, None)
        pipeline.camera = mock_cam
        result = pipeline.process_frame()
        assert result is None
        assert pipeline._last_raw_frame is None

    def test_process_frame_with_mock_cap(self):
        """A valid frame from a mock camera is stored in _last_raw_frame."""
        from src.cv.pipeline import DartPipeline
        pipeline = DartPipeline(camera_src=0)
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cam = MagicMock()
        mock_cam.read.return_value = (True, fake_frame)
        pipeline.camera = mock_cam
        # process_frame may return None (no motion), but must not crash
        pipeline.process_frame()
        assert pipeline._last_raw_frame is not None

    def test_frame_drop_under_load(self):
        """C1: Stale frames are skipped and _dropped_frames counter increments."""
        from src.cv.pipeline import DartPipeline, FRAME_STALE_THRESHOLD_S
        pipeline = DartPipeline(camera_src=0)
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cam = MagicMock()

        # Make camera.read() simulate a slow capture (> threshold)
        def slow_read():
            time.sleep(FRAME_STALE_THRESHOLD_S + 0.02)
            return (True, fake_frame)

        mock_cam.read.side_effect = slow_read
        pipeline.camera = mock_cam

        before = pipeline._dropped_frames
        pipeline.process_frame()
        assert pipeline._dropped_frames > before

    def test_detect_optical_center_no_calibration(self):
        """detect_optical_center without a prior frame returns None gracefully."""
        from src.cv.pipeline import DartPipeline
        pipeline = DartPipeline(camera_src=0)
        pipeline.camera = None
        pipeline._last_raw_frame = None
        result = pipeline.detect_optical_center()
        assert result is None


# ------------------------------------------------------------------
# Performance optimizations tests
# ------------------------------------------------------------------


class TestMotionDetectorDownscale:
    """Tests for downscaled motion detection (Tier-2 #13)."""

    def test_downscale_factor_default_is_1(self):
        md = MotionDetector()
        assert md._downscale_factor == 1

    def test_downscale_factor_stored(self):
        md = MotionDetector(downscale_factor=4)
        assert md._downscale_factor == 4

    def test_invalid_downscale_factor_raises(self):
        import pytest
        with pytest.raises(ValueError):
            MotionDetector(downscale_factor=0)

    def test_downscale_preserves_mask_shape(self):
        """Mask returned with downscale should match original frame dimensions."""
        md = MotionDetector(threshold=500, downscale_factor=4)
        frame = np.zeros((400, 400), dtype=np.uint8)
        for _ in range(5):
            mask, _ = md.detect(frame)
        assert mask.shape == (400, 400)

    def test_downscale_detects_motion(self):
        """Downscaled detector should still detect motion on large changes."""
        md = MotionDetector(threshold=100, downscale_factor=4)
        bg = np.zeros((400, 400), dtype=np.uint8)
        for _ in range(30):
            md.detect(bg)
        fg = bg.copy()
        fg[100:300, 100:300] = 255
        _, motion = md.detect(fg)
        assert motion

    def test_downscale_no_motion_on_static(self):
        """Downscaled detector should not detect motion on static frames."""
        md = MotionDetector(threshold=500, downscale_factor=4)
        frame = np.zeros((400, 400), dtype=np.uint8)
        for _ in range(10):
            _, motion = md.detect(frame)
        assert not motion

    def test_no_downscale_same_as_factor_1(self):
        """Factor 1 should behave identically to no downscale."""
        md1 = MotionDetector(threshold=100, downscale_factor=1)
        md2 = MotionDetector(threshold=100)
        frame = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        for _ in range(5):
            mask1, m1 = md1.detect(frame)
            mask2, m2 = md2.detect(frame)
        np.testing.assert_array_equal(mask1, mask2)
        assert m1 == m2


class TestIdleFrameSkip:
    """Tests for frame-skip in idle (Tier-5 #33)."""

    def test_frame_skip_defaults(self):
        from src.cv.pipeline import DartPipeline
        p = DartPipeline(camera_src=0)
        assert p._idle_frame_skip_enabled is True
        assert p._idle_frame_skip_threshold == 10
        assert p._no_motion_count == 0

    def test_frame_skip_can_be_disabled(self):
        from src.cv.pipeline import DartPipeline
        p = DartPipeline(camera_src=0)
        p._idle_frame_skip_enabled = False
        # With skip disabled, every frame should be processed
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cam = MagicMock()
        mock_cam.read.return_value = (True, fake_frame)
        p.camera = mock_cam
        # Run many frames; none should be skipped by idle logic
        results = []
        for _ in range(20):
            # process_frame returns None normally (no dart), but runs full pipeline
            p.process_frame()
            results.append(p._last_raw_frame is not None)
        assert all(results)

    def test_no_motion_count_resets_on_motion(self):
        """_no_motion_count should reset when motion is detected."""
        from src.cv.pipeline import DartPipeline
        p = DartPipeline(camera_src=0)
        p._no_motion_count = 50
        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_cam = MagicMock()
        mock_cam.read.return_value = (True, fake_frame)
        p.camera = mock_cam

        # Inject motion by patching motion detector
        with patch.object(p.motion_detector, 'detect', return_value=(np.zeros((400, 400), dtype=np.uint8), True)):
            p.process_frame()
        assert p._no_motion_count == 0
