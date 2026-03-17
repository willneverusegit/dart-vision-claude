"""Generate synthetic dart-throw video clips with ground-truth annotations.

Creates a short video where a white blob (simulated dart tip) appears at known
positions on a 400x400 ROI-sized frame.  A matching ground-truth JSON is written
alongside the video so that the E2E accuracy test can verify detections.

Usage (standalone):
    python -m tests.e2e.generate_synthetic_clip --out tests/replays/synthetic_01

This produces:
    tests/replays/synthetic_01.avi
    tests/ground_truth/synthetic_01.json
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import cv2
import numpy as np


# Board layout constants (must match default geometry in src/cv/geometry.py)
ROI_SIZE = 400
CENTER = ROI_SIZE // 2  # 200
BOARD_RADIUS_PX = 200.0

# Normalized ring boundaries (from geometry.py)
BULL_INNER_NORM = 6.35 / 170.0
BULL_OUTER_NORM = 15.9 / 170.0
TRIPLE_INNER_NORM = 99.0 / 170.0
TRIPLE_OUTER_NORM = 107.0 / 170.0
DOUBLE_INNER_NORM = 162.0 / 170.0
DOUBLE_OUTER_NORM = 170.0 / 170.0

SECTOR_ORDER = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)
SECTOR_ANGLE_DEG = 18.0


def _polar_to_roi(r_norm: float, angle_deg: float) -> tuple[int, int]:
    """Convert board polar coords to ROI pixel coords."""
    r_px = r_norm * BOARD_RADIUS_PX
    # angle_deg: 0=12 o'clock, clockwise → convert to math angle
    math_angle = math.radians(-(angle_deg - 90.0))
    x = int(CENTER + r_px * math.cos(math_angle))
    y = int(CENTER - r_px * math.sin(math_angle))
    return (x, y)


def _expected_score(r_norm: float, angle_deg: float) -> dict:
    """Compute the expected score for a given polar position."""
    # Ring
    if r_norm < BULL_INNER_NORM:
        return {"score": 50, "sector": 25, "ring": "inner_bull", "multiplier": 1}
    elif r_norm < BULL_OUTER_NORM:
        return {"score": 25, "sector": 25, "ring": "outer_bull", "multiplier": 1}
    elif r_norm >= DOUBLE_OUTER_NORM:
        return {"score": 0, "sector": 0, "ring": "miss", "multiplier": 0}

    # Sector
    adjusted = (angle_deg + SECTOR_ANGLE_DEG / 2.0) % 360.0
    sector_index = int(adjusted / SECTOR_ANGLE_DEG) % 20
    sector_value = SECTOR_ORDER[sector_index]

    if TRIPLE_INNER_NORM <= r_norm < TRIPLE_OUTER_NORM:
        return {"score": sector_value * 3, "sector": sector_value, "ring": "triple", "multiplier": 3}
    elif DOUBLE_INNER_NORM <= r_norm < DOUBLE_OUTER_NORM:
        return {"score": sector_value * 2, "sector": sector_value, "ring": "double", "multiplier": 2}
    else:
        return {"score": sector_value, "sector": sector_value, "ring": "single", "multiplier": 1}


# Predefined throws: (r_norm, angle_deg, tag)
DEFAULT_THROWS = [
    (0.0, 0.0, "bullseye"),                          # Inner bull
    (BULL_INNER_NORM + 0.02, 0.0, "outer_bull"),     # Outer bull
    (0.5, 0.0, "single_20"),                          # Single 20 (12 o'clock)
    ((TRIPLE_INNER_NORM + TRIPLE_OUTER_NORM) / 2, 0.0, "triple_20"),  # Triple 20
    ((DOUBLE_INNER_NORM + DOUBLE_OUTER_NORM) / 2, 0.0, "double_20"),  # Double 20
    (0.5, 90.0, "single_6"),                          # Single 6 (3 o'clock)
    (0.5, 180.0, "single_3"),                         # Single 3 (6 o'clock)
    (0.5, 270.0, "single_11"),                        # Single 11 (9 o'clock)
    ((TRIPLE_INNER_NORM + TRIPLE_OUTER_NORM) / 2, 162.0, "triple_19"),  # Triple 19
    ((DOUBLE_INNER_NORM + DOUBLE_OUTER_NORM) / 2, 306.0, "double_9"),   # Double 9
]

# MOG2 needs ~15 frames to build a stable background model.
BG_WARMUP_FRAMES = 20
# Per throw: blank → blob → blank (with dart removal reset between throws)
BLANK_BEFORE = 10
BLOB_FRAMES = 8   # 3 for confirmation + margin
BLANK_AFTER = 10
FRAMES_PER_THROW = BLANK_BEFORE + BLOB_FRAMES + BLANK_AFTER


def generate_clip(
    output_dir: str | Path,
    name: str = "synthetic_01",
    throws: list[tuple[float, float, str]] | None = None,
    blob_radius: int = 18,
    fps: int = 30,
) -> tuple[str, str]:
    """Generate a synthetic clip and ground-truth JSON.

    Returns (video_path, ground_truth_path).
    """
    output_dir = Path(output_dir)
    throws = throws or DEFAULT_THROWS

    replays_dir = output_dir / "replays"
    gt_dir = output_dir / "ground_truth"
    replays_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)

    video_path = str(replays_dir / f"{name}.avi")
    gt_path = str(gt_dir / f"{name}.json")

    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(video_path, fourcc, fps, (ROI_SIZE, ROI_SIZE))

    ground_truth_events = []
    frame_index = 0

    # Warmup: blank frames so MOG2 can build a stable background model
    for _ in range(BG_WARMUP_FRAMES):
        blank = np.zeros((ROI_SIZE, ROI_SIZE, 3), dtype=np.uint8)
        writer.write(blank)
        frame_index += 1

    for r_norm, angle_deg, tag in throws:
        px, py = _polar_to_roi(r_norm, angle_deg)
        expected = _expected_score(r_norm, angle_deg)

        # Blank frames before
        for _ in range(BLANK_BEFORE):
            blank = np.zeros((ROI_SIZE, ROI_SIZE, 3), dtype=np.uint8)
            writer.write(blank)
            frame_index += 1

        # Blob frames (simulated dart)
        blob_start = frame_index
        for _ in range(BLOB_FRAMES):
            frame = np.zeros((ROI_SIZE, ROI_SIZE, 3), dtype=np.uint8)
            cv2.circle(frame, (px, py), blob_radius, (255, 255, 255), -1)
            writer.write(frame)
            frame_index += 1

        ground_truth_events.append({
            "frame_index": blob_start,
            "raw_point_px": [px, py],
            "expected": expected,
            "tag": tag,
        })

        # Blank frames after (dart removal)
        for _ in range(BLANK_AFTER):
            blank = np.zeros((ROI_SIZE, ROI_SIZE, 3), dtype=np.uint8)
            writer.write(blank)
            frame_index += 1

    writer.release()

    ground_truth = {
        "video": f"{name}.avi",
        "total_frames": frame_index,
        "fps": fps,
        "throws": len(throws),
        "events": ground_truth_events,
    }

    with open(gt_path, "w") as f:
        json.dump(ground_truth, f, indent=2)

    return video_path, gt_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tests", help="Output base directory")
    parser.add_argument("--name", default="synthetic_01")
    args = parser.parse_args()
    vp, gp = generate_clip(args.out, args.name)
    print(f"Video: {vp}")
    print(f"Ground truth: {gp}")
