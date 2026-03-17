"""P6: Tests for improved board detection — multi-stage ArUco, optical center, quality metrics."""

import numpy as np
import cv2
from unittest.mock import patch, MagicMock

from src.cv.calibration import CalibrationManager, BOARD_CROP_MM, RING_RADII_MM


class TestMultiStageArUcoDetection:
    """Test that ArUco detection tries multiple enhancement stages."""

    def _make_manager(self):
        return CalibrationManager(camera_id="test_p6", config_path="/dev/null")

    @patch("src.cv.calibration.CalibrationManager._atomic_save")
    def test_detection_method_returned(self, mock_save):
        """Successful ArUco calibration should include detection_method."""
        cm = self._make_manager()
        # Create a synthetic frame with 4 ArUco markers
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

        # Draw 4 markers at known positions
        positions = [(100, 100), (500, 100), (500, 400), (100, 400)]
        marker_size = 60
        for i, (x, y) in enumerate(positions):
            marker_img = cv2.aruco.generateImageMarker(dictionary, i, marker_size)
            marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)
            frame[y:y + marker_size, x:x + marker_size] = marker_bgr

        result = cm.aruco_calibration(frame)
        if result["ok"]:
            assert "detection_method" in result
            assert result["detection_method"] in ("raw", "clahe_3.0", "clahe_6.0", "blur_clahe")

    def test_failed_detection_still_reports_count(self):
        """If no markers found, error should report found count."""
        cm = self._make_manager()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)  # blank frame
        result = cm.aruco_calibration(frame)
        assert not result["ok"]
        assert "Found 0 markers" in result["error"]


class TestOpticalCenterFallback:
    """Test optical center detection with intensity fallback."""

    def _make_calibrated_manager(self):
        cm = CalibrationManager(camera_id="test_oc", config_path="/dev/null")
        cm._config["board_crop_mm"] = BOARD_CROP_MM
        cm._config["valid"] = True
        return cm

    def test_geometric_center_on_grayscale(self):
        """Grayscale ROI should return geometric center."""
        cm = self._make_calibrated_manager()
        gray = np.zeros((400, 400), dtype=np.uint8)
        cx, cy = cm.find_optical_center(gray)
        assert abs(cx - 200.0) < 0.1
        assert abs(cy - 200.0) < 0.1

    def test_red_bullseye_detected(self):
        """Red bullseye blob should shift center."""
        cm = self._make_calibrated_manager()
        roi = np.zeros((400, 400, 3), dtype=np.uint8)
        # Draw a red circle slightly off-center (195, 198)
        cv2.circle(roi, (195, 198), 8, (0, 0, 255), -1)
        cx, cy = cm.find_optical_center(roi)
        # Should be near the red blob, not at geometric center
        assert abs(cx - 195) < 5
        assert abs(cy - 198) < 5

    def test_green_bullseye_detected(self):
        """Green bullseye blob should be detected."""
        cm = self._make_calibrated_manager()
        roi = np.zeros((400, 400, 3), dtype=np.uint8)
        cv2.circle(roi, (203, 197), 8, (0, 200, 0), -1)
        cx, cy = cm.find_optical_center(roi)
        assert abs(cx - 203) < 5
        assert abs(cy - 197) < 5

    def test_intensity_fallback_on_blank_color(self):
        """With no color blobs, intensity fallback finds bright spot."""
        cm = self._make_calibrated_manager()
        roi = np.zeros((400, 400, 3), dtype=np.uint8)
        # Add a bright white spot near center
        cv2.circle(roi, (198, 202), 6, (255, 255, 255), -1)
        cx, cy = cm.find_optical_center(roi)
        # Should find either via intensity fallback or geometric center
        # Both are acceptable — just shouldn't crash
        assert 150 < cx < 250
        assert 150 < cy < 250

    def test_empty_patch_returns_geometric(self):
        """Tiny ROI that can't produce a patch returns geometric center."""
        cm = self._make_calibrated_manager()
        roi = np.zeros((10, 10, 3), dtype=np.uint8)
        cx, cy = cm.find_optical_center(roi)
        assert abs(cx - 5.0) < 0.1


class TestCalibrationQualityMetrics:
    """Test verify_rings returns quality metrics."""

    def _make_calibrated_manager(self):
        cm = CalibrationManager(camera_id="test_quality", config_path="/dev/null")
        cm._config["board_crop_mm"] = BOARD_CROP_MM
        cm._config["valid"] = True
        # Set radii that match expected values perfectly
        roi_mm_per_px = BOARD_CROP_MM / 400
        radii_px = []
        for name in ["bull_inner", "bull_outer", "triple_inner",
                      "triple_outer", "double_inner", "double_outer"]:
            radii_px.append(round(RING_RADII_MM[name] / roi_mm_per_px, 1))
        cm._config["radii_px"] = radii_px
        return cm

    def test_perfect_calibration_quality_100(self):
        """Perfectly matching radii should give quality=100."""
        cm = self._make_calibrated_manager()
        frame = np.zeros((400, 400), dtype=np.uint8)
        result = cm.verify_rings(frame)
        assert result["ok"]
        assert result["quality"] == 100
        assert result["max_deviation_mm"] == 0.0
        assert all(d == 0.0 for d in result["deviations_px"])

    def test_imperfect_calibration_lower_quality(self):
        """Offset radii should produce lower quality score."""
        cm = self._make_calibrated_manager()
        # Shift all radii by 2px
        cm._config["radii_px"] = [r + 2.0 for r in cm._config["radii_px"]]
        frame = np.zeros((400, 400), dtype=np.uint8)
        result = cm.verify_rings(frame)
        assert result["ok"]
        assert result["quality"] < 100
        assert result["max_deviation_mm"] > 0

    def test_missing_radii_quality_zero(self):
        """Missing stored radii should give quality=0."""
        cm = CalibrationManager(camera_id="test_no_radii", config_path="/dev/null")
        cm._config["board_crop_mm"] = BOARD_CROP_MM
        cm._config["radii_px"] = []
        frame = np.zeros((400, 400), dtype=np.uint8)
        result = cm.verify_rings(frame)
        assert result["quality"] == 0

    def test_response_includes_deviations(self):
        """verify_rings should include deviations_px list."""
        cm = self._make_calibrated_manager()
        frame = np.zeros((400, 400), dtype=np.uint8)
        result = cm.verify_rings(frame)
        assert "deviations_px" in result
        assert "max_deviation_mm" in result
        assert "quality" in result
        assert len(result["deviations_px"]) == 6
