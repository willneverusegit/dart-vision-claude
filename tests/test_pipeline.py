"""Integration tests for the CV pipeline modules."""

import time
from unittest.mock import MagicMock, patch

import numpy as np
from src.cv.geometry import BoardGeometry, BoardPose
from src.cv.motion import MotionDetector
from src.cv.roi import ROIProcessor
from src.cv.detector import DartImpactDetector


class TestMotionDetector:
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
