"""Tests for calibration validation (Phase 6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_config(**overrides) -> dict:
    """Build a valid calibration config dict with optional overrides."""
    base = {
        "lens_valid": True,
        "camera_matrix": [[1, 0, 320], [0, 1, 240], [0, 0, 1]],
        "dist_coeffs": [0.0, 0.0, 0.0, 0.0, 0.0],
        "lens_reprojection_error": 0.5,
        "lens_image_size": [640, 480],
        "lens_last_update_utc": datetime.now(timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


def _make_manager(config: dict):
    """Create a CameraCalibrationManager with a mocked config backend."""
    from src.cv.camera_calibration import CameraCalibrationManager

    mgr = CameraCalibrationManager.__new__(CameraCalibrationManager)
    mgr._config_io = MagicMock()
    mgr._config_io.get_config.return_value = config
    mgr.config_path = "fake.yaml"
    mgr.camera_id = "test"
    return mgr


class TestValidateIntrinsics:
    def test_valid_config(self):
        mgr = _make_manager(_make_config())
        result = mgr.validate_intrinsics()
        assert result["valid"] is True
        assert result["errors"] == []

    def test_no_lens_valid(self):
        mgr = _make_manager(_make_config(lens_valid=False))
        result = mgr.validate_intrinsics()
        assert result["valid"] is False
        assert any("Keine Lens-Kalibrierung" in e for e in result["errors"])

    def test_missing_camera_matrix(self):
        mgr = _make_manager(_make_config(camera_matrix=None))
        result = mgr.validate_intrinsics()
        assert result["valid"] is False
        assert any("camera_matrix oder dist_coeffs fehlen" in e for e in result["errors"])

    def test_missing_dist_coeffs(self):
        mgr = _make_manager(_make_config(dist_coeffs=None))
        result = mgr.validate_intrinsics()
        assert result["valid"] is False

    def test_bad_camera_matrix_shape(self):
        mgr = _make_manager(_make_config(camera_matrix=[[1, 2], [3, 4]]))
        result = mgr.validate_intrinsics()
        assert result["valid"] is False
        assert any("falsche Shape" in e for e in result["errors"])

    def test_high_reprojection_error_warning(self):
        mgr = _make_manager(_make_config(lens_reprojection_error=1.5))
        result = mgr.validate_intrinsics()
        assert result["valid"] is True
        assert any("Reprojection Error hoch" in w for w in result["warnings"])

    def test_image_size_mismatch(self):
        mgr = _make_manager(_make_config(lens_image_size=[640, 480]))
        result = mgr.validate_intrinsics(current_image_size=(1920, 1080))
        assert result["valid"] is False
        assert any("aktuelle Aufloesung" in e for e in result["errors"])

    def test_image_size_match(self):
        mgr = _make_manager(_make_config(lens_image_size=[640, 480]))
        result = mgr.validate_intrinsics(current_image_size=(640, 480))
        assert result["valid"] is True

    def test_old_calibration_warning(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        mgr = _make_manager(_make_config(lens_last_update_utc=old_date))
        result = mgr.validate_intrinsics(max_age_days=30)
        assert result["valid"] is True
        assert any("Tage alt" in w for w in result["warnings"])


class TestValidateStereoPrerequisites:
    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_both_valid(self, MockMgr):
        instance = MockMgr.return_value
        instance.validate_intrinsics.return_value = {"valid": True, "errors": [], "warnings": []}

        from src.cv.stereo_calibration import validate_stereo_prerequisites
        result = validate_stereo_prerequisites("cam_a", "cam_b", config_path="fake.yaml")
        assert result["ready"] is True
        assert result["errors"] == []

    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    def test_one_missing(self, MockMgr):
        def side_effect(config_path, camera_id):
            inst = MagicMock()
            if camera_id == "cam_b":
                inst.validate_intrinsics.return_value = {
                    "valid": False, "errors": ["Keine Lens-Kalibrierung vorhanden"], "warnings": []
                }
            else:
                inst.validate_intrinsics.return_value = {"valid": True, "errors": [], "warnings": []}
            return inst
        MockMgr.side_effect = side_effect

        from src.cv.stereo_calibration import validate_stereo_prerequisites
        result = validate_stereo_prerequisites("cam_a", "cam_b", config_path="fake.yaml")
        assert result["ready"] is False
        assert any("cam_b" in e for e in result["errors"])
