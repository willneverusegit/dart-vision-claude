"""Robustness tests for multi-camera pipeline edge cases."""

import time
from dataclasses import dataclass
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.cv.multi_camera import MultiCameraPipeline, MAX_DETECTION_TIME_DIFF_S
from src.cv.stereo_utils import CameraParams, TriangulationResult


@dataclass
class FakeDetection:
    """Minimal detection mock."""
    center: tuple[int, int] = (200, 200)
    area: float = 100.0
    confidence: float = 0.8
    frame_count: int = 3


def _make_cam_params(cam_id: str) -> CameraParams:
    """Create dummy CameraParams for testing."""
    return CameraParams(
        camera_id=cam_id,
        camera_matrix=np.eye(3, dtype=np.float64) * 500,
        dist_coeffs=np.zeros((5, 1), dtype=np.float64),
        R=np.eye(3, dtype=np.float64),
        T=np.zeros((3, 1), dtype=np.float64),
    )


class TestCameraFailureFallback:
    """When one camera fails/stops producing detections, the other should still work."""

    def test_single_camera_fallback_after_timeout(self):
        """Only one camera detects -> single-camera fallback after timeout."""
        cb = MagicMock()
        configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ]
        pipeline = MultiCameraPipeline(camera_configs=configs, on_multi_dart_detected=cb)

        # Only cam_left detects, cam_right is "dead"
        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "ring": "single", "sector": 20, "multiplier": 1, "total_score": 20},
            "detection": FakeDetection(confidence=0.85),
            "timestamp": time.time() - 0.5,  # older than sync_wait_s (0.3s default)
        }

        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "single"
        assert result["camera_id"] == "cam_left"

    def test_no_crash_on_none_detection(self):
        """Buffer entry with detection=None should not crash voting."""
        cb = MagicMock()
        configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ]
        pipeline = MultiCameraPipeline(camera_configs=configs, on_multi_dart_detected=cb)

        now = time.time()
        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "total_score": 20},
            "detection": None,
            "timestamp": now,
        }
        pipeline._detection_buffer["cam_right"] = {
            "camera_id": "cam_right",
            "score_result": {"score": 60, "total_score": 60},
            "detection": FakeDetection(confidence=0.9),
            "timestamp": now + 0.01,
        }

        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "voting_fallback"


class TestZBehindBoard:
    """Triangulation with Z < 0 (behind board) should trigger voting fallback."""

    def test_z_negative_uses_voting(self, monkeypatch):
        """Triangulation returning Z < 0 is marked invalid, falls back to voting."""
        cb = MagicMock()
        cam_left = _make_cam_params("cam_left")
        cam_right = _make_cam_params("cam_right")

        configs = [
            {"camera_id": "cam_left", "src": 0, "camera_params": cam_left},
            {"camera_id": "cam_right", "src": 1, "camera_params": cam_right},
        ]
        pipeline = MultiCameraPipeline(camera_configs=configs, on_multi_dart_detected=cb)

        # Patch triangulate_point to return Z < 0
        def fake_triangulate(pt1, pt2, c1, c2, max_reproj_error=5.0):
            return TriangulationResult(
                point_3d=np.array([0.01, 0.02, -0.5]),
                reprojection_error=1.0,
                valid=False,  # Z < 0 → invalid
            )

        monkeypatch.setattr("src.cv.stereo_utils.triangulate_point", fake_triangulate)

        now = time.time()
        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "total_score": 20},
            "detection": FakeDetection(center=(150, 150), confidence=0.7),
            "timestamp": now,
        }
        pipeline._detection_buffer["cam_right"] = {
            "camera_id": "cam_right",
            "score_result": {"score": 20, "total_score": 20},
            "detection": FakeDetection(center=(250, 250), confidence=0.9),
            "timestamp": now + 0.01,
        }

        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "voting_fallback"

    def test_z_too_far_from_board_uses_voting(self, monkeypatch):
        """Triangulation with |Z| > 50mm (0.05m) should trigger voting fallback."""
        cb = MagicMock()
        cam_left = _make_cam_params("cam_left")
        cam_right = _make_cam_params("cam_right")

        configs = [
            {"camera_id": "cam_left", "src": 0, "camera_params": cam_left},
            {"camera_id": "cam_right", "src": 1, "camera_params": cam_right},
        ]
        pipeline = MultiCameraPipeline(camera_configs=configs, on_multi_dart_detected=cb)

        # Z = 0.1m (100mm) — too far from board plane
        def fake_triangulate(pt1, pt2, c1, c2, max_reproj_error=5.0):
            return TriangulationResult(
                point_3d=np.array([0.01, 0.02, 0.1]),
                reprojection_error=1.0,
                valid=True,
            )

        monkeypatch.setattr("src.cv.stereo_utils.triangulate_point", fake_triangulate)

        now = time.time()
        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "total_score": 20},
            "detection": FakeDetection(center=(150, 150), confidence=0.7),
            "timestamp": now,
        }
        pipeline._detection_buffer["cam_right"] = {
            "camera_id": "cam_right",
            "score_result": {"score": 20, "total_score": 20},
            "detection": FakeDetection(center=(250, 250), confidence=0.9),
            "timestamp": now + 0.01,
        }

        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "voting_fallback"


