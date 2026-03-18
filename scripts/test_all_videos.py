"""Batch-test all videos in testvids/ through the dart detection pipeline.

Usage:
    python scripts/test_all_videos.py --marker-size 100
    python scripts/test_all_videos.py --source-dir testvids --marker-size 100 --max-frames 300
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.cv.pipeline import DartPipeline  # noqa: E402


def test_video(path: str, marker_size_mm: float | None,
               marker_spacing_mm: float | None, max_frames: int) -> dict:
    """Run pipeline on a single video file, return stats."""
    darts_detected: list[dict] = []

    def on_dart(score: dict, detection=None) -> None:
        darts_detected.append(score)

    pipeline = DartPipeline(
        camera_src=path,
        on_dart_detected=on_dart,
        marker_size_mm=marker_size_mm,
        marker_spacing_mm=marker_spacing_mm,
    )

    frames_processed = 0
    t0 = time.perf_counter()
    error: str | None = None

    try:
        pipeline.start()
        while frames_processed < max_frames:
            result = pipeline.process_frame()
            if result is None:
                break
            frames_processed += 1
    except Exception as exc:
        error = str(exc)
    finally:
        pipeline.stop()

    elapsed = time.perf_counter() - t0
    fps = frames_processed / elapsed if elapsed > 0 else 0.0

    return {
        "file": os.path.basename(path),
        "frames": frames_processed,
        "darts": len(darts_detected),
        "fps": round(fps, 1),
        "elapsed_s": round(elapsed, 1),
        "error": error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-test videos through dart pipeline")
    parser.add_argument("--source-dir", default="testvids", help="Directory with .mp4 files")
    parser.add_argument("--marker-size", type=float, default=None,
                        help="ArUco marker edge length in mm (default: from config or 75)")
    parser.add_argument("--marker-spacing", type=float, default=None,
                        help="ArUco marker center-to-center distance in mm (default: 430)")
    parser.add_argument("--max-frames", type=int, default=500,
                        help="Max frames to process per video (default: 500)")
    args = parser.parse_args()

    videos = sorted(glob.glob(os.path.join(args.source_dir, "*.mp4")))
    if not videos:
        print(f"No .mp4 files found in {args.source_dir}/")
        sys.exit(1)

    print(f"Found {len(videos)} video(s) in {args.source_dir}/")
    if args.marker_size:
        print(f"Marker size: {args.marker_size}mm")
    if args.marker_spacing:
        print(f"Marker spacing: {args.marker_spacing}mm")
    print()

    # Header
    print(f"{'File':<15} {'Frames':>7} {'Darts':>6} {'FPS':>6} {'Time':>7} {'Status'}")
    print("-" * 60)

    results = []
    for vpath in videos:
        result = test_video(vpath, args.marker_size, args.marker_spacing, args.max_frames)
        results.append(result)
        status = "OK" if result["error"] is None else f"ERR: {result['error'][:30]}"
        print(f"{result['file']:<15} {result['frames']:>7} {result['darts']:>6} "
              f"{result['fps']:>6} {result['elapsed_s']:>6}s {status}")

    # Summary
    print("-" * 60)
    total_frames = sum(r["frames"] for r in results)
    total_darts = sum(r["darts"] for r in results)
    errors = sum(1 for r in results if r["error"])
    print(f"Total: {total_frames} frames, {total_darts} darts detected, {errors} errors")


if __name__ == "__main__":
    main()
