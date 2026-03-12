"""Tests for single-pass combined remapping."""

import numpy as np

from src.cv.geometry import CameraIntrinsics
from src.cv.remapping import CombinedRemapper


def test_remapper_without_homography_returns_input():
    remapper = CombinedRemapper(roi_size=(50, 50))
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    remapper.configure(homography=None, intrinsics=None)
    out = remapper.remap(frame)
    assert out.shape == frame.shape


def test_remapper_homography_only_warp():
    remapper = CombinedRemapper(roi_size=(40, 40))
    frame = np.random.randint(0, 255, (80, 80, 3), dtype=np.uint8)
    remapper.configure(homography=np.eye(3), intrinsics=None)
    out = remapper.remap(frame)
    assert out.shape == (40, 40, 3)
    assert not remapper.has_combined_map


def test_remapper_combined_map_identity_model():
    remapper = CombinedRemapper(roi_size=(30, 30))
    frame = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
    intrinsics = CameraIntrinsics(
        camera_matrix=np.array([[80.0, 0.0, 25.0], [0.0, 80.0, 25.0], [0.0, 0.0, 1.0]], dtype=np.float64),
        dist_coeffs=np.zeros((5, 1), dtype=np.float64),
        valid=True,
        method="test",
    )
    remapper.configure(homography=np.eye(3), intrinsics=intrinsics)
    out = remapper.remap(frame)
    assert remapper.has_combined_map
    assert out.shape == (30, 30, 3)
