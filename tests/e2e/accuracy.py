"""Accuracy metrics for comparing pipeline detections against ground truth."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Ground-truth files may use "bull_inner"/"bull_outer" while the pipeline
# produces "inner_bull"/"outer_bull".  Normalise before comparison.
_GT_RING_ALIASES: dict[str, str] = {
    "bull_inner": "inner_bull",
    "bull_outer": "outer_bull",
}


def normalize_gt_ring(ring: str) -> str:
    """Translate ground-truth ring names to backend ring names."""
    return _GT_RING_ALIASES.get(ring, ring)


@dataclass
class DetectionEvent:
    """A single detection from the pipeline during replay."""
    frame_index: int
    center_px: tuple[int, int]
    score: int
    sector: int
    ring: str
    multiplier: int


@dataclass
class AccuracyReport:
    """Aggregated accuracy metrics from an E2E replay run."""
    total_expected: int = 0
    total_detected: int = 0
    matched: int = 0
    score_correct: int = 0
    sector_correct: int = 0
    ring_correct: int = 0
    false_positives: int = 0
    missed: int = 0
    details: list[dict] = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        """Fraction of expected throws that were detected at all."""
        return self.matched / self.total_expected if self.total_expected > 0 else 0.0

    @property
    def score_accuracy(self) -> float:
        """Fraction of matched detections with correct score."""
        return self.score_correct / self.matched if self.matched > 0 else 0.0

    @property
    def sector_accuracy(self) -> float:
        """Fraction of matched detections with correct sector."""
        return self.sector_correct / self.matched if self.matched > 0 else 0.0

    @property
    def ring_accuracy(self) -> float:
        """Fraction of matched detections with correct ring."""
        return self.ring_correct / self.matched if self.matched > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        """False positives relative to total detections."""
        return self.false_positives / self.total_detected if self.total_detected > 0 else 0.0

    def summary(self) -> str:
        lines = [
            f"Expected: {self.total_expected}, Detected: {self.total_detected}, Matched: {self.matched}",
            f"Hit rate:         {self.hit_rate:.1%}",
            f"Score accuracy:   {self.score_accuracy:.1%}",
            f"Sector accuracy:  {self.sector_accuracy:.1%}",
            f"Ring accuracy:    {self.ring_accuracy:.1%}",
            f"False positives:  {self.false_positives} ({self.false_positive_rate:.1%})",
            f"Missed:           {self.missed}",
        ]
        return "\n".join(lines)


def load_ground_truth(gt_path: str | Path) -> dict:
    """Load and validate a ground-truth JSON file."""
    with open(gt_path) as f:
        data = json.load(f)
    assert "events" in data, f"Ground truth missing 'events' key: {gt_path}"
    return data


def compute_accuracy(
    ground_truth: dict,
    detections: list[DetectionEvent],
    frame_tolerance: int = 10,
    position_tolerance_px: int = 40,
) -> AccuracyReport:
    """Compare detections against ground truth and compute accuracy metrics.

    Matching logic:
    - A detection matches a GT event if it occurs within ±frame_tolerance frames
      of the GT frame_index AND within position_tolerance_px of the GT point.
    - Each GT event matches at most one detection (closest in frame index).
    - Unmatched detections are false positives.
    - Unmatched GT events are misses.
    """
    report = AccuracyReport(
        total_expected=len(ground_truth["events"]),
        total_detected=len(detections),
    )

    gt_events = ground_truth["events"]
    used_detections = set()

    for gt_event in gt_events:
        gt_frame = gt_event["frame_index"]
        gt_x, gt_y = gt_event["raw_point_px"]
        expected = gt_event["expected"]

        best_match = None
        best_dist = float("inf")

        for i, det in enumerate(detections):
            if i in used_detections:
                continue
            frame_diff = abs(det.frame_index - gt_frame)
            if frame_diff > frame_tolerance:
                continue
            dx = det.center_px[0] - gt_x
            dy = det.center_px[1] - gt_y
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > position_tolerance_px:
                continue
            if dist < best_dist:
                best_dist = dist
                best_match = i

        detail = {
            "tag": gt_event.get("tag", ""),
            "expected": expected,
            "gt_frame": gt_frame,
            "gt_point": [gt_x, gt_y],
        }

        if best_match is not None:
            used_detections.add(best_match)
            det = detections[best_match]
            report.matched += 1

            det_result = {
                "score": det.score,
                "sector": det.sector,
                "ring": det.ring,
                "multiplier": det.multiplier,
            }
            detail["detected"] = det_result
            detail["det_frame"] = det.frame_index
            detail["det_point"] = list(det.center_px)
            detail["distance_px"] = round(best_dist, 1)

            if det.score == expected["score"]:
                report.score_correct += 1
            if det.sector == expected["sector"]:
                report.sector_correct += 1
            expected_ring = normalize_gt_ring(expected["ring"])
            if det.ring == expected_ring:
                report.ring_correct += 1

            detail["score_ok"] = det.score == expected["score"]
            detail["sector_ok"] = det.sector == expected["sector"]
            detail["ring_ok"] = det.ring == expected_ring
        else:
            report.missed += 1
            detail["detected"] = None

        report.details.append(detail)

    report.false_positives = len(detections) - len(used_detections)

    return report