class TestTemporalTimeout:
    """Detections too far apart in time should use single-camera fallback."""

    def test_timeout_uses_most_recent(self):
        """Detections 1s apart -> single_timeout with most recent camera."""
        cb = MagicMock()
        configs = [
            {"camera_id": "cam_left", "src": 0},
            {"camera_id": "cam_right", "src": 1},
        ]
        pipeline = MultiCameraPipeline(camera_configs=configs, on_multi_dart_detected=cb)

        now = time.time()
        pipeline._detection_buffer["cam_left"] = {
            "camera_id": "cam_left",
            "score_result": {"score": 20, "total_score": 20},
            "detection": FakeDetection(confidence=0.95),
            "timestamp": now - 1.0,
        }
        pipeline._detection_buffer["cam_right"] = {
            "camera_id": "cam_right",
            "score_result": {"score": 60, "total_score": 60},
            "detection": FakeDetection(confidence=0.5),
            "timestamp": now,
        }

        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "single_timeout"
        assert result["camera_id"] == "cam_right"  # Most recent, not highest conf


class TestConfidenceVoting:
    """Voting should weight by confidence when cameras disagree."""

    def test_weighted_average_two_cameras(self):
        """Two cameras: weighted average of total_score by confidence."""
        pipeline = MultiCameraPipeline(camera_configs=[])

        entries = [
            {
                "camera_id": "cam_left",
                "score_result": {"score": 20, "ring": "single", "total_score": 20},
                "detection": FakeDetection(confidence=0.3),
                "timestamp": time.time(),
            },
            {
                "camera_id": "cam_right",
                "score_result": {"score": 60, "ring": "triple", "total_score": 60},
                "detection": FakeDetection(confidence=0.9),
                "timestamp": time.time(),
            },
        ]

        result = pipeline._voting_fallback(entries)
        assert result["source"] == "voting_fallback"
        # weighted: (20*0.3 + 60*0.9) / (0.3+0.9) = (6+54)/1.2 = 50.0
        assert result["total_score"] == 50
        assert result["camera_id"] == "cam_right"  # Highest confidence base

    def test_median_three_cameras(self):
        """Three cameras: median of total_score."""
        pipeline = MultiCameraPipeline(camera_configs=[])

        entries = [
            {
                "camera_id": "cam_a",
                "score_result": {"total_score": 10},
                "detection": FakeDetection(confidence=0.5),
                "timestamp": time.time(),
            },
            {
                "camera_id": "cam_b",
                "score_result": {"total_score": 20},
                "detection": FakeDetection(confidence=0.8),
                "timestamp": time.time(),
            },
            {
                "camera_id": "cam_c",
                "score_result": {"total_score": 60},
                "detection": FakeDetection(confidence=0.3),
                "timestamp": time.time(),
            },
        ]

        result = pipeline._voting_fallback(entries)
        assert result["total_score"] == 20  # Median
        assert result["source"] == "voting_fallback"

    def test_fallback_no_total_score(self):
        """Without total_score key, falls back to highest confidence selection."""
        pipeline = MultiCameraPipeline(camera_configs=[])

        entries = [
            {
                "camera_id": "cam_left",
                "score_result": {"score": 20, "ring": "single"},
                "detection": FakeDetection(confidence=0.4),
                "timestamp": time.time(),
            },
            {
                "camera_id": "cam_right",
                "score_result": {"score": 60, "ring": "triple"},
                "detection": FakeDetection(confidence=0.9),
                "timestamp": time.time(),
            },
        ]

        result = pipeline._voting_fallback(entries)
        assert result["score"] == 60
        assert result["camera_id"] == "cam_right"


class TestDifferentResolutions:
    """Cameras with different resolutions should not crash."""

    def test_different_resolution_detections(self):
        """Detection centers from different resolution cameras don't crash fusion."""
        cb = MagicMock()
        configs = [
            {"camera_id": "cam_hd", "src": 0},
            {"camera_id": "cam_sd", "src": 1},
        ]
        pipeline = MultiCameraPipeline(camera_configs=configs, on_multi_dart_detected=cb)

        now = time.time()
        # HD camera: 1920x1080 center region
        pipeline._detection_buffer["cam_hd"] = {
            "camera_id": "cam_hd",
            "score_result": {"score": 20, "total_score": 20},
            "detection": FakeDetection(center=(960, 540), confidence=0.9, area=500.0),
            "timestamp": now,
        }
        # SD camera: 640x480 center region
        pipeline._detection_buffer["cam_sd"] = {
            "camera_id": "cam_sd",
            "score_result": {"score": 20, "total_score": 20},
            "detection": FakeDetection(center=(320, 240), confidence=0.7, area=150.0),
            "timestamp": now + 0.01,
        }

        # Should not crash — no CameraParams so falls back to voting
        pipeline._try_fuse()
        cb.assert_called_once()
        result = cb.call_args[0][0]
        assert result["source"] == "voting_fallback"
