"""Shared test fixtures for Dart-Vision."""

import pytest
import numpy as np


@pytest.fixture
def mock_frame():
    """Generate a 720p black frame."""
    return np.zeros((720, 1280, 3), dtype=np.uint8)


@pytest.fixture
def mock_frame_with_circle(mock_frame):
    """Generate a frame with a white circle (simulated dartboard)."""
    import cv2
    frame = mock_frame.copy()
    cv2.circle(frame, (640, 360), 300, (255, 255, 255), 2)
    return frame


@pytest.fixture
def mock_roi_frame():
    """Generate a 400x400 ROI frame."""
    return np.zeros((400, 400), dtype=np.uint8)


@pytest.fixture
def mock_calibration_config(tmp_path):
    """Generate a temporary calibration config."""
    import yaml
    config = {
        "center_px": [200, 200],
        "mm_per_px": 0.85,
        "homography": np.eye(3).tolist(),
        "valid": True,
        "method": "manual",
    }
    config_path = str(tmp_path / "test_config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path
