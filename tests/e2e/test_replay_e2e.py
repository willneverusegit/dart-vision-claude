"""E2E replay-based accuracy tests for the dart detection pipeline.

These tests generate synthetic video clips, run them through DartPipeline,
and compare detections against ground truth.  They serve as regression
protection for CV changes.

CI thresholds (adjust as detection improves):
    - Hit rate >= 60%
    - Score accuracy >= 50%
    - Ring accuracy >= 50%
    - False positive rate <= 50%
"""

from __future__ import annotations

import logging
import os

import pytest

from tests.e2e.generate_synthetic_clip import generate_clip
from tests.e2e.accuracy import (
    AccuracyReport,
    DetectionEvent,
    compute_accuracy,
    load_ground_truth,
)

logger = logging.getLogger(__name__)


def _run_replay_pipeline(video_path: str, gt_data: dict) -> list[DetectionEvent]:
    """Run DartPipeline on a replay clip and collect detections."""
    from src.cv.pipeline import DartPipeline

    detections: list[DetectionEvent] = []
    frame_counter = 0

    def on_dart(score_dict: dict, detection=None) -> None:
        nonlocal frame_counter
        center = detection.center if detection else (0, 0)
        detections.append(DetectionEvent(
            frame_index=frame_counter,
            center_px=center,
            score=score_dict["score"],
            sector=score_dict["sector"],
            ring=score_dict["ring"],
            multiplier=score_dict["multiplier"],
        ))

    pipeline = DartPipeline(
        camera_src=video_path,
        on_dart_detected=on_dart,
    )
    pipeline.start()

    # Override calibration: synthetic clips are already in ROI space (400x400),
    # so we need identity remapping and default centered geometry.
    pipeline.remapper.configure(homography=None, intrinsics=None)
    from src.cv.geometry import BoardGeometry, BoardPose
    default_pose = BoardPose(
        homography=None,
        center_px=(200.0, 200.0),
        radii_px=(10.0, 19.0, 106.0, 116.0, 188.0, 200.0),
        rotation_deg=0.0,
        optical_center_roi_px=(200.0, 200.0),
        valid=True,
        method="synthetic",
    )
    pipeline.geometry = BoardGeometry.from_pose(default_pose, roi_size=(400, 400))

    try:
        from tests.e2e.generate_synthetic_clip import FRAMES_PER_THROW, BG_WARMUP_FRAMES
        total_frames = gt_data.get("total_frames", 999)
        for _ in range(total_frames):
            pipeline.process_frame()
            frame_counter += 1
            # Reset detector between throws to simulate dart removal
            frames_after_warmup = frame_counter - BG_WARMUP_FRAMES
            if frames_after_warmup > 0 and frames_after_warmup % FRAMES_PER_THROW == 0:
                pipeline.dart_detector.reset()
    finally:
        pipeline.stop()

    return detections


@pytest.fixture(scope="module")
def synthetic_clip(tmp_path_factory):
    """Generate a synthetic test clip once per test module."""
    base = tmp_path_factory.mktemp("e2e_replay")
    video_path, gt_path = generate_clip(str(base))
    gt_data = load_ground_truth(gt_path)
    return video_path, gt_data


class TestReplayE2E:
    """Replay-based E2E accuracy tests."""

    def test_pipeline_detects_throws(self, synthetic_clip):
        """Pipeline should detect at least some of the synthetic throws."""
        video_path, gt_data = synthetic_clip
        detections = _run_replay_pipeline(video_path, gt_data)
        assert len(detections) > 0, "Pipeline detected zero throws on synthetic clip"

    def test_accuracy_hit_rate(self, synthetic_clip):
        """Hit rate should meet minimum threshold."""
        video_path, gt_data = synthetic_clip
        detections = _run_replay_pipeline(video_path, gt_data)
        report = compute_accuracy(gt_data, detections)
        logger.info("Accuracy report:\n%s", report.summary())
        # Lenient threshold for synthetic data — tighten as detection improves
        assert report.hit_rate >= 0.6, (
            f"Hit rate {report.hit_rate:.1%} below 60% threshold.\n"
            f"Matched: {report.matched}/{report.total_expected}\n"
            f"{report.summary()}"
        )

    def test_accuracy_score(self, synthetic_clip):
        """Score accuracy should meet minimum threshold for matched detections."""
        video_path, gt_data = synthetic_clip
        detections = _run_replay_pipeline(video_path, gt_data)
        report = compute_accuracy(gt_data, detections)
        if report.matched == 0:
            pytest.skip("No matched detections — can't measure score accuracy")
        assert report.score_accuracy >= 0.5, (
            f"Score accuracy {report.score_accuracy:.1%} below 50%.\n"
            f"{report.summary()}"
        )

    def test_accuracy_ring(self, synthetic_clip):
        """Ring classification accuracy should meet minimum threshold."""
        video_path, gt_data = synthetic_clip
        detections = _run_replay_pipeline(video_path, gt_data)
        report = compute_accuracy(gt_data, detections)
        if report.matched == 0:
            pytest.skip("No matched detections — can't measure ring accuracy")
        assert report.ring_accuracy >= 0.5, (
            f"Ring accuracy {report.ring_accuracy:.1%} below 50%.\n"
            f"{report.summary()}"
        )

    def test_false_positive_rate(self, synthetic_clip):
        """False positive rate should stay below threshold."""
        video_path, gt_data = synthetic_clip
        detections = _run_replay_pipeline(video_path, gt_data)
        report = compute_accuracy(gt_data, detections)
        assert report.false_positive_rate <= 0.5, (
            f"False positive rate {report.false_positive_rate:.1%} above 50%.\n"
            f"{report.summary()}"
        )

    def test_report_details_logged(self, synthetic_clip, caplog):
        """Full accuracy report should be logged for debugging."""
        video_path, gt_data = synthetic_clip
        with caplog.at_level(logging.INFO):
            detections = _run_replay_pipeline(video_path, gt_data)
            report = compute_accuracy(gt_data, detections)
            logger.info("=== E2E ACCURACY REPORT ===\n%s", report.summary())
            for d in report.details:
                tag = d.get("tag", "?")
                if d["detected"]:
                    status = "✅" if d["score_ok"] else "❌"
                    logger.info("  %s %s: expected=%s detected=%s dist=%.0fpx",
                                status, tag, d["expected"], d["detected"], d["distance_px"])
                else:
                    logger.info("  ⚠️  %s: MISSED", tag)
