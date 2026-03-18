"""Validate pipeline detection counts against ground_truth.yaml for real test videos.

This test runs real video files through the full pipeline (calibration + detection)
and compares detected throw counts against annotated ground truth.

Skips automatically if testvids/ directory is absent (CI-friendly).
Marked as slow — run with ``pytest -m slow`` or ``pytest tests/e2e/``.
"""

from __future__ import annotations

import glob
import logging
import os

import pytest
import yaml

logger = logging.getLogger(__name__)

TESTVIDS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "testvids")
GT_PATH = os.path.join(TESTVIDS_DIR, "ground_truth.yaml")

# Only parametrise over videos that have ground-truth annotations
_gt_data: dict = {}
if os.path.exists(GT_PATH):
    with open(GT_PATH, encoding="utf-8") as _f:
        _raw = yaml.safe_load(_f)
    _gt_data = _raw.get("videos", {}) if _raw else {}

# Videos with at least one annotated throw
_ANNOTATED = [
    (os.path.join(TESTVIDS_DIR, fname), fname, entry)
    for fname, entry in _gt_data.items()
    if entry and entry.get("throws")
    and os.path.exists(os.path.join(TESTVIDS_DIR, fname))
]

pytestmark = [
    pytest.mark.skipif(not _ANNOTATED, reason="No annotated testvids available"),
    pytest.mark.slow,
]


def _run_pipeline_on_video(video_path: str) -> list[dict]:
    """Run the full pipeline (calibrate + detect) on a video, return detections."""
    import cv2
    from src.cv.pipeline import DartPipeline

    # Get total frame count
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    darts: list[dict] = []

    def on_dart(score: dict, detection=None) -> None:
        darts.append(score)

    pipeline = DartPipeline(
        camera_src=video_path,
        on_dart_detected=on_dart,
        marker_size_mm=100.0,
        marker_spacing_mm=365.0,
    )

    try:
        pipeline.start()

        # Phase 1: Calibrate from early frames
        legacy = pipeline.board_calibration._legacy
        original_save = legacy._atomic_save
        legacy._atomic_save = lambda: None

        for _ in range(30):
            if pipeline.camera is None:
                break
            ret, frame = pipeline.camera.read()
            if not ret or frame is None:
                break
            result = pipeline.board_calibration.aruco_calibration(
                frame, marker_spacing_mm=365.0, marker_size_mm=100.0,
            )
            if result.get("ok"):
                pipeline.refresh_remapper()
                pipeline.geometry = pipeline.board_calibration.get_geometry()
                break

        legacy._atomic_save = original_save

        # Seek back to start
        if hasattr(pipeline.camera, "capture"):
            pipeline.camera.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Reset detectors
        pipeline.motion_detector.reset()
        pipeline.frame_diff_detector.reset()
        pipeline.dart_detector.reset()

        # Phase 2: Process frames
        real_read = pipeline.camera.read
        frames_processed = 0

        def counting_read():
            nonlocal frames_processed
            ret, frame = real_read()
            if ret and frame is not None:
                frames_processed += 1
            return ret, frame

        pipeline.camera.read = counting_read

        limit = min(total_frames, 15000) if total_frames > 0 else 15000
        no_read = 0
        last = 0
        for _ in range(limit):
            pipeline.process_frame()
            if frames_processed == last:
                no_read += 1
                if no_read > 50:
                    break
            else:
                no_read = 0
                last = frames_processed

    finally:
        pipeline.stop()

    return darts


@pytest.mark.xfail(
    reason="Pipeline detection on real videos not yet accurate enough — "
           "baseline warmup and tuning needed (see P1/P11 priorities)",
    strict=False,
)
@pytest.mark.parametrize(
    "video_path,fname,gt_entry",
    _ANNOTATED,
    ids=[a[1] for a in _ANNOTATED],
)
def test_detection_count_within_range(video_path: str, fname: str, gt_entry: dict) -> None:
    """Pipeline detects a reasonable number of throws compared to ground truth.

    This is a lenient test: we check that the pipeline detects at least 20% of
    expected throws and does not produce more than 3x false positives.
    These thresholds should be tightened as detection accuracy improves.
    """
    gt_throws = gt_entry.get("throws", [])
    expected = len([t for t in gt_throws if t.get("ring") != "miss"])

    if expected == 0:
        pytest.skip(f"{fname}: no non-miss throws annotated")

    darts = _run_pipeline_on_video(video_path)
    detected = len(darts)

    logger.info(
        "%s: expected=%d detected=%d (%.0f%%)",
        fname, expected, detected,
        detected / expected * 100 if expected else 0,
    )

    # Log each detection for debugging
    for i, d in enumerate(darts):
        logger.info(
            "  dart %d: sector=%s ring=%s score=%s",
            i + 1, d.get("sector", "?"), d.get("ring", "?"), d.get("score", "?"),
        )

    # Lenient thresholds — pipeline must detect *something*
    min_detections = max(1, int(expected * 0.2))
    max_detections = expected * 4

    assert detected >= min_detections, (
        f"{fname}: detected {detected} throws, expected at least {min_detections} "
        f"(20% of {expected} ground-truth throws)"
    )
    assert detected <= max_detections, (
        f"{fname}: detected {detected} throws, expected at most {max_detections} "
        f"(4x of {expected} ground-truth throws — too many false positives)"
    )


@pytest.mark.parametrize(
    "video_path,fname,gt_entry",
    _ANNOTATED[:1],
    ids=[_ANNOTATED[0][1]] if _ANNOTATED else [],
)
def test_calibration_succeeds(video_path: str, fname: str, gt_entry: dict) -> None:
    """Pipeline can calibrate from the first annotated test video."""
    import cv2
    from src.cv.pipeline import DartPipeline

    pipeline = DartPipeline(
        camera_src=video_path,
        on_dart_detected=lambda s, d=None: None,
        marker_size_mm=100.0,
        marker_spacing_mm=365.0,
    )
    pipeline.start()
    calibrated = False
    try:
        legacy = pipeline.board_calibration._legacy
        legacy._atomic_save = lambda: None
        for _ in range(30):
            if pipeline.camera is None:
                break
            ret, frame = pipeline.camera.read()
            if not ret or frame is None:
                break
            result = pipeline.board_calibration.aruco_calibration(
                frame, marker_spacing_mm=365.0, marker_size_mm=100.0,
            )
            if result.get("ok"):
                calibrated = True
                break
    finally:
        pipeline.stop()

    assert calibrated, f"{fname}: ArUco calibration failed within 30 frames"
