"""Tests for multi-camera config: stereo pairs, CalibrationManager camera_id, legacy migration."""

import os
import threading

import yaml
import numpy as np
import pytest

from src.cv.calibration import CalibrationManager
from src.utils.config import (
    get_stereo_pair,
    save_stereo_pair,
    load_multi_cam_config,
)


class TestStereoPairRoundtrip:
    def test_save_and_load(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        R = np.eye(3).tolist()
        T = [0.1, 0.0, 0.0]
        save_stereo_pair("cam_left", "cam_right", R, T, 0.42, path=path)

        pair = get_stereo_pair("cam_left", "cam_right", path=path)
        assert pair is not None
        assert pair["R"] == R
        assert pair["T"] == T
        assert pair["reprojection_error"] == 0.42
        assert "calibrated_utc" in pair

    def test_order_independent_lookup(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        R = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        T = [0.1, 0.0, 0.0]
        save_stereo_pair("cam_left", "cam_right", R, T, 0.5, path=path)

        # Lookup in reverse order
        pair = get_stereo_pair("cam_right", "cam_left", path=path)
        assert pair is not None
        assert pair["reprojection_error"] == 0.5

    def test_nonexistent_pair_returns_none(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        assert get_stereo_pair("a", "b", path=path) is None

    def test_schema_version_preserved(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        save_stereo_pair("a", "b", [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0], 0.1, path=path)
        cfg = load_multi_cam_config(path)
        assert cfg["schema_version"] >= 2  # v2 added cameras + board_transform sections

    def test_metadata_roundtrip(self, tmp_path):
        path = str(tmp_path / "multi.yaml")
        save_stereo_pair(
            "cam_left",
            "cam_right",
            np.eye(3).tolist(),
            [0.1, 0.0, 0.0],
            0.42,
            calibration_method="board_pose_provisional",
            quality_level="provisional",
            intrinsics_source="estimated",
            pose_consistency_px=0.73,
            warning="Provisorisch - Verfeinerung empfohlen",
            path=path,
        )

        pair = get_stereo_pair("cam_left", "cam_right", path=path)
        assert pair["calibration_method"] == "board_pose_provisional"
        assert pair["quality_level"] == "provisional"
        assert pair["intrinsics_source"] == "estimated"
        assert pair["pose_consistency_px"] == pytest.approx(0.73)
        assert "Verfeinerung" in pair["warning"]


class TestCalibrationManagerCameraId:
    def test_default_camera_id(self, tmp_path):
        path = str(tmp_path / "cal.yaml")
        mgr = CalibrationManager(config_path=path)
        assert mgr.camera_id == "default"

    def test_custom_camera_id(self, tmp_path):
        path = str(tmp_path / "cal.yaml")
        mgr = CalibrationManager(config_path=path, camera_id="cam_left")
        assert mgr.camera_id == "cam_left"

    def test_multiple_cameras_same_file(self, tmp_path):
        path = str(tmp_path / "cal.yaml")

        mgr1 = CalibrationManager(config_path=path, camera_id="cam_left")
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        result1 = mgr1.manual_calibration(points)
        assert result1["ok"]

        mgr2 = CalibrationManager(config_path=path, camera_id="cam_right")
        points2 = [[50, 50], [250, 50], [250, 250], [50, 250]]
        result2 = mgr2.manual_calibration(points2)
        assert result2["ok"]

        # Reload and verify both cameras are in the file
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        assert "cameras" in raw
        assert "cam_left" in raw["cameras"]
        assert "cam_right" in raw["cameras"]
        assert raw["schema_version"] == 3

        # Verify each camera has its own config
        assert raw["cameras"]["cam_left"]["valid"] is True
        assert raw["cameras"]["cam_right"]["valid"] is True

    def test_reload_camera_config(self, tmp_path):
        path = str(tmp_path / "cal.yaml")

        mgr1 = CalibrationManager(config_path=path, camera_id="cam_left")
        mgr1.manual_calibration([[100, 100], [300, 100], [300, 300], [100, 300]])

        # Fresh load of same camera_id should get persisted config
        mgr_reload = CalibrationManager(config_path=path, camera_id="cam_left")
        assert mgr_reload.is_valid()
        np.testing.assert_array_almost_equal(
            mgr_reload.get_homography(), mgr1.get_homography()
        )


class TestLegacyMigration:
    def test_legacy_flat_config_loads(self, tmp_path):
        path = str(tmp_path / "cal.yaml")
        # Write a legacy flat config (no 'cameras' key)
        legacy_data = {
            "center_px": [200, 200],
            "radii_px": [10, 19, 106, 116, 188, 200],
            "rotation_deg": 0.0,
            "mm_per_px": 2.5,
            "homography": np.eye(3).tolist(),
            "valid": True,
            "method": "manual",
            "schema_version": 2,
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(legacy_data, f)

        # Loading as default should work
        mgr = CalibrationManager(config_path=path, camera_id="default")
        assert mgr.is_valid()
        assert mgr.get_mm_per_px() == 2.5

    def test_legacy_migrated_on_save(self, tmp_path):
        path = str(tmp_path / "cal.yaml")
        # Write legacy flat config
        legacy_data = {
            "center_px": [200, 200],
            "radii_px": [10, 19, 106, 116, 188, 200],
            "rotation_deg": 0.0,
            "mm_per_px": 2.5,
            "homography": np.eye(3).tolist(),
            "valid": True,
            "method": "manual",
            "schema_version": 2,
        }
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(legacy_data, f)

        # Load, then save (trigger migration)
        mgr = CalibrationManager(config_path=path, camera_id="default")
        mgr.manual_calibration([[100, 100], [300, 100], [300, 300], [100, 300]])

        # Verify file is now in new format
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        assert "cameras" in raw
        assert "default" in raw["cameras"]
        assert raw["schema_version"] == 3
        assert raw["cameras"]["default"]["valid"] is True


class TestFileLock:
    def test_concurrent_writes(self, tmp_path):
        """Two managers with different camera_ids write to the same file."""
        path = str(tmp_path / "cal.yaml")
        errors = []

        def write_camera(camera_id, points):
            try:
                mgr = CalibrationManager(config_path=path, camera_id=camera_id)
                result = mgr.manual_calibration(points)
                if not result["ok"]:
                    errors.append(f"{camera_id}: {result['error']}")
            except Exception as e:
                errors.append(f"{camera_id}: {e}")

        t1 = threading.Thread(
            target=write_camera,
            args=("cam_a", [[100, 100], [300, 100], [300, 300], [100, 300]]),
        )
        t2 = threading.Thread(
            target=write_camera,
            args=("cam_b", [[50, 50], [250, 50], [250, 250], [50, 250]]),
        )
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == [], f"Concurrent write errors: {errors}"

        # Both cameras should be in the file
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        assert "cameras" in raw
        assert "cam_a" in raw["cameras"]
        assert "cam_b" in raw["cameras"]
