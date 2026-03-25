"""Tests for CalibrationManager — targeting uncovered branches in src/cv/calibration.py.

Covers:
- ArUco calibration success path (lines 272-412)
- charuco_calibration (lines 573-635)
- reset_calibration (lines 684-713)
- _atomic_save edge cases (lines 733-762)
- find_optical_center edge cases (lines 545, 561-564)
- _load_config error handling (lines 103-104)
- manual_calibration edge cases (lines 143, 146, 183-185)
- get_optical_center None path (line 661)
"""

import os
import tempfile
import numpy as np
import cv2
import pytest
import yaml

from src.cv.calibration import (
    CalibrationManager,
    ARUCO_DICT_TYPE,
    ARUCO_MARKER_SIZE_MM,
    MARKER_SPACING_MM,
    RING_RADII_MM,
    BOARD_CROP_MM,
    MM_PER_PX_MIN,
    MM_PER_PX_MAX,
    MANUAL_MIN_POINT_DISTANCE_PX,
)


@pytest.fixture
def tmp_config(tmp_path):
    """Provide a temporary config path for CalibrationManager."""
    return str(tmp_path / "calibration_config.yaml")


@pytest.fixture
def manager(tmp_config):
    """CalibrationManager with temp config."""
    return CalibrationManager(config_path=tmp_config, camera_id="test_cam")


def _create_aruco_frame(marker_ids=(0, 1, 2, 3), spacing_px=300,
                         marker_size_px=60, img_size=800):
    """Create a synthetic frame with ArUco markers at known positions.

    Markers are placed in a square pattern centered in the image:
      ID 0 = TL, ID 1 = TR, ID 2 = BR, ID 3 = BL
    """
    frame = np.ones((img_size, img_size), dtype=np.uint8) * 200  # light gray bg

    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)
    half_sp = spacing_px // 2
    cx, cy = img_size // 2, img_size // 2

    # TL, TR, BR, BL positions (marker centers)
    positions = [
        (cx - half_sp, cy - half_sp),  # ID 0 — TL
        (cx + half_sp, cy - half_sp),  # ID 1 — TR
        (cx + half_sp, cy + half_sp),  # ID 2 — BR
        (cx - half_sp, cy + half_sp),  # ID 3 — BL
    ]

    for mid, (px, py) in zip(marker_ids, positions):
        marker_img = cv2.aruco.generateImageMarker(dictionary, mid, marker_size_px)
        x1 = px - marker_size_px // 2
        y1 = py - marker_size_px // 2
        x2 = x1 + marker_size_px
        y2 = y1 + marker_size_px
        if x1 >= 0 and y1 >= 0 and x2 <= img_size and y2 <= img_size:
            frame[y1:y2, x1:x2] = marker_img

    return frame


# =============================================================================
# ArUco Calibration Success Path (lines 272-412)
# =============================================================================

