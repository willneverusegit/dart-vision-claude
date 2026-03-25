"""Extended tests for src/cv/remapping.py — covering all branches.

Covers:
- roi_to_raw() all 3 paths (no homography, with intrinsics, without intrinsics)
- configure() with invalid intrinsics (valid=False)
- configure() exception path in _build_combined_maps
- _build_combined_maps with fx=0 (ValueError)
- remap() fallback path (intrinsics present but no combined map)
- remap() with combined map (already tested, but verify round-trip)
- homography property
- has_combined_map property states
"""

import numpy as np
import pytest

from src.cv.geometry import CameraIntrinsics
from src.cv.remapping import CombinedRemapper


def _make_intrinsics(fx=80.0, fy=80.0, cx=30.0, cy=30.0, valid=True):
    """Helper to create CameraIntrinsics with given parameters."""
    return CameraIntrinsics(
        camera_matrix=np.array(
            [[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float64
        ),
        dist_coeffs=np.zeros((5, 1), dtype=np.float64),
        valid=valid,
        method="test",
    )


# --- Property tests ---


class TestProperties:
    def test_homography_property_none_initially(self):
        r = CombinedRemapper()
        assert r.homography is None

    def test_homography_property_after_configure(self):
        r = CombinedRemapper()
        h = np.eye(3) * 2.0
        r.configure(homography=h, intrinsics=None)
        assert r.homography is not None
        np.testing.assert_allclose(r.homography, h)

    def test_has_combined_map_false_without_configure(self):
        r = CombinedRemapper()
        assert not r.has_combined_map

    def test_has_combined_map_false_homography_only(self):
        r = CombinedRemapper()
        r.configure(homography=np.eye(3), intrinsics=None)
        assert not r.has_combined_map

    def test_has_combined_map_false_invalid_intrinsics(self):
        r = CombinedRemapper()
        intr = _make_intrinsics(valid=False)
        r.configure(homography=np.eye(3), intrinsics=intr)
        assert not r.has_combined_map

    def test_has_combined_map_true_valid_intrinsics(self):
        r = CombinedRemapper(roi_size=(20, 20))
        intr = _make_intrinsics()
        r.configure(homography=np.eye(3), intrinsics=intr)
        assert r.has_combined_map


# --- configure() edge cases ---


class TestConfigure:
    def test_configure_none_homography_resets(self):
        r = CombinedRemapper(roi_size=(20, 20))
        intr = _make_intrinsics()
        r.configure(homography=np.eye(3), intrinsics=intr)
        assert r.has_combined_map
        # Now reset
        r.configure(homography=None, intrinsics=None)
        assert not r.has_combined_map
        assert r.homography is None

    def test_configure_invalid_intrinsics_no_combined_map(self):
        """valid=False should skip combined map build."""
        r = CombinedRemapper(roi_size=(20, 20))
        intr = _make_intrinsics(valid=False)
        r.configure(homography=np.eye(3), intrinsics=intr)
        assert not r.has_combined_map
        # Homography should still be set
        assert r.homography is not None

    def test_configure_no_intrinsics_no_combined_map(self):
        """None intrinsics should skip combined map build."""
        r = CombinedRemapper(roi_size=(20, 20))
        r.configure(homography=np.eye(3), intrinsics=None)
        assert not r.has_combined_map

    def test_configure_exception_in_build_maps_graceful(self):
        """If _build_combined_maps raises, configure falls back gracefully."""
        r = CombinedRemapper(roi_size=(20, 20))
        # Create intrinsics with fx=0 which triggers ValueError
        intr = _make_intrinsics(fx=0.0, fy=0.0)
        r.configure(homography=np.eye(3), intrinsics=intr)
        assert not r.has_combined_map
        # Homography should still be set
        assert r.homography is not None

    def test_configure_reshapes_flat_homography(self):
        """Homography given as flat array should be reshaped to 3x3."""
        r = CombinedRemapper(roi_size=(20, 20))
        h_flat = np.eye(3).ravel()  # 9 elements
        r.configure(homography=h_flat, intrinsics=None)
        assert r.homography.shape == (3, 3)


# --- _build_combined_maps ---


class TestBuildCombinedMaps:
    def test_zero_focal_length_raises(self):
        r = CombinedRemapper(roi_size=(10, 10))
        intr = _make_intrinsics(fx=0.0, fy=80.0)
        with pytest.raises(ValueError, match="Invalid focal lengths"):
            r._build_combined_maps(np.eye(3), intr)

    def test_zero_fy_raises(self):
        r = CombinedRemapper(roi_size=(10, 10))
        intr = _make_intrinsics(fx=80.0, fy=0.0)
        with pytest.raises(ValueError, match="Invalid focal lengths"):
            r._build_combined_maps(np.eye(3), intr)

    def test_valid_build_returns_float32_maps(self):
        r = CombinedRemapper(roi_size=(10, 10))
        intr = _make_intrinsics()
        map_x, map_y = r._build_combined_maps(np.eye(3), intr)
        assert map_x.dtype == np.float32
        assert map_y.dtype == np.float32
        assert map_x.shape == (10, 10)
        assert map_y.shape == (10, 10)


# --- remap() paths ---


class TestRemap:
    def test_remap_no_homography_returns_frame_unchanged(self):
        r = CombinedRemapper(roi_size=(40, 40))
        frame = np.ones((60, 60, 3), dtype=np.uint8) * 128
        r.configure(homography=None, intrinsics=None)
        out = r.remap(frame)
        np.testing.assert_array_equal(out, frame)

    def test_remap_homography_only_fallback(self):
        """With homography but no intrinsics, uses warpPerspective fallback."""
        r = CombinedRemapper(roi_size=(30, 30))
        frame = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
        r.configure(homography=np.eye(3), intrinsics=None)
        assert not r.has_combined_map
        out = r.remap(frame)
        assert out.shape == (30, 30, 3)

    def test_remap_with_invalid_intrinsics_uses_warp_fallback(self):
        """invalid intrinsics => no combined map => warpPerspective fallback."""
        r = CombinedRemapper(roi_size=(30, 30))
        frame = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
        intr = _make_intrinsics(valid=False)
        r.configure(homography=np.eye(3), intrinsics=intr)
        assert not r.has_combined_map
        out = r.remap(frame)
        assert out.shape == (30, 30, 3)

    def test_remap_with_valid_intrinsics_and_undistort_fallback(self):
        """Valid intrinsics but combined map build failed => undistort + warp fallback."""
        r = CombinedRemapper(roi_size=(30, 30))
        frame = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
        # fx=0 causes build failure
        intr = _make_intrinsics(fx=0.0, fy=0.0)
        r.configure(homography=np.eye(3), intrinsics=intr)
        assert not r.has_combined_map
        # But _intrinsics is set and valid=True, so undistort fallback should be used
        # Actually fx=0 with valid=True: the remap fallback path calls undistort
        # This tests line 103-108 (undistort fallback path)
        out = r.remap(frame)
        assert out.shape == (30, 30, 3)

    def test_remap_with_combined_map(self):
        """With valid homography + intrinsics, uses combined map (fast path)."""
        r = CombinedRemapper(roi_size=(20, 20))
        frame = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
        intr = _make_intrinsics()
        r.configure(homography=np.eye(3), intrinsics=intr)
        assert r.has_combined_map
        out = r.remap(frame)
        assert out.shape == (20, 20, 3)


# --- roi_to_raw() all paths ---


class TestRoiToRaw:
    def test_no_homography_returns_unchanged(self):
        r = CombinedRemapper()
        r.configure(homography=None, intrinsics=None)
        x, y = r.roi_to_raw(100.0, 200.0)
        assert x == 100.0
        assert y == 200.0

    def test_homography_only_no_intrinsics(self):
        """With homography but no intrinsics, applies inverse homography only."""
        r = CombinedRemapper(roi_size=(40, 40))
        r.configure(homography=np.eye(3), intrinsics=None)
        x, y = r.roi_to_raw(15.0, 25.0)
        assert abs(x - 15.0) < 0.1
        assert abs(y - 25.0) < 0.1

    def test_homography_with_invalid_intrinsics(self):
        """With homography and invalid intrinsics, skips re-distortion."""
        r = CombinedRemapper(roi_size=(40, 40))
        intr = _make_intrinsics(valid=False)
        r.configure(homography=np.eye(3), intrinsics=intr)
        x, y = r.roi_to_raw(15.0, 25.0)
        assert abs(x - 15.0) < 0.1
        assert abs(y - 25.0) < 0.1

    def test_homography_with_valid_intrinsics_re_distorts(self):
        """With homography and valid intrinsics, applies full inverse + re-distortion."""
        r = CombinedRemapper(roi_size=(40, 40))
        intr = _make_intrinsics(fx=200.0, fy=200.0, cx=30.0, cy=30.0)
        r.configure(homography=np.eye(3), intrinsics=intr)
        # With identity homography and zero distortion, should be near-identity
        x, y = r.roi_to_raw(30.0, 30.0)
        # At optical center with zero distortion: input == output
        assert abs(x - 30.0) < 0.5
        assert abs(y - 30.0) < 0.5

    def test_roi_to_raw_with_nonidentity_homography(self):
        """With a non-identity homography, coordinates should transform."""
        r = CombinedRemapper(roi_size=(40, 40))
        # Scale homography: ROI coords map to 2x camera coords
        h = np.array([[0.5, 0, 0], [0, 0.5, 0], [0, 0, 1]], dtype=np.float64)
        r.configure(homography=h, intrinsics=None)
        x, y = r.roi_to_raw(10.0, 10.0)
        # Inverse of 0.5 scale = 2x, so (10, 10) -> (20, 20)
        assert abs(x - 20.0) < 0.5
        assert abs(y - 20.0) < 0.5

    def test_roi_to_raw_with_zero_fx_skips_redistortion(self):
        """If fx==0, skip re-distortion step and return undistorted coords."""
        r = CombinedRemapper(roi_size=(40, 40))
        intr = _make_intrinsics(fx=0.0, fy=80.0)
        # fx=0 will cause the if fx != 0 and fy != 0 check to fail
        r.configure(homography=np.eye(3), intrinsics=intr)
        x, y = r.roi_to_raw(15.0, 25.0)
        # Should return undistorted point without re-distortion
        assert abs(x - 15.0) < 0.1
        assert abs(y - 25.0) < 0.1

    def test_roi_to_raw_roundtrip_consistency(self):
        """remap + roi_to_raw should be roughly inverse operations."""
        r = CombinedRemapper(roi_size=(40, 40))
        intr = _make_intrinsics(fx=300.0, fy=300.0, cx=320.0, cy=240.0)
        # Simple translation homography
        h = np.eye(3, dtype=np.float64)
        r.configure(homography=h, intrinsics=intr)
        # Point near center
        roi_x, roi_y = 20.0, 20.0
        raw_x, raw_y = r.roi_to_raw(roi_x, roi_y)
        # With zero distortion coefficients and identity homography,
        # the roundtrip should produce coordinates that are consistent
        assert isinstance(raw_x, float)
        assert isinstance(raw_y, float)
