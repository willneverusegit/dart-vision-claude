"""Tests for stereo calibration wizard API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestCalibrationStatus:
    @patch("src.cv.board_calibration.BoardCalibrationManager")
    @patch("src.cv.camera_calibration.CameraCalibrationManager")
    @patch("src.utils.config.load_multi_cam_config")
    def test_returns_expected_structure(self, mock_cfg, mock_cam_cal, mock_board_cal, client):
        mock_cfg.return_value = {
            "last_cameras": [{"camera_id": "cam0"}, {"camera_id": "cam1"}],
            "pairs": {"cam0_cam1": {"reprojection_error": 0.45}},
        }

        cam_inst = MagicMock()
        cam_inst.has_intrinsics.return_value = True
        cam_inst.validate_intrinsics.return_value = {
            "valid": True, "errors": [], "warnings": []
        }
        mock_cam_cal.return_value = cam_inst

        board_inst = MagicMock()
        board_inst.is_valid.return_value = True
        board_inst.get_viewing_angle_quality.return_value = 0.85
        mock_board_cal.return_value = board_inst

        resp = client.get("/api/multi-cam/calibration/status")
        assert resp.status_code == 200
        data = resp.json()

        assert "cameras" in data
        assert "pairs" in data
        assert "ready_for_multi" in data
        assert data["ready_for_multi"] is True

        assert "cam0" in data["cameras"]
        cam0 = data["cameras"]["cam0"]
        assert cam0["has_intrinsics"] is True
        assert cam0["intrinsics_valid"] is True
        assert cam0["has_board_pose"] is True
        assert cam0["viewing_angle_quality"] == 0.85

        assert "cam0_cam1" in data["pairs"]
        assert data["pairs"]["cam0_cam1"]["has_extrinsics"] is True
        assert data["pairs"]["cam0_cam1"]["reprojection_error"] == 0.45

    @patch("src.utils.config.load_multi_cam_config")
    def test_empty_config(self, mock_cfg, client):
        mock_cfg.return_value = {"last_cameras": [], "pairs": {}}

        resp = client.get("/api/multi-cam/calibration/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cameras"] == {}
        assert data["pairs"] == {}
        assert data["ready_for_multi"] is False


class TestCalibrationValidate:
    @patch("src.cv.stereo_calibration.validate_stereo_prerequisites")
    def test_valid_cameras(self, mock_validate, client):
        mock_validate.return_value = {"ok": True, "checks": []}

        resp = client.post(
            "/api/multi-cam/calibration/validate",
            json={"cam_a": "cam0", "cam_b": "cam1"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "checks": []}
        mock_validate.assert_called_once_with("cam0", "cam1")

    def test_missing_params_returns_400(self, client):
        resp = client.post(
            "/api/multi-cam/calibration/validate",
            json={"cam_a": "cam0"},
        )
        assert resp.status_code == 400
        assert "error" in resp.json()

    def test_empty_body_returns_400(self, client):
        resp = client.post(
            "/api/multi-cam/calibration/validate",
            json={},
        )
        assert resp.status_code == 400