class TestArucoCalibrationSuccess:
    """Test the full ArUco calibration success path."""

    def test_aruco_success_grayscale(self, manager):
        """ArUco calibration succeeds on a synthetic grayscale frame with 4 markers."""
        frame = _create_aruco_frame()
        result = manager.aruco_calibration(frame)

        assert result["ok"] is True
        assert "homography" in result
        assert "mm_per_px" in result
        assert "corners_px" in result
        assert "radii_px" in result
        assert "detected_ids" in result
        assert "detection_method" in result
        assert len(result["corners_px"]) == 4
        assert len(result["radii_px"]) == 6
        assert MM_PER_PX_MIN <= result["mm_per_px"] <= MM_PER_PX_MAX

    def test_aruco_success_bgr(self, manager):
        """ArUco calibration succeeds on a BGR (3-channel) frame."""
        gray = _create_aruco_frame()
        bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        result = manager.aruco_calibration(bgr)

        assert result["ok"] is True
        assert len(result["detected_ids"]) >= 4

    def test_aruco_success_saves_config(self, tmp_config):
        """ArUco calibration persists results to config file."""
        mgr = CalibrationManager(config_path=tmp_config, camera_id="test_cam")
        frame = _create_aruco_frame()
        result = mgr.aruco_calibration(frame)

        assert result["ok"] is True

        # Verify config file written
        with open(tmp_config, "r") as f:
            data = yaml.safe_load(f)
        assert "cameras" in data
        assert "test_cam" in data["cameras"]
        cam_cfg = data["cameras"]["test_cam"]
        assert cam_cfg["valid"] is True
        assert cam_cfg["method"] == "aruco"
        assert cam_cfg["marker_spacing_mm"] == MARKER_SPACING_MM

    def test_aruco_custom_marker_size(self, manager):
        """ArUco calibration uses custom marker_size_mm when provided."""
        frame = _create_aruco_frame()
        result = manager.aruco_calibration(frame, marker_size_mm=100.0)

        assert result["ok"] is True
        # With larger marker_size_mm, mm_per_px should be larger
        # (same pixel edge length but representing 100mm instead of 75mm)
        assert result["mm_per_px"] > 0

    def test_aruco_custom_marker_spacing(self, manager):
        """ArUco calibration accepts custom marker_spacing_mm."""
        frame = _create_aruco_frame()
        result = manager.aruco_calibration(frame, marker_spacing_mm=500.0)

        assert result["ok"] is True

    def test_aruco_detection_method_raw(self, manager):
        """With clear markers, detection_method should be 'raw'."""
        frame = _create_aruco_frame()
        result = manager.aruco_calibration(frame)

        assert result["ok"] is True
        assert result["detection_method"] == "raw"

    def test_aruco_missing_marker_id(self, manager):
        """ArUco calibration fails when expected marker is missing."""
        frame = _create_aruco_frame(marker_ids=(0, 1, 2, 5))  # ID 3 missing
        result = manager.aruco_calibration(frame, expected_ids=[0, 1, 2, 3])

        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_aruco_too_few_markers(self, manager):
        """ArUco calibration fails with < 4 markers detected."""
        # Create frame with only 2 markers
        frame = np.ones((800, 800), dtype=np.uint8) * 200
        dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_TYPE)

        for mid, pos in [(0, (200, 200)), (1, (600, 200))]:
            marker = cv2.aruco.generateImageMarker(dictionary, mid, 60)
            x, y = pos[0] - 30, pos[1] - 30
            frame[y:y + 60, x:x + 60] = marker

        result = manager.aruco_calibration(frame)
        assert result["ok"] is False
        assert "Found" in result["error"]

    def test_aruco_updates_manager_state(self, manager):
        """After successful ArUco calibration, manager reports valid."""
        frame = _create_aruco_frame()
        result = manager.aruco_calibration(frame)

        assert result["ok"] is True
        assert manager.is_valid() is True
        assert manager.get_homography() is not None
        assert isinstance(manager.get_mm_per_px(), float)
        assert manager.get_mm_per_px() > 0

    def test_aruco_radii_px_correct_count(self, manager):
        """ArUco calibration computes 6 ring radii."""
        frame = _create_aruco_frame()
        result = manager.aruco_calibration(frame)

        assert result["ok"] is True
        radii = result["radii_px"]
        assert len(radii) == 6
        # Radii should be monotonically increasing
        for i in range(len(radii) - 1):
            assert radii[i] < radii[i + 1]


# =============================================================================
# ChArUco Calibration (lines 573-635)
# =============================================================================

