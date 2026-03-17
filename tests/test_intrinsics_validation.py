"""Tests for BoardCalibrationManager.has_valid_intrinsics (P31)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cv.board_calibration import BoardCalibrationManager


@pytest.fixture
def bcm(tmp_path):
    """Create a BoardCalibrationManager with a temp config."""
    config = tmp_path / "calibration_config.yaml"
    config.write_text(
        "camera_matrix: null\ndist_coeffs: null\nhomography: null\n"
        "ring_radii_px: []\noptical_center_roi_px: null\n"
        "schema_version: 2\n"
    )
    return BoardCalibrationManager(config_path=str(config), camera_id="test_cam")


class TestHasValidIntrinsics:
    """Test has_valid_intrinsics with various mock scenarios."""

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_valid_intrinsics(self, mock_ccm_cls, bcm):
        intr = MagicMock()
        intr.camera_matrix = np.eye(3)
        mock_ccm_cls.return_value.get_intrinsics.return_value = intr

        assert bcm.has_valid_intrinsics() is True

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_none_intrinsics(self, mock_ccm_cls, bcm):
        mock_ccm_cls.return_value.get_intrinsics.return_value = None

        assert bcm.has_valid_intrinsics() is False

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_wrong_shape(self, mock_ccm_cls, bcm):
        intr = MagicMock()
        intr.camera_matrix = np.zeros((2, 2))
        mock_ccm_cls.return_value.get_intrinsics.return_value = intr

        assert bcm.has_valid_intrinsics() is False

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_no_camera_matrix_attr(self, mock_ccm_cls, bcm):
        intr = MagicMock(spec=[])  # no attributes
        mock_ccm_cls.return_value.get_intrinsics.return_value = intr

        assert bcm.has_valid_intrinsics() is False

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_camera_matrix_is_none(self, mock_ccm_cls, bcm):
        intr = MagicMock()
        intr.camera_matrix = None
        mock_ccm_cls.return_value.get_intrinsics.return_value = intr

        assert bcm.has_valid_intrinsics() is False
