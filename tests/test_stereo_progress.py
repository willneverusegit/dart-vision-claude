"""Tests for StereoProgressTracker."""
import pytest
from src.web.stereo_progress import StereoProgressTracker


class TestQualityAssessment:
    def test_excellent(self):
        r = StereoProgressTracker.quality_assessment(0.3)
        assert r["quality"] == "excellent"
        assert r["label"] == "Exzellent"

    def test_excellent_boundary(self):
        r = StereoProgressTracker.quality_assessment(0.49)
        assert r["quality"] == "excellent"

    def test_good(self):
        r = StereoProgressTracker.quality_assessment(0.5)
        assert r["quality"] == "good"

    def test_good_upper(self):
        r = StereoProgressTracker.quality_assessment(0.99)
        assert r["quality"] == "good"

    def test_acceptable(self):
        r = StereoProgressTracker.quality_assessment(1.0)
        assert r["quality"] == "acceptable"

    def test_acceptable_upper(self):
        r = StereoProgressTracker.quality_assessment(1.99)
        assert r["quality"] == "acceptable"

    def test_poor(self):
        r = StereoProgressTracker.quality_assessment(2.0)
        assert r["quality"] == "poor"

    def test_poor_high(self):
        r = StereoProgressTracker.quality_assessment(5.0)
        assert r["quality"] == "poor"
        assert "wiederholen" in r["recommendation"]


class TestFrameProgress:
    def test_first_frame(self):
        r = StereoProgressTracker.frame_progress(0, 10, True, False)
        assert r["type"] == "stereo_progress"
        assert r["frame_idx"] == 0
        assert r["total"] == 10
        assert r["detected_a"] is True
        assert r["detected_b"] is False
        assert r["percent"] == 10

    def test_last_frame(self):
        r = StereoProgressTracker.frame_progress(9, 10, True, True)
        assert r["percent"] == 100

    def test_middle_frame(self):
        r = StereoProgressTracker.frame_progress(4, 10, False, False)
        assert r["percent"] == 50

    def test_single_frame(self):
        r = StereoProgressTracker.frame_progress(0, 1, True, True)
        assert r["percent"] == 100


class TestCalibrationResult:
    def test_basic(self):
        r = StereoProgressTracker.calibration_result(0.75, 12, "cam0", "cam1")
        assert r["type"] == "stereo_result"
        assert r["rms"] == 0.75
        assert r["pairs_used"] == 12
        assert r["camera_a"] == "cam0"
        assert r["camera_b"] == "cam1"
        assert r["quality"] == "good"

    def test_rms_rounding(self):
        r = StereoProgressTracker.calibration_result(0.123456, 5, "a", "b")
        assert r["rms"] == 0.1235

    def test_poor_result(self):
        r = StereoProgressTracker.calibration_result(3.5, 5, "a", "b")
        assert r["quality"] == "poor"