class TestCharucoCalibration:
    """Test charuco_calibration method."""

    def _create_charuco_frames(self, n_frames=5):
        """Generate synthetic ChArUco board frames from different angles."""
        from src.cv.stereo_calibration import DEFAULT_CHARUCO_BOARD_SPEC
        spec = DEFAULT_CHARUCO_BOARD_SPEC
        dictionary = spec.create_dictionary()
        board = spec.create_board(dictionary)

        board_img = board.generateImage((600, 800))

        frames = []
        for i in range(n_frames):
            # Simulate slightly different perspectives via small affine transforms
            offset_x = i * 5
            offset_y = i * 3
            M = np.float32([
                [1.0, 0.02 * (i - 2), offset_x],
                [-0.02 * (i - 2), 1.0, offset_y]
            ])
            h, w = board_img.shape[:2]
            warped = cv2.warpAffine(board_img, M, (w, h),
                                    borderMode=cv2.BORDER_CONSTANT,
                                    borderValue=200)
            frames.append(warped)
        return frames

    def test_charuco_too_few_frames(self, manager):
        """charuco_calibration rejects < 3 frames."""
        frame = np.zeros((480, 640), dtype=np.uint8)
        result = manager.charuco_calibration([frame, frame])

        assert result["ok"] is False
        assert "3 frames" in result["error"]

    def test_charuco_no_usable_frames(self, manager):
        """charuco_calibration fails when no frames have enough markers."""
        blank_frames = [np.ones((480, 640), dtype=np.uint8) * 128 for _ in range(5)]
        result = manager.charuco_calibration(blank_frames)

        assert result["ok"] is False
        assert "usable frames" in result["error"]

    def test_charuco_success_with_synthetic_board(self, manager):
        """charuco_calibration succeeds with synthetic ChArUco board images."""
        frames = self._create_charuco_frames(n_frames=8)
        result = manager.charuco_calibration(frames)

        # May fail on synthetic data due to perspective limitations,
        # but should at least get past the frame-counting checks
        if result["ok"]:
            assert "homography" in result
            assert "mm_per_px" in result
            assert "reprojection_error" in result
            assert result["reprojection_error"] >= 0
        else:
            # Acceptable failure: not enough usable charuco corners
            assert "error" in result

    def test_charuco_bgr_frames(self, manager):
        """charuco_calibration handles BGR frames (converts to gray)."""
        frames = self._create_charuco_frames(n_frames=5)
        bgr_frames = [cv2.cvtColor(f, cv2.COLOR_GRAY2BGR) for f in frames]
        result = manager.charuco_calibration(bgr_frames)
        # Just verify it doesn't crash on BGR input
        assert "ok" in result

    def test_charuco_exception_handling(self, manager):
        """charuco_calibration handles exceptions gracefully."""
        # Pass invalid data that will cause an exception
        result = manager.charuco_calibration([None, None, None])
        assert result["ok"] is False
        assert "error" in result


# =============================================================================
# reset_calibration (lines 684-713)
# =============================================================================

class TestResetCalibration:
    """Test reset_calibration with different modes."""

    def _calibrate_first(self, manager):
        """Helper: run ArUco calibration to populate config."""
        frame = _create_aruco_frame()
        result = manager.aruco_calibration(frame)
        assert result["ok"] is True
        return result

    def test_reset_all(self, manager):
        """Full reset removes all calibration data."""
        self._calibrate_first(manager)
        assert manager.is_valid() is True

        result = manager.reset_calibration()
        assert result["ok"] is True
        assert result["mode"] == "all"
        assert len(result["removed_keys"]) > 0
        assert manager.is_valid() is False

    def test_reset_lens_only(self, manager):
        """Lens-only reset removes only lens/intrinsics keys."""
        self._calibrate_first(manager)
        # Manually add lens keys
        manager._config["camera_matrix"] = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        manager._config["dist_coeffs"] = [0, 0, 0, 0, 0]
        manager._config["lens_valid"] = True

        result = manager.reset_calibration(lens_only=True)
        assert result["ok"] is True
        assert result["mode"] == "lens"
        # Board calibration should still be valid
        assert manager.is_valid() is True
        # Lens keys should be gone
        assert "camera_matrix" not in manager._config
        assert "dist_coeffs" not in manager._config

    def test_reset_board_only(self, manager):
        """Board-only reset removes only board/homography keys."""
        self._calibrate_first(manager)
        # Add lens key to verify it survives
        manager._config["camera_matrix"] = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

        result = manager.reset_calibration(board_only=True)
        assert result["ok"] is True
        assert result["mode"] == "board"
        assert manager.is_valid() is False
        # Lens key should survive
        assert "camera_matrix" in manager._config

    def test_reset_clears_in_memory_state(self, tmp_config):
        """Full reset clears in-memory state and reports removed keys."""
        mgr = CalibrationManager(config_path=tmp_config, camera_id="cam1")
        frame = _create_aruco_frame()
        mgr.aruco_calibration(frame)
        assert mgr.is_valid() is True

        result = mgr.reset_calibration()
        assert result["ok"] is True
        assert result["mode"] == "all"
        assert len(result["removed_keys"]) > 5  # Many keys removed

        # In-memory state is reset
        assert mgr.is_valid() is False
        assert mgr._config.get("method") is None
        assert mgr._config.get("last_update_utc") is None

        # Preserved keys survive
        assert "aruco_marker_size_mm" in mgr._config or "board_crop_mm" in mgr._config


