"""Validate tip detection against real diagnostic captures.

Reads thresh images from diagnostics/, runs tip detection on the largest
contour, and prints results alongside the original centroid for comparison.
Also generates a visual overlay showing centroid (red) vs tip (cyan).
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cv.tip_detection import find_dart_tip


def validate_camera(diag_dir: Path, output_dir: Path) -> None:
    """Run tip detection on all thresh images in a diagnostics directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    thresh_files = sorted(diag_dir.glob("*_thresh.png"))
    if not thresh_files:
        print(f"  No thresh images found in {diag_dir}")
        return

    for thresh_path in thresh_files:
        ts = thresh_path.name.replace("_thresh.png", "")

        # Load thresh mask and find contour
        thresh = cv2.imread(str(thresh_path), cv2.IMREAD_GRAYSCALE)
        if thresh is None:
            print(f"  {ts}: could not load thresh image")
            continue

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            print(f"  {ts}: no contours found")
            continue

        largest = max(contours, key=cv2.contourArea)

        # Run tip detection
        tip = find_dart_tip(largest)

        # Load original meta for comparison
        meta_path = diag_dir / f"{ts}_meta.json"
        centroid = None
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
            centroid = tuple(meta["centroid"])

        # Calculate distance between centroid and tip
        dist = None
        if tip and centroid:
            dist = np.sqrt((tip[0] - centroid[0])**2 + (tip[1] - centroid[1])**2)

        status = "OK" if tip else "FAIL"
        print(f"  {ts}: {status}  centroid={centroid}  tip={tip}  dist={dist:.1f}px" if dist else
              f"  {ts}: {status}  centroid={centroid}  tip={tip}")

        # Generate visual overlay on contour image
        contour_path = diag_dir / f"{ts}_contour.png"
        if contour_path.exists():
            img = cv2.imread(str(contour_path))
            if img is not None and tip is not None:
                cv2.circle(img, tip, 7, (255, 255, 0), 2)  # Cyan ring = tip
                if centroid:
                    cv2.line(img, centroid, tip, (0, 255, 255), 1)
                cv2.imwrite(str(output_dir / f"{ts}_tip_overlay.png"), img)


def main():
    project_root = Path(__file__).parent.parent
    diag_root = project_root / "diagnostics"

    if not diag_root.exists():
        print("No diagnostics/ directory found")
        return

    output_root = project_root / "diagnostics" / "tip_validation"

    for cam_dir in sorted(diag_root.iterdir()):
        if cam_dir.is_dir() and cam_dir.name.startswith("cam_"):
            print(f"\n=== {cam_dir.name} ===")
            validate_camera(cam_dir, output_root / cam_dir.name)

    print(f"\nOverlays saved to: {output_root}")


if __name__ == "__main__":
    main()
