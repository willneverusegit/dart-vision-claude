"""Sweep detection thresholds to find optimal values for your hardware.

Runs the pipeline on all ground-truth-annotated videos with different
parameter combinations and reports which settings maximize hit rate
while minimizing false positives.

Usage:
    python scripts/calibrate_thresholds.py
    python scripts/calibrate_thresholds.py --source-dir testvids --quick
    python scripts/calibrate_thresholds.py --marker-size 100 --marker-spacing 365
"""

from __future__ import annotations

import argparse
import itertools
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import yaml  # noqa: E402
from scripts.test_all_videos import (  # noqa: E402
    test_video,
    match_detections_to_ground_truth,
    load_ground_truth,
)


# Parameter grid to sweep
PARAM_GRID = {
    "diff_threshold": [20, 30, 40],
    "min_elongation": [1.5, 2.0, 2.5, 3.0],
    "min_diff_area": [30, 50, 80],
}

QUICK_GRID = {
    "diff_threshold": [25, 35],
    "min_elongation": [2.0, 2.5],
    "min_diff_area": [30, 60],
}


def score_result(
    gt_throws: list[dict],
    dart_frames: list[int],
    dart_details: list[dict],
    video_fps: float,
) -> dict:
    """Score a single video run: hit rate, false positives, accuracy."""
    gt_non_miss = [t for t in gt_throws if t.get("ring") != "miss"]
    gt_count = len(gt_non_miss)

    matches = match_detections_to_ground_truth(
        dart_frames, dart_details, gt_non_miss, video_fps
    )
    matched = sum(1 for m in matches if m["matched"])
    correct = sum(
        1 for m in matches
        if m["matched"]
        and m["detection"].get("sector") == m["gt"].get("sector")
        and m["detection"].get("ring") == m["gt"].get("ring")
    )
    false_pos = len(dart_details) - matched

    return {
        "gt_count": gt_count,
        "detected": len(dart_details),
        "matched": matched,
        "correct": correct,
        "false_positives": false_pos,
        "hit_rate": matched / gt_count if gt_count > 0 else 0.0,
        "accuracy": correct / gt_count if gt_count > 0 else 0.0,
        "fp_rate": false_pos / max(len(dart_details), 1),
    }


def run_sweep(
    videos_with_gt: list[tuple[str, list[dict]]],
    marker_size: float,
    marker_spacing: float,
    max_frames: int,
    grid: dict,
) -> list[dict]:
    """Run all parameter combinations and return ranked results."""
    keys = sorted(grid.keys())
    combos = list(itertools.product(*(grid[k] for k in keys)))
    print(f"Sweeping {len(combos)} parameter combinations x {len(videos_with_gt)} videos")
    print(f"Parameters: {keys}")
    print()

    results = []

    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        print(f"[{i+1}/{len(combos)}] {params} ... ", end="", flush=True)

        # Monkey-patch FrameDiffDetector defaults for this run
        import src.cv.diff_detector as dd_mod
        orig_init = dd_mod.FrameDiffDetector.__init__

        def patched_init(self, *args, **kwargs):
            for k, v in params.items():
                kwargs.setdefault(k, v)
            orig_init(self, *args, **kwargs)

        dd_mod.FrameDiffDetector.__init__ = patched_init

        totals = {
            "gt_count": 0, "detected": 0, "matched": 0,
            "correct": 0, "false_positives": 0,
        }

        try:
            for vpath, gt_throws in videos_with_gt:
                result = test_video(vpath, marker_size, marker_spacing, max_frames)
                s = score_result(
                    gt_throws, result["dart_frames"],
                    result["dart_details"], result["video_fps"],
                )
                for k in totals:
                    totals[k] += s[k]
        finally:
            dd_mod.FrameDiffDetector.__init__ = orig_init

        gt = totals["gt_count"]
        hit_rate = totals["matched"] / gt if gt > 0 else 0.0
        accuracy = totals["correct"] / gt if gt > 0 else 0.0
        fp = totals["false_positives"]

        # Combined score: reward hits, penalize false positives
        combined = hit_rate * 0.6 + accuracy * 0.3 - (fp / max(gt, 1)) * 0.1

        entry = {
            "params": params,
            **totals,
            "hit_rate": hit_rate,
            "accuracy": accuracy,
            "combined_score": combined,
        }
        results.append(entry)
        print(f"hit={hit_rate:.0%} acc={accuracy:.0%} fp={fp} score={combined:.3f}")

    return sorted(results, key=lambda r: r["combined_score"], reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep thresholds for optimal detection")
    parser.add_argument("--source-dir", default="testvids")
    parser.add_argument("--marker-size", type=float, default=100.0)
    parser.add_argument("--marker-spacing", type=float, default=365.0)
    parser.add_argument("--max-frames", type=int, default=10000)
    parser.add_argument("--ground-truth", default=None)
    parser.add_argument("--quick", action="store_true",
                        help="Use smaller parameter grid for faster results")
    args = parser.parse_args()

    gt_path = args.ground_truth or os.path.join(args.source_dir, "ground_truth.yaml")
    ground_truth = load_ground_truth(gt_path)

    if not ground_truth:
        print(f"No ground truth found at {gt_path}")
        sys.exit(1)

    # Only sweep videos that have GT throws
    videos_with_gt = []
    for fname, entry in ground_truth.items():
        throws = entry.get("throws", [])
        if not throws:
            continue
        vpath = os.path.join(args.source_dir, fname)
        if os.path.exists(vpath):
            videos_with_gt.append((vpath, throws))

    if not videos_with_gt:
        print("No videos with ground truth throws found")
        sys.exit(1)

    print(f"Found {len(videos_with_gt)} videos with ground truth annotations")
    grid = QUICK_GRID if args.quick else PARAM_GRID
    t0 = time.perf_counter()
    ranked = run_sweep(videos_with_gt, args.marker_size, args.marker_spacing,
                       args.max_frames, grid)
    elapsed = time.perf_counter() - t0

    print()
    print("=" * 80)
    print("TOP 5 PARAMETER COMBINATIONS")
    print("=" * 80)
    for i, r in enumerate(ranked[:5]):
        print(f"\n  #{i+1}: {r['params']}")
        print(f"      Hit rate: {r['hit_rate']:.0%} ({r['matched']}/{r['gt_count']})")
        print(f"      Accuracy: {r['accuracy']:.0%} ({r['correct']}/{r['gt_count']})")
        print(f"      False positives: {r['false_positives']}")
        print(f"      Combined score: {r['combined_score']:.3f}")

    best = ranked[0]
    print()
    print(f"RECOMMENDED: {best['params']}")
    print(f"  Apply via API: POST /api/detection/params with {best['params']}")
    print(f"  Or update defaults in src/cv/diff_detector.py")
    print(f"\nTotal sweep time: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
