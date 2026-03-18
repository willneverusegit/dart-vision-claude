"""Tests for timestamp-based detection matching in test_all_videos.py."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.test_all_videos import (  # noqa: E402
    match_detections_to_ground_truth,
    format_match_report,
)


def test_exact_match():
    """Detections at exact expected frames match correctly."""
    gt = [
        {"sector": 20, "ring": "triple", "timestamp_s": 3.0},
        {"sector": 5, "ring": "single", "timestamp_s": 6.0},
    ]
    fps = 30.0
    dart_frames = [90, 180]  # 3*30=90, 6*30=180
    dart_details = [
        {"sector": 20, "ring": "triple", "score": 60},
        {"sector": 5, "ring": "single", "score": 5},
    ]
    matches = match_detections_to_ground_truth(
        dart_frames, dart_details, gt, fps, tolerance_frames=30
    )
    assert len(matches) == 2
    assert all(m["matched"] for m in matches)
    assert matches[0]["frame_delta"] == 0
    assert matches[1]["frame_delta"] == 0
    assert matches[0]["detection"]["sector"] == 20


def test_within_tolerance():
    """Detection within tolerance window matches."""
    gt = [{"sector": 1, "ring": "single", "timestamp_s": 5.0}]
    fps = 30.0
    dart_frames = [170]  # expected=150, delta=20 < 30
    dart_details = [{"sector": 1, "ring": "single", "score": 1}]
    matches = match_detections_to_ground_truth(
        dart_frames, dart_details, gt, fps, tolerance_frames=30
    )
    assert matches[0]["matched"]
    assert matches[0]["frame_delta"] == 20


def test_outside_tolerance():
    """Detection outside tolerance window does not match."""
    gt = [{"sector": 1, "ring": "single", "timestamp_s": 5.0}]
    fps = 30.0
    dart_frames = [250]  # expected=150, delta=100 > 30
    dart_details = [{"sector": 1, "ring": "single", "score": 1}]
    matches = match_detections_to_ground_truth(
        dart_frames, dart_details, gt, fps, tolerance_frames=30
    )
    assert not matches[0]["matched"]


def test_no_gt():
    """Empty GT returns empty matches."""
    matches = match_detections_to_ground_truth([10], [{}], [], 30.0)
    assert matches == []


def test_no_detections():
    """No detections means all GT unmatched."""
    gt = [{"sector": 20, "ring": "triple", "timestamp_s": 3.0}]
    matches = match_detections_to_ground_truth([], [], gt, 30.0)
    assert len(matches) == 1
    assert not matches[0]["matched"]


def test_one_detection_matches_closest_gt():
    """When one detection is near two GT throws, it matches the closest."""
    gt = [
        {"sector": 1, "ring": "single", "timestamp_s": 3.0},
        {"sector": 2, "ring": "single", "timestamp_s": 4.0},
    ]
    fps = 30.0
    # Frame 110: closer to 4.0s (frame 120, delta=10) than 3.0s (frame 90, delta=20)
    dart_frames = [110]
    dart_details = [{"sector": 2, "ring": "single", "score": 2}]
    matches = match_detections_to_ground_truth(
        dart_frames, dart_details, gt, fps, tolerance_frames=30
    )
    # GT at 3.0s should try first (greedy order), delta=20 -> matches
    # GT at 4.0s has no remaining detections -> unmatched
    assert matches[0]["matched"]  # 3.0s matches (delta=20)
    assert not matches[1]["matched"]  # 4.0s has no detection left


def test_format_match_report_produces_output():
    """format_match_report returns non-empty string for matched data."""
    gt = [{"sector": 20, "ring": "triple", "timestamp_s": 3.0}]
    dart_frames = [90]
    dart_details = [{"sector": 20, "ring": "triple", "score": 60}]
    matches = match_detections_to_ground_truth(
        dart_frames, dart_details, gt, 30.0
    )
    report = format_match_report(matches, dart_frames, dart_details)
    assert "OK" in report
    assert "GT triple 20" in report


def test_format_report_wrong_detection():
    """Report shows WRONG when detection sector/ring differs from GT."""
    gt = [{"sector": 20, "ring": "triple", "timestamp_s": 3.0}]
    dart_frames = [90]
    dart_details = [{"sector": 5, "ring": "single", "score": 5}]
    matches = match_detections_to_ground_truth(
        dart_frames, dart_details, gt, 30.0
    )
    report = format_match_report(matches, dart_frames, dart_details)
    assert "WRONG" in report


def test_format_report_false_positive():
    """Unmatched detections appear as FALSE POS."""
    dart_frames = [90, 500]
    dart_details = [
        {"sector": 20, "ring": "triple", "score": 60},
        {"sector": 1, "ring": "single", "score": 1},
    ]
    gt = [{"sector": 20, "ring": "triple", "timestamp_s": 3.0}]
    matches = match_detections_to_ground_truth(
        dart_frames, dart_details, gt, 30.0
    )
    report = format_match_report(matches, dart_frames, dart_details)
    assert "FALSE POS" in report


def test_missing_timestamp():
    """GT throw without timestamp_s is reported as unmatched."""
    gt = [{"sector": 20, "ring": "triple"}]
    matches = match_detections_to_ground_truth([90], [{}], gt, 30.0)
    assert not matches[0]["matched"]
    assert matches[0]["expected_frame"] is None
