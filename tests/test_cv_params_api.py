"""Tests for CV parameter tuning API and runtime parameter updates."""

import pytest
import numpy as np

from src.cv.diff_detector import FrameDiffDetector


class TestFrameDiffDetectorParams:
    """Test get_params / set_params on FrameDiffDetector."""

    def test_get_params_returns_defaults(self):
        det = FrameDiffDetector()
        params = det.get_params()
        assert params["settle_frames"] == 5
        assert params["diff_threshold"] == 50
        assert params["min_diff_area"] == 50
        assert params["max_diff_area"] == 8000
        assert params["min_elongation"] == 1.5
        assert params["diagnostics_enabled"] is False

    def test_set_params_updates_values(self):
        det = FrameDiffDetector()
        result = det.set_params(diff_threshold=80, settle_frames=3)
        assert result["diff_threshold"] == 80
        assert result["settle_frames"] == 3
        # Others unchanged
        assert result["min_diff_area"] == 50

    def test_set_params_partial_update(self):
        det = FrameDiffDetector()
        det.set_params(min_elongation=2.5)
        assert det.min_elongation == 2.5
        assert det.diff_threshold == 50  # unchanged

    def test_set_params_rejects_invalid_settle_frames(self):
        det = FrameDiffDetector()
        with pytest.raises(ValueError, match="settle_frames"):
            det.set_params(settle_frames=0)

    def test_set_params_rejects_invalid_diff_threshold(self):
        det = FrameDiffDetector()
        with pytest.raises(ValueError, match="diff_threshold"):
            det.set_params(diff_threshold=0)
        with pytest.raises(ValueError, match="diff_threshold"):
            det.set_params(diff_threshold=256)

    def test_set_params_rejects_invalid_area_range(self):
        det = FrameDiffDetector()
        with pytest.raises(ValueError, match="min_diff_area"):
            det.set_params(min_diff_area=9000, max_diff_area=8000)

    def test_set_params_rejects_invalid_elongation(self):
        det = FrameDiffDetector()
        with pytest.raises(ValueError, match="min_elongation"):
            det.set_params(min_elongation=0.5)

    def test_set_params_does_not_apply_on_validation_failure(self):
        det = FrameDiffDetector()
        original = det.get_params()
        with pytest.raises(ValueError):
            det.set_params(diff_threshold=0)
        # Values should be unchanged
        assert det.get_params() == original


class TestToggleDiagnostics:
    """Test runtime diagnostics toggle."""

    def test_enable_diagnostics(self, tmp_path):
        det = FrameDiffDetector()
        result = det.toggle_diagnostics(str(tmp_path / "diag"))
        assert result is True
        assert det._diagnostics_dir is not None
        assert det.get_params()["diagnostics_enabled"] is True

    def test_disable_diagnostics(self, tmp_path):
        det = FrameDiffDetector(diagnostics_dir=str(tmp_path / "diag"))
        result = det.toggle_diagnostics(None)
        assert result is False
        assert det._diagnostics_dir is None
        assert det.get_params()["diagnostics_enabled"] is False