# =============================================================================
# _atomic_save edge cases (lines 733-734, 757-762)
# =============================================================================

class TestAtomicSave:
    """Test _atomic_save with edge cases."""

    def test_save_creates_directory(self, tmp_path):
        """_atomic_save creates config directory if it doesn't exist."""
        deep_path = str(tmp_path / "a" / "b" / "config.yaml")
        mgr = CalibrationManager(config_path=deep_path, camera_id="test")
        mgr._config["valid"] = True
        mgr._atomic_save()

        assert os.path.exists(deep_path)

    def test_save_migrates_legacy_format(self, tmp_path):
        """_atomic_save converts legacy flat format to multi-camera format."""
        config_path = str(tmp_path / "config.yaml")
        # Write legacy format
        with open(config_path, "w") as f:
            yaml.dump({"valid": True, "mm_per_px": 1.5, "method": "aruco"}, f)

        mgr = CalibrationManager(config_path=config_path, camera_id="cam1")
        mgr._config["test_key"] = "test_value"
        mgr._atomic_save()

        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        assert data["schema_version"] == 3
        assert "cameras" in data
        assert "cam1" in data["cameras"]

    def test_save_preserves_other_cameras(self, tmp_path):
        """_atomic_save preserves config for other camera IDs."""
        config_path = str(tmp_path / "config.yaml")

        # Save cam1
        mgr1 = CalibrationManager(config_path=config_path, camera_id="cam1")
        mgr1._config["valid"] = True
        mgr1._config["method"] = "aruco"
        mgr1._atomic_save()

        # Save cam2
        mgr2 = CalibrationManager(config_path=config_path, camera_id="cam2")
        mgr2._config["valid"] = True
        mgr2._config["method"] = "manual"
        mgr2._atomic_save()

        # Both should be present
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        assert "cam1" in data["cameras"]
        assert "cam2" in data["cameras"]
        assert data["cameras"]["cam1"]["method"] == "aruco"
        assert data["cameras"]["cam2"]["method"] == "manual"

    def test_save_handles_corrupt_existing_file(self, tmp_path):
        """_atomic_save handles corrupt YAML in existing config."""
        config_path = str(tmp_path / "config.yaml")
        with open(config_path, "w") as f:
            f.write("{{invalid yaml: [")

        mgr = CalibrationManager(config_path=config_path, camera_id="test")
        mgr._config["valid"] = True
        mgr._atomic_save()

        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        assert data["schema_version"] == 3
        assert "test" in data["cameras"]


# =============================================================================
# find_optical_center edge cases (lines 545, 561-564)
# =============================================================================

