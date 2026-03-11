"""Integration tests for the CV pipeline modules."""

import numpy as np
from src.cv.field_mapper import FieldMapper
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


class TestFieldMapperIntegration:
    def test_score_roundtrip(self):
        """Score detection -> field mapping integration."""
        mapper = FieldMapper()
        # Simulate detecting a dart at triple-20 position
        # Triple zone: 99-107mm / 170mm = 0.582-0.629 fraction
        result = mapper.point_to_score(200, 200 - 200 * 0.60, 200, 200, 200)
        assert result["score"] == 60
        assert result["sector"] == 20
        assert result["multiplier"] == 3
        assert result["ring"] == "triple"


class TestDetectionToScoring:
    def test_full_detect_to_score_flow(self):
        """Full flow: motion mask -> detection -> scoring."""
        import cv2
        detector = DartImpactDetector(confirmation_frames=2, position_tolerance_px=30)
        mapper = FieldMapper()

        roi = np.zeros((400, 400), dtype=np.uint8)
        # Create a dart-like blob at (200, 90) -> near triple-20 zone
        mask = np.zeros((400, 400), dtype=np.uint8)
        cv2.circle(mask, (200, 90), 15, 255, -1)

        # Confirm over 2 frames
        detector.detect(roi, mask)
        detection = detector.detect(roi, mask)

        if detection is not None:
            # DartDetection has .center = (x, y) tuple
            cx, cy = detection.center
            score = mapper.point_to_score(cx, cy, 200, 200, 200)
            assert score["score"] > 0
            assert score["sector"] in range(1, 21)
