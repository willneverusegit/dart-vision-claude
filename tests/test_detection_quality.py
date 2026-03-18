"""Tests for Phase 2: Detection Quality Metrics."""

import math

import cv2
import numpy as np
import pytest

from src.cv.detector import DartDetection
from src.cv.diff_detector import FrameDiffDetector
from src.cv.board_calibration import BoardCalibrationManager


class TestDartDetectionQualityField:
    """DartDetection dataclass has quality field with default 0.0."""

    def test_default_quality(self):
        det = DartDetection(center=(100, 100), area=500.0, confidence=0.8, frame_count=5)
        assert det.quality == 0.0

    def test_explicit_quality(self):
        det = DartDetection(center=(100, 100), area=500.0, confidence=0.8, frame_count=5, quality=0.75)
        assert det.quality == 0.75

    def test_quality_with_tip(self):
        det = DartDetection(center=(100, 100), area=500.0, confidence=0.8, frame_count=5, quality=0.9, tip=(110, 90))
        assert det.quality == 0.9
        assert det.tip == (110, 90)


class TestComputeQuality:
    """Test _compute_quality method on FrameDiffDetector."""

    def setup_method(self):
        self.detector = FrameDiffDetector()

    def _make_elongated_contour(self, w: int, h: int) -> np.ndarray:
        """Create a rectangular contour of given width x height."""
        return np.array([[[0, 0]], [[w, 0]], [[w, h]], [[0, h]]], dtype=np.int32)

    def test_high_quality_dart(self):
        """Elongated contour + good area + tip with distance -> high quality."""
        contour = self._make_elongated_contour(10, 40)  # aspect ~4.0
        area = 400.0
        tip = (5, 0)
        centroid = (5, 20)
        q = self.detector._compute_quality(contour, area, tip, centroid)
        # 0.3 (elongation) + 0.2 (area) + 0.3 (tip) + 0.2 (dist>10) = 1.0
        assert q == 1.0

    def test_no_tip(self):
        """No tip detected -> max 0.5."""
        contour = self._make_elongated_contour(10, 40)
        area = 400.0
        q = self.detector._compute_quality(contour, area, None, (5, 20))
        # 0.3 (elongation) + 0.2 (area) = 0.5
        assert q == 0.5

    def test_circular_contour(self):
        """Nearly circular contour -> low elongation score."""
        contour = self._make_elongated_contour(20, 20)
        area = 400.0
        q = self.detector._compute_quality(contour, area, None, (10, 10))
        # 0.0 (aspect=1.0) + 0.2 (area) = 0.2
        assert q == 0.2

    def test_small_area(self):
        """Area below 100 but above 30 -> partial area score."""
        contour = self._make_elongated_contour(5, 15)
        area = 50.0
        q = self.detector._compute_quality(contour, area, None, (2, 7))
        # 0.3 (elongation, aspect=3.0) + 0.1 (area 30-5000) = 0.4
        assert q == 0.4

    def test_tip_close_to_centroid(self):
        """Tip very close to centroid -> partial tip distance score."""
        contour = self._make_elongated_contour(10, 40)
        area = 400.0
        tip = (5, 14)
        centroid = (5, 20)
        q = self.detector._compute_quality(contour, area, tip, centroid)
        # 0.3 (elongation) + 0.2 (area) + 0.3 (tip) + 0.1 (dist ~6, >5) = 0.9
        assert q == 0.9

    def test_capped_at_1(self):
        """Quality never exceeds 1.0."""
        contour = self._make_elongated_contour(5, 50)
        area = 200.0
        tip = (2, 0)
        centroid = (2, 25)
        q = self.detector._compute_quality(contour, area, tip, centroid)
        assert q <= 1.0


