"""Tests for intrinsics validation (P31) and camera error reporting (P30)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.cv.board_calibration import BoardCalibrationManager
from src.cv.stereo_calibration import validate_stereo_prerequisites


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


# --- P31: validate_stereo_prerequisites ---

class TestValidateStereoPrerequisites:
    """Pre-flight check: both cameras must have valid intrinsics."""

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_both_cameras_valid(self, mock_cls):
        mock_mgr = MagicMock()
        mock_mgr.validate_intrinsics.return_value = {
            "valid": True, "errors": [], "warnings": [],
        }
        mock_cls.return_value = mock_mgr

        result = validate_stereo_prerequisites("cam_left", "cam_right")
        assert result["ready"] is True
        assert result["errors"] == []

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_one_camera_missing(self, mock_cls):
        def side_effect(config_path, camera_id):
            mgr = MagicMock()
            if camera_id == "cam_left":
                mgr.validate_intrinsics.return_value = {
                    "valid": True, "errors": [], "warnings": [],
                }
            else:
                mgr.validate_intrinsics.return_value = {
                    "valid": False,
                    "errors": ["Keine Lens-Kalibrierung vorhanden"],
                    "warnings": [],
                }
            return mgr
        mock_cls.side_effect = side_effect

        result = validate_stereo_prerequisites("cam_left", "cam_right")
        assert result["ready"] is False
        assert len(result["errors"]) == 1
        assert "cam_right" in result["errors"][0]

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_both_cameras_missing(self, mock_cls):
        mock_mgr = MagicMock()
        mock_mgr.validate_intrinsics.return_value = {
            "valid": False,
            "errors": ["Keine Lens-Kalibrierung vorhanden"],
            "warnings": [],
        }
        mock_cls.return_value = mock_mgr

        result = validate_stereo_prerequisites("cam_a", "cam_b")
        assert result["ready"] is False
        assert len(result["errors"]) == 2

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_warnings_forwarded(self, mock_cls):
        mock_mgr = MagicMock()
        mock_mgr.validate_intrinsics.return_value = {
            "valid": True, "errors": [],
            "warnings": ["Kalibrierung ist 45 Tage alt"],
        }
        mock_cls.return_value = mock_mgr

        result = validate_stereo_prerequisites("cam_a", "cam_b")
        assert result["ready"] is True
        assert len(result["warnings"]) == 2


# --- P30: Camera error callback ---

class TestMultiCameraErrorCallback:
    """on_camera_errors_changed callback in MultiCameraPipeline."""

    def test_callback_called(self):
        from src.cv.multi_camera import MultiCameraPipeline

        received = []
        mp = MultiCameraPipeline.__new__(MultiCameraPipeline)
        mp._camera_errors = {"cam_0": "timeout"}
        mp.on_camera_errors_changed = lambda errors: received.append(errors)

        mp._notify_camera_errors()

        assert len(received) == 1
        assert received[0]["cam_0"] == "timeout"

    def test_no_callback_no_crash(self):
        from src.cv.multi_camera import MultiCameraPipeline

        mp = MultiCameraPipeline.__new__(MultiCameraPipeline)
        mp._camera_errors = {"cam_x": "error"}
        mp.on_camera_errors_changed = None
        mp._notify_camera_errors()  # should not raise

    def test_callback_exception_swallowed(self):
        from src.cv.multi_camera import MultiCameraPipeline

        mp = MultiCameraPipeline.__new__(MultiCameraPipeline)
        mp._camera_errors = {"cam_x": "error"}
        mp.on_camera_errors_changed = lambda e: (_ for _ in ()).throw(RuntimeError("boom"))
        mp._notify_camera_errors()  # should not raise


# --- P30: /api/multi/errors endpoint ---

class TestMultiErrorsEndpoint:

    def test_no_pipeline(self):
        from src.main import app, app_state
        from fastapi.testclient import TestClient

        saved = app_state.pop("multi_pipeline", None)
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/errors")
                assert resp.status_code == 200
                data = resp.json()
                assert data["ok"] is True
                assert data["errors"] == {}
        finally:
            if saved is not None:
                app_state["multi_pipeline"] = saved

    def test_with_errors(self):
        from src.main import app, app_state
        from fastapi.testclient import TestClient

        mock_multi = MagicMock()
        mock_multi.get_camera_errors.return_value = {"cam_0": "Kamera nicht erreichbar"}
        saved = app_state.get("multi_pipeline")
        app_state["multi_pipeline"] = mock_multi
        try:
            with TestClient(app) as client:
                resp = client.get("/api/multi/errors")
                assert resp.status_code == 200
                data = resp.json()
                assert data["errors"]["cam_0"] == "Kamera nicht erreichbar"
        finally:
            if saved is not None:
                app_state["multi_pipeline"] = saved
            else:
                app_state.pop("multi_pipeline", None)
