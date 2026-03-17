"""Tests for config schema validation."""

import pytest
from src.utils.config import (
    validate_calibration_config,
    validate_matrix_shape,
    save_stereo_pair,
    save_board_transform,
)


def _make_matrix(rows, cols, val=1.0):
    return [[val] * cols for _ in range(rows)]


class TestValidateMatrixShape:
    def test_valid_3x3(self):
        assert validate_matrix_shape(_make_matrix(3, 3), 3, 3, "M") is None

    def test_wrong_rows(self):
        assert validate_matrix_shape(_make_matrix(2, 3), 3, 3, "M") is not None

    def test_wrong_cols(self):
        assert validate_matrix_shape(_make_matrix(3, 2), 3, 3, "M") is not None

    def test_non_numeric(self):
        m = [[1.0, 2.0, "x"], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0]]
        assert "expected number" in validate_matrix_shape(m, 3, 3, "M")


class TestValidateCalibrationConfig:
    def test_valid_config(self):
        config = {
            "cameras": {
                "default": {
                    "camera_matrix": _make_matrix(3, 3),
                    "dist_coeffs": [0.1, -0.2, 0.0, 0.0, 0.5],
                }
            }
        }
        assert validate_calibration_config(config) == []

    def test_invalid_camera_matrix_shape(self):
        config = {
            "cameras": {
                "cam1": {
                    "camera_matrix": _make_matrix(2, 3),
                }
            }
        }
        errors = validate_calibration_config(config)
        assert len(errors) == 1
        assert "camera_matrix" in errors[0]

    def test_invalid_board_transform(self):
        config = {
            "cameras": {
                "cam1": {
                    "board_transform": {
                        "R_cb": _make_matrix(2, 2),
                        "t_cb": _make_matrix(3, 1),
                    }
                }
            }
        }
        errors = validate_calibration_config(config)
        assert len(errors) == 1
        assert "R_cb" in errors[0]

    def test_missing_keys_graceful(self):
        assert validate_calibration_config({}) == []
        assert validate_calibration_config({"cameras": {}}) == []
        assert validate_calibration_config({"cameras": {"c": {}}}) == []

    def test_dist_coeffs_nested(self):
        config = {
            "cameras": {
                "c": {"dist_coeffs": [[0.1, -0.2, 0.0, 0.0, 0.5]]}
            }
        }
        assert validate_calibration_config(config) == []

    def test_dist_coeffs_non_numeric(self):
        config = {
            "cameras": {
                "c": {"dist_coeffs": ["bad"]}
            }
        }
        errors = validate_calibration_config(config)
        assert len(errors) == 1


class TestSaveStereoPairValidation:
    def test_invalid_R_raises(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        with pytest.raises(ValueError, match="R"):
            save_stereo_pair("a", "b", _make_matrix(2, 3), [[0], [0], [0]], 0.5, path=path)

    def test_negative_reprojection_error_raises(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        with pytest.raises(ValueError, match="reprojection_error"):
            save_stereo_pair("a", "b", _make_matrix(3, 3), [0, 0, 0], -1.0, path=path)

    def test_valid_save(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        save_stereo_pair("a", "b", _make_matrix(3, 3), [0, 0, 0], 0.5, path=path)


class TestSaveBoardTransformValidation:
    def test_invalid_R_cb_raises(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        with pytest.raises(ValueError, match="R_cb"):
            save_board_transform("cam1", _make_matrix(2, 2), [[0], [0], [0]], path=path)

    def test_invalid_t_cb_raises(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        with pytest.raises(ValueError, match="t_cb"):
            save_board_transform("cam1", _make_matrix(3, 3), [[0, 0], [0, 0]], path=path)

    def test_valid_save(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        save_board_transform("cam1", _make_matrix(3, 3), [0, 0, 0], path=path)