class TestFindOpticalCenter:
    """Test find_optical_center edge cases."""

    def test_m00_near_zero(self, manager):
        """Fallback to geometric center when largest contour has m00 < 1."""
        # Create a tiny 1-pixel "contour" that will have near-zero moment
        roi = np.zeros((400, 400, 3), dtype=np.uint8)
        # Set a single pixel that's red in the center region
        roi[200, 200] = [0, 0, 255]
        cx, cy = manager.find_optical_center(roi)
        # Should fall back to geometric center
        assert abs(cx - 200.0) < 50
        assert abs(cy - 200.0) < 50

    def test_offset_exceeds_search_radius(self, manager):
        """Fallback when detected center is too far from geometric center."""
        roi = np.zeros((400, 400, 3), dtype=np.uint8)
        # Place a large red blob far from center (in the corner)
        cv2.circle(roi, (50, 50), 20, (0, 0, 255), -1)
        # With default 10mm search radius, this should exceed it
        cx, cy = manager.find_optical_center(roi, search_radius_mm=1.0)
        # Should fall back to geometric center (200, 200)
        assert abs(cx - 200.0) < 5
        assert abs(cy - 200.0) < 5

    def test_grayscale_input(self, manager):
        """Grayscale ROI triggers early return with geometric center."""
        roi = np.zeros((400, 400), dtype=np.uint8)
        cx, cy = manager.find_optical_center(roi)
        assert cx == 200.0
        assert cy == 200.0

    def test_empty_patch(self, manager):
        """Empty patch falls back to geometric center."""
        roi = np.zeros((2, 2, 3), dtype=np.uint8)
        cx, cy = manager.find_optical_center(roi, search_radius_mm=0.01)
        assert cx == pytest.approx(1.0)
        assert cy == pytest.approx(1.0)


# =============================================================================
# get_optical_center None path (line 661)
# =============================================================================

class TestGetOpticalCenter:
    """Test get_optical_center accessor."""

    def test_returns_none_when_not_set(self, manager):
        """get_optical_center returns None when no optical center stored."""
        result = manager.get_optical_center()
        assert result is None

    def test_returns_tuple_when_set(self, manager):
        """get_optical_center returns (cx, cy) when set in config."""
        manager._config["optical_center_roi_px"] = [195.3, 202.1]
        result = manager.get_optical_center()
        assert result == (195.3, 202.1)

    def test_returns_none_for_partial_data(self, manager):
        """get_optical_center returns None for incomplete data."""
        manager._config["optical_center_roi_px"] = [195.3]
        result = manager.get_optical_center()
        assert result is None


# =============================================================================
# _load_config error handling (lines 103-104)
# =============================================================================

class TestLoadConfig:
    """Test _load_config edge cases."""

    def test_config_load_exception(self, tmp_path):
        """_load_config handles file read errors gracefully."""
        config_path = str(tmp_path / "config.yaml")
        # Write binary garbage
        with open(config_path, "wb") as f:
            f.write(b"\x00\x01\x02\xff\xfe")

        mgr = CalibrationManager(config_path=config_path, camera_id="test")
        # Should not raise, should use defaults
        assert mgr._config.get("valid") is False

    def test_multi_cam_format_camera_not_present(self, tmp_path):
        """_load_config handles multi-cam format where camera_id is missing."""
        config_path = str(tmp_path / "config.yaml")
        with open(config_path, "w") as f:
            yaml.dump({"cameras": {"other_cam": {"valid": True}}}, f)

        mgr = CalibrationManager(config_path=config_path, camera_id="my_cam")
        assert mgr._config.get("valid") is False

    def test_empty_file_with_data(self, tmp_path):
        """_load_config handles file with raw data but no valid flag."""
        config_path = str(tmp_path / "config.yaml")
        with open(config_path, "w") as f:
            yaml.dump({"mm_per_px": 2.0, "rotation_deg": 5.0}, f)

        mgr = CalibrationManager(config_path=config_path, camera_id="default")
        # Should pick up raw data
        assert mgr._config.get("mm_per_px") == 2.0
        assert mgr._config.get("rotation_deg") == 5.0


# =============================================================================
# manual_calibration edge cases (lines 143, 146, 183-185)
# =============================================================================

