"""Tests for ROIProcessor."""

import numpy as np
import pytest

from src.cv.roi import ROIProcessor


class TestROIProcessor:
    def test_warp_roi_no_homography_returns_original(self):
        proc = ROIProcessor(roi_size=(200, 200))
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = proc.warp_roi(frame)
        assert result is frame

    def test_set_homography_matrix_and_warp(self):
        proc = ROIProcessor(roi_size=(200, 200))
        # Identity-like homography
        matrix = np.eye(3, dtype=np.float64)
        proc.set_homography_matrix(matrix)
        assert proc.homography is not None
        assert proc.homography.shape == (3, 3)

        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        result = proc.warp_roi(frame)
        assert result.shape == (200, 200, 3)

    def test_set_homography_from_points(self):
        proc = ROIProcessor(roi_size=(200, 200))
        src = np.array([[0, 0], [640, 0], [640, 480], [0, 480]], dtype=np.float32)
        dst = np.array([[0, 0], [200, 0], [200, 200], [0, 200]], dtype=np.float32)
        proc.set_homography(src, dst)
        assert proc.homography is not None

        frame = np.ones((480, 640), dtype=np.uint8) * 100
        result = proc.warp_roi(frame)
        assert result.shape == (200, 200)

    def test_polar_unwrap_default_center(self):
        proc = ROIProcessor()
        roi = np.zeros((400, 400), dtype=np.uint8)
        polar = proc.polar_unwrap(roi)
        assert polar.shape == (360, 400)

    def test_polar_unwrap_custom_center(self):
        proc = ROIProcessor()
        roi = np.zeros((400, 400), dtype=np.uint8)
        polar = proc.polar_unwrap(roi, center=(200, 200), radius=150)
        assert polar.shape == (360, 300)

    def test_warp_roi_with_invalid_homography_falls_back(self):
        proc = ROIProcessor(roi_size=(200, 200))
        # Set a degenerate homography (all zeros)
        proc.homography = np.zeros((3, 3), dtype=np.float64)
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        # Should not raise, falls back to original
        result = proc.warp_roi(frame)
        assert result is not None
