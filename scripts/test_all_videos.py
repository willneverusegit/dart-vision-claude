"""Batch-test all videos in testvids/ through the dart detection pipeline.

Usage:
    python scripts/test_all_videos.py --marker-size 100 --marker-spacing 365
    python scripts/test_all_videos.py --source-dir testvids --marker-size 100 --max-frames 5000
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import yaml  # noqa: E402
from src.cv.pipeline import DartPipeline  # noqa: E402


def _calibrate_from_video(pipeline: DartPipeline, marker_size_mm: float,
                           marker_spacing_mm: float, max_tries: int = 30) -> dict | None:
    """Read frames from the video until ArUco calibration succeeds."""
    for _ in range(max_tries):
        if pipeline.camera is None:
            return None
        ret, frame = pipeline.camera.read()
        if not ret or frame is None:
            return None
        result = pipeline.board_calibration.aruco_calibration(
            frame,
            marker_spacing_mm=marker_spacing_mm,
            marker_size_mm=marker_size_mm,
        )
        if result.get("ok"):
            return result
    return None


def test_video(path: str, marker_size_mm: float,
               marker_spacing_mm: float, max_frames: int) -> dict:
    """Run pipeline on a single video file, return stats."""
    # Get total frame count upfront
    cap = cv2.VideoCapture(path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    darts_detected: list[dict] = []
    dart_frames: list[int] = []
    frame_counter = 0

    def on_dart(score: dict, detection=None) -> None:
        darts_detected.append(score)
        dart_frames.append(frame_counter)

    pipeline = DartPipeline(
        camera_src=path,
        on_dart_detected=on_dart,
        marker_size_mm=marker_size_mm,
        marker_spacing_mm=marker_spacing_mm,
    )

    frames_processed = 0
    calib_frames_used = 0
    t0 = time.perf_counter()
    error: str | None = None
    calibrated = False

    try:
        pipeline.start()

        # Phase 1: Calibrate from early frames
        # Suppress saving to disk — we only want in-memory calibration
        legacy = pipeline.board_calibration._legacy
        original_save = legacy._atomic_save
        legacy._atomic_save = lambda: None  # no-op

        calib_result = _calibrate_from_video(pipeline, marker_size_mm, marker_spacing_mm)
        if calib_result and calib_result.get("ok"):
            calibrated = True
            pipeline.refresh_remapper()
            pipeline.geometry = pipeline.board_calibration.get_geometry()

        legacy._atomic_save = original_save  # restore

        # Seek back to start for full processing
        if hasattr(pipeline.camera, 'capture'):
            pipeline.camera.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Reset detectors (calibration frames may have polluted state)
        pipeline.motion_detector.reset()
        pipeline.frame_diff_detector.reset()
        pipeline.dart_detector.reset()

        # Phase 2: Process all frames through pipeline
        # Monkey-patch camera.read() to count frames accurately
        real_read = pipeline.camera.read
        def counting_read():
            nonlocal frames_processed, frame_counter
            ret, frame = real_read()
            if ret and frame is not None:
                frames_processed += 1
            frame_counter += 1
            return ret, frame
        pipeline.camera.read = counting_read

        limit = min(max_frames, total_frames) if total_frames > 0 else max_frames
        no_read_count = 0
        last_frames = 0
        for _ in range(limit):
            pipeline.process_frame()
            if frames_processed == last_frames:
                no_read_count += 1
                if no_read_count > 50:
                    break  # Video exhausted (camera.read returns False)
            else:
                no_read_count = 0
                last_frames = frames_processed

    except Exception as exc:
        import traceback
        error = str(exc)
        traceback.print_exc()
    finally:
        pipeline.stop()

    elapsed = time.perf_counter() - t0
    fps = frames_processed / elapsed if elapsed > 0 else 0.0

    return {
        "file": os.path.basename(path),
        "frames": frames_processed,
        "total_frames": total_frames,
        "video_fps": round(video_fps, 1),
        "darts": len(darts_detected),
        "dart_details": darts_detected,
        "dart_frames": dart_frames,
        "fps": round(fps, 1),
        "elapsed_s": round(elapsed, 1),
        "calibrated": calibrated,
        "error": error,
    }


def load_ground_truth(gt_path: str) -> dict:
    """Load ground truth YAML file."""
    if not os.path.exists(gt_path):
        return {}
    with open(gt_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("videos", {}) if data else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-test videos through dart pipeline")
    parser.add_argument("--source-dir", default="testvids", help="Directory with .mp4 files")
    parser.add_argument("--marker-size", type=float, default=100.0,
                        help="ArUco marker edge length in mm (default: 100)")
    parser.add_argument("--marker-spacing", type=float, default=365.0,
                        help="ArUco marker center-to-center distance in mm (default: 365)")
    parser.add_argument("--max-frames", type=int, default=10000,
                        help="Max frames to process per video (default: 10000)")
    parser.add_argument("--ground-truth", default=None,
                        help="Path to ground_truth.yaml (default: <source-dir>/ground_truth.yaml)")
    args = parser.parse_args()

    gt_path = args.ground_truth or os.path.join(args.source_dir, "ground_truth.yaml")
    ground_truth = load_ground_truth(gt_path)

    videos = sorted(glob.glob(os.path.join(args.source_dir, "*.mp4")))
    if not videos:
        print(f"No .mp4 files found in {args.source_dir}/")
        sys.exit(1)

    print(f"Found {len(videos)} video(s) in {args.source_dir}/")
    print(f"Marker size: {args.marker_size}mm, spacing: {args.marker_spacing}mm")
    if ground_truth:
        print(f"Ground truth: {gt_path}")
    print()

    # Header
    print(f"{'File':<30} {'Frames':>7} {'Calib':>5} {'Detect':>6} {'GT':>4} {'Hit%':>5} {'FPS':>6} {'Time':>7}")
    print("-" * 85)

    results = []
    total_gt = 0
    total_detected = 0
    total_correct = 0

    for vpath in videos:
        result = test_video(vpath, args.marker_size, args.marker_spacing, args.max_frames)
        results.append(result)

        fname = result["file"]
        gt_entry = ground_truth.get(fname, {})
        gt_throws = gt_entry.get("throws", []) if gt_entry else []
        gt_count = len([t for t in gt_throws if t.get("ring") != "miss"])
        total_gt += gt_count
        total_detected += result["darts"]

        calib_str = "OK" if result["calibrated"] else "FAIL"
        if result["error"]:
            calib_str = "ERR"

        hit_pct = ""
        if gt_count > 0:
            # Simple hit rate: detected / expected (capped at 100%)
            rate = min(result["darts"] / gt_count * 100, 100) if gt_count > 0 else 0
            hit_pct = f"{rate:.0f}%"

        print(f"{fname:<30} {result['frames']:>7} {calib_str:>5} {result['darts']:>6} "
              f"{gt_count:>4} {hit_pct:>5} {result['fps']:>6} {result['elapsed_s']:>6}s")

        # Print detected darts
        for i, d in enumerate(result["dart_details"]):
            sector = d.get("sector", "?")
            ring = d.get("ring", "?")
            score = d.get("score", "?")
            frame = result["dart_frames"][i] if i < len(result["dart_frames"]) else "?"
            print(f"  detected: {ring} {sector} = {score} (frame ~{frame})")

        if result["error"]:
            print(f"  ERROR: {result['error'][:80]}")

    # Summary
    print("-" * 85)
    total_frames = sum(r["frames"] for r in results)
    calib_ok = sum(1 for r in results if r["calibrated"])
    errors = sum(1 for r in results if r["error"])
    overall_hit = f"{total_detected}/{total_gt}" if total_gt > 0 else "n/a"
    overall_pct = f"({total_detected/total_gt*100:.0f}%)" if total_gt > 0 else ""
    print(f"Total: {total_frames} frames, {total_detected} detected, "
          f"{total_gt} ground truth, hit rate: {overall_hit} {overall_pct}")
    print(f"Calibration: {calib_ok}/{len(results)} videos, {errors} errors")


if __name__ == "__main__":
    main()