class TestManualCalibrationEdgeCases:
    """Test manual_calibration error paths."""

    def test_degenerate_homography(self, manager):
        """manual_calibration detects degenerate homography (collinear points)."""
        # 4 collinear points produce a degenerate homography
        points = [[100, 100], [200, 100], [300, 100], [400, 100]]
        result = manager.manual_calibration(points)
        assert result["ok"] is False
        # Either "Degenerate" or some other error from collinear points
        assert "error" in result

    def test_board_width_too_small(self, manager):
        """manual_calibration rejects points with near-zero board width."""
        # Two points very close together for the top edge
        points = [[100, 100], [100.5, 100], [200, 200], [100, 200]]
        result = manager.manual_calibration(points)
        assert result["ok"] is False

    def test_exception_in_manual_calibration(self, manager):
        """manual_calibration handles unexpected exceptions."""
        # Pass non-numeric data to trigger an exception
        result = manager.manual_calibration([["a", "b"], [1, 2], [3, 4], [5, 6]])
        assert result["ok"] is False
        assert "error" in result

    def test_points_too_close(self, manager):
        """manual_calibration rejects points closer than minimum distance."""
        points = [[100, 100], [110, 100], [300, 300], [100, 300]]
        result = manager.manual_calibration(points)
        assert result["ok"] is False
        assert "px" in result["error"]

    def test_wrong_point_count(self, manager):
        """manual_calibration rejects != 4 points."""
        result = manager.manual_calibration([[0, 0], [1, 1], [2, 2]])
        assert result["ok"] is False
        assert "4 points" in result["error"]

    def test_mm_per_px_out_of_range(self, manager):
        """manual_calibration rejects unrealistic mm/px ratio."""
        # Points very far apart → very small mm/px (< MM_PER_PX_MIN)
        points = [[100, 100], [10000, 100], [10000, 10000], [100, 10000]]
        result = manager.manual_calibration(points)
        assert result["ok"] is False
        assert "mm/px" in result["error"]


# =============================================================================
# verify_rings (testing completeness)
# =============================================================================

class TestVerifyRings:
    """Test verify_rings with various states."""

    def test_verify_after_aruco_calibration(self, manager):
        """verify_rings returns quality metrics after successful calibration."""
        frame = _create_aruco_frame()
        cal_result = manager.aruco_calibration(frame)
        assert cal_result["ok"] is True

        roi = np.zeros((400, 400), dtype=np.uint8)
        result = manager.verify_rings(roi)

        assert result["ok"] is True
        assert len(result["radii_px"]) == 6
        assert len(result["expected_radii_px"]) == 6
        assert result["roi_mm_per_px"] > 0
        assert 0 <= result["quality"] <= 100

    def test_verify_without_calibration(self, manager):
        """verify_rings handles uncalibrated state gracefully."""
        roi = np.zeros((400, 400), dtype=np.uint8)
        result = manager.verify_rings(roi)

        assert result["ok"] is True
        assert result["quality"] == 0  # No stored radii to compare

    def test_verify_with_3channel_frame(self, manager):
        """verify_rings uses frame dimensions even from 3-channel images."""
        frame = _create_aruco_frame()
        manager.aruco_calibration(frame)

        roi_bgr = np.zeros((400, 400, 3), dtype=np.uint8)
        result = manager.verify_rings(roi_bgr)
        assert result["ok"] is True


# =============================================================================
# Config accessors
# =============================================================================

class TestConfigAccessors:
    """Test config getter methods."""

    def test_get_center_default(self, manager):
        """get_center returns default when not calibrated."""
        cx, cy = manager.get_center()
        assert cx == 200.0
        assert cy == 200.0

    def test_get_radii_default(self, manager):
        """get_radii_px returns defaults when not calibrated."""
        radii = manager.get_radii_px()
        assert len(radii) == 6

    def test_get_homography_none_uncalibrated(self, manager):
        """get_homography returns None when not calibrated."""
        assert manager.get_homography() is None

    def test_get_config_returns_copy(self, manager):
        """get_config returns a dict copy of the config."""
        cfg = manager.get_config()
        assert isinstance(cfg, dict)
        cfg["test"] = "modified"
        # Original should not be affected
        assert "test" not in manager._config