class TestViewingAngleQuality:
    """Test get_viewing_angle_quality on BoardCalibrationManager."""

    def test_no_calibration_returns_zero(self):
        """Without calibration, viewing angle quality is 0.0."""
        bcm = BoardCalibrationManager(config_path="nonexistent.yaml")
        assert bcm.get_viewing_angle_quality() == 0.0

    def test_valid_homography_returns_above_threshold(self):
        """With a valid homography, quality should be > 0.3."""
        bcm = BoardCalibrationManager(config_path="nonexistent.yaml")
        # Monkey-patch get_homography to return an identity-like matrix
        H = np.eye(3, dtype=np.float64)
        bcm.get_homography = lambda: H
        q = bcm.get_viewing_angle_quality()
        assert q > 0.3
        assert q <= 1.0

    def test_frontal_homography_high_quality(self):
        """Near-identity homography (frontal) should give high quality."""
        bcm = BoardCalibrationManager(config_path="nonexistent.yaml")
        H = np.eye(3, dtype=np.float64) * 1.0  # det = 1.0, log10 = 0
        bcm.get_homography = lambda: H
        q = bcm.get_viewing_angle_quality()
        # log10(1) = 0, mapped: 0.3 + 0.7*(0+2)/4 = 0.3 + 0.35 = 0.65
        assert abs(q - 0.65) < 0.01

    def test_scaled_homography(self):
        """Homography with large determinant -> higher quality."""
        bcm = BoardCalibrationManager(config_path="nonexistent.yaml")
        H = np.eye(3, dtype=np.float64) * 10.0  # det = 1000, log10 = 3
        bcm.get_homography = lambda: H
        q = bcm.get_viewing_angle_quality()
        # log10(1000) = 3, mapped: 0.3 + 0.7*min(1, (3+2)/4) = 0.3 + 0.7*1.0 = 1.0
        assert q == 1.0


class TestVotingFallbackWithQuality:
    """Test that _voting_fallback uses quality-weighted confidences."""

    def _make_pipeline(self):
        from src.cv.multi_camera import MultiCameraPipeline
        mcp = MultiCameraPipeline(camera_configs=[])
        mcp._viewing_angle_qualities = {}
        return mcp

    def test_quality_affects_voting(self):
        """Higher quality detection should be preferred."""
        mcp = self._make_pipeline()
        mcp._viewing_angle_qualities = {"cam1": 1.0, "cam2": 1.0}

        det1 = DartDetection(center=(100, 100), area=500, confidence=0.8, frame_count=5, quality=0.2)
        det2 = DartDetection(center=(150, 150), area=400, confidence=0.7, frame_count=5, quality=0.9)

        entries = [
            {"camera_id": "cam1", "score_result": {"total_score": 20}, "detection": det1},
            {"camera_id": "cam2", "score_result": {"total_score": 60}, "detection": det2},
        ]

        result = mcp._voting_fallback(entries)
        # cam1 weight: 0.8 * 0.2 * 1.0 = 0.16
        # cam2 weight: 0.7 * 0.9 * 1.0 = 0.63
        # weighted = (20*0.16 + 60*0.63) / (0.16+0.63) = (3.2 + 37.8) / 0.79 = 51.9
        assert result["total_score"] == 52  # round(51.9)

    def test_vaq_affects_voting(self):
        """Lower viewing angle quality should reduce weight."""
        mcp = self._make_pipeline()
        mcp._viewing_angle_qualities = {"cam1": 1.0, "cam2": 0.4}

        det1 = DartDetection(center=(100, 100), area=500, confidence=0.8, frame_count=5, quality=0.5)
        det2 = DartDetection(center=(150, 150), area=400, confidence=0.8, frame_count=5, quality=0.5)

        entries = [
            {"camera_id": "cam1", "score_result": {"total_score": 20}, "detection": det1},
            {"camera_id": "cam2", "score_result": {"total_score": 60}, "detection": det2},
        ]

        result = mcp._voting_fallback(entries)
        # cam1 weight: 0.8 * 0.5 * 1.0 = 0.4
        # cam2 weight: 0.8 * 0.5 * 0.4 = 0.16
        # weighted = (20*0.4 + 60*0.16) / (0.4+0.16) = (8 + 9.6) / 0.56 = 31.43
        assert result["total_score"] == 31

    def test_zero_quality_uses_floor(self):
        """Quality=0 should use floor of 0.1, not zero weight."""
        mcp = self._make_pipeline()
        mcp._viewing_angle_qualities = {"cam1": 1.0}

        det1 = DartDetection(center=(100, 100), area=500, confidence=0.8, frame_count=5, quality=0.0)

        entries = [
            {"camera_id": "cam1", "score_result": {"total_score": 20}, "detection": det1},
        ]

        # Should not crash - quality floored to 0.1
        result = mcp._voting_fallback(entries)
        assert "source" in result
