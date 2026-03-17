"""Integration tests: FrameDiffDetector wired into DartPipeline."""
import numpy as np
import pytest
from src.cv.pipeline import DartPipeline
from src.cv.diff_detector import FrameDiffDetector


def test_pipeline_has_frame_diff_detector():
    p = DartPipeline()
    assert hasattr(p, "frame_diff_detector")
    assert isinstance(p.frame_diff_detector, FrameDiffDetector)


def test_reset_turn_resets_diff_detector():
    p = DartPipeline()
    # Drive state to in_motion naturally
    p.frame_diff_detector.update(np.zeros((100, 100), dtype=np.uint8), has_motion=False)
    p.frame_diff_detector.update(np.zeros((100, 100), dtype=np.uint8), has_motion=True)
    assert p.frame_diff_detector.state == "in_motion"
    p.reset_turn()
    assert p.frame_diff_detector.state == "idle"
