"""Helper to add or update ground truth entries in testvids/ground_truth.yaml.

Usage:
    # Interactive: prompts for throws
    python scripts/add_ground_truth.py testvids/new_video.mp4

    # Quick-add a single throw
    python scripts/add_ground_truth.py testvids/new_video.mp4 --throw "20 triple 3.2"

    # Validate existing ground_truth.yaml
    python scripts/add_ground_truth.py --validate

    # Show summary of ground truth coverage
    python scripts/add_ground_truth.py --summary
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import yaml

VALID_RINGS = {"single", "double", "triple", "bull_inner", "bull_outer", "miss"}
VALID_SECTORS = set(range(0, 21)) | {25}  # 0=miss, 1-20, 25=bull

GT_PATH_DEFAULT = os.path.join(
    os.path.dirname(__file__), "..", "testvids", "ground_truth.yaml"
)


def validate_throw(throw: dict, video_name: str, index: int) -> list[str]:
    """Validate a single throw entry, return list of error strings."""
    errors = []
    sector = throw.get("sector")
    ring = throw.get("ring")

    if sector is None:
        errors.append(f"{video_name} throw #{index + 1}: missing 'sector'")
    elif sector not in VALID_SECTORS:
        errors.append(
            f"{video_name} throw #{index + 1}: invalid sector {sector} "
            f"(valid: 0-20, 25)"
        )

    if ring is None:
        errors.append(f"{video_name} throw #{index + 1}: missing 'ring'")
    elif ring not in VALID_RINGS:
        errors.append(
            f"{video_name} throw #{index + 1}: invalid ring '{ring}' "
            f"(valid: {sorted(VALID_RINGS)})"
        )

    # Cross-validate sector/ring combinations
    if sector == 0 and ring != "miss":
        errors.append(
            f"{video_name} throw #{index + 1}: sector 0 must have ring 'miss'"
        )
    if ring == "miss" and sector != 0:
        errors.append(
            f"{video_name} throw #{index + 1}: ring 'miss' must have sector 0"
        )
    if sector == 25 and ring not in ("bull_inner", "bull_outer"):
        errors.append(
            f"{video_name} throw #{index + 1}: sector 25 must have "
            f"ring 'bull_inner' or 'bull_outer'"
        )
    if ring in ("bull_inner", "bull_outer") and sector != 25:
        errors.append(
            f"{video_name} throw #{index + 1}: ring '{ring}' must have sector 25"
        )

    ts = throw.get("timestamp_s")
    if ts is not None and (not isinstance(ts, (int, float)) or ts < 0):
        errors.append(
            f"{video_name} throw #{index + 1}: invalid timestamp_s={ts}"
        )

    return errors


def validate_ground_truth(gt_path: str) -> list[str]:
    """Validate entire ground_truth.yaml, return list of error strings."""
    if not os.path.exists(gt_path):
        return [f"File not found: {gt_path}"]

    with open(gt_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "videos" not in data:
        return ["Missing 'videos' top-level key"]

    errors = []
    videos = data["videos"]

    for fname, entry in videos.items():
        if not fname.endswith(".mp4"):
            errors.append(f"Video key '{fname}' does not end with .mp4")
        if entry is None:
            errors.append(f"{fname}: entry is null")
            continue
        throws = entry.get("throws")
        if throws is None:
            errors.append(f"{fname}: missing 'throws' key")
            continue
        if not isinstance(throws, list):
            errors.append(f"{fname}: 'throws' must be a list")
            continue

        # Check timestamp ordering
        timestamps = [
            t.get("timestamp_s")
            for t in throws
            if t.get("timestamp_s") is not None
        ]
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i - 1]:
                errors.append(
                    f"{fname}: timestamps not in order at throw #{i + 1} "
                    f"({timestamps[i - 1]}s -> {timestamps[i]}s)"
                )

        for idx, throw in enumerate(throws):
            errors.extend(validate_throw(throw, fname, idx))

    return errors


def parse_throw_string(s: str) -> dict:
    """Parse a throw string like '20 triple 3.2' into a dict.

    Format: <sector> <ring> [<timestamp_s>]
    """
    parts = s.strip().split()
    if len(parts) < 2:
        raise ValueError(
            f"Expected '<sector> <ring> [timestamp_s]', got: '{s}'"
        )

    sector = int(parts[0])
    ring = parts[1]
    timestamp_s = float(parts[2]) if len(parts) > 2 else None

    entry = {"sector": sector, "ring": ring}
    if timestamp_s is not None:
        entry["timestamp_s"] = timestamp_s

    errs = validate_throw(entry, "<input>", 0)
    if errs:
        raise ValueError("; ".join(errs))

    return entry


def load_or_create_gt(gt_path: str) -> dict:
    """Load existing ground truth or create empty structure."""
    if os.path.exists(gt_path):
        with open(gt_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "videos" not in data:
            data["videos"] = {}
        return data
    return {"videos": {}}


def save_gt(gt_path: str, data: dict) -> None:
    """Save ground truth YAML with consistent formatting."""
    with open(gt_path, "w", encoding="utf-8") as f:
        f.write("# Ground Truth Annotation fuer Testvideos\n")
        f.write("#\n")
        f.write("# Format pro Wurf:\n")
        f.write("#   - sector: Zahlensegment (1-20, 25 fuer Bull)\n")
        f.write(
            '#   - ring: "single", "double", "triple", '
            '"bull_inner", "bull_outer"\n'
        )
        f.write("#   - timestamp_s: ungefaehre Sekunde im Video (optional)\n\n")
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )


def print_summary(gt_path: str) -> None:
    """Print summary of ground truth coverage."""
    if not os.path.exists(gt_path):
        print(f"No ground truth file at {gt_path}")
        return

    with open(gt_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    videos = (data or {}).get("videos", {})
    testvids_dir = os.path.dirname(gt_path)
    mp4s = {
        os.path.basename(p)
        for p in glob.glob(os.path.join(testvids_dir, "*.mp4"))
    }

    print(f"Ground truth: {gt_path}")
    print(f"{'Video':<35} {'Throws':>7} {'File?':>6}")
    print("-" * 55)

    total_throws = 0
    annotated = 0
    for fname, entry in videos.items():
        throws = entry.get("throws", []) if entry else []
        n = len(throws)
        total_throws += n
        exists = "YES" if fname in mp4s else "NO"
        if n > 0:
            annotated += 1
        print(f"{fname:<35} {n:>7} {exists:>6}")

    # Videos on disk but not in GT
    missing = mp4s - set(videos.keys())
    for fname in sorted(missing):
        print(f"{fname:<35} {'---':>7} {'YES':>6}  (not in GT)")

    print("-" * 55)
    print(
        f"Total: {len(videos)} entries, {annotated} annotated, "
        f"{total_throws} throws, {len(missing)} videos without GT"
    )


def interactive_add(gt_path: str, video_path: str) -> None:
    """Interactively add throws for a video."""
    fname = os.path.basename(video_path)
    data = load_or_create_gt(gt_path)

    if fname in data["videos"]:
        existing = data["videos"][fname].get("throws", [])
        print(f"{fname} already has {len(existing)} throws.")
        resp = input("Append (a), Replace (r), or Cancel (c)? ").strip().lower()
        if resp == "c":
            return
        if resp == "r":
            existing = []
    else:
        existing = []

    print(f"\nAdding throws for {fname}")
    print("Format: <sector> <ring> [timestamp_s]")
    print("Example: 20 triple 3.2")
    print("Enter empty line to finish.\n")

    throws = list(existing)
    while True:
        try:
            line = input(f"  Throw #{len(throws) + 1}: ").strip()
        except EOFError:
            break
        if not line:
            break
        try:
            entry = parse_throw_string(line)
            throws.append(entry)
            print(f"    -> Added: {entry}")
        except ValueError as e:
            print(f"    ERROR: {e}")

    data["videos"][fname] = {
        "description": "",
        "throws": throws,
    }
    save_gt(gt_path, data)
    print(f"\nSaved {len(throws)} throws for {fname}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage ground truth entries for dart test videos"
    )
    parser.add_argument("video", nargs="?", help="Path to .mp4 video file")
    parser.add_argument(
        "--throw",
        action="append",
        help="Quick-add throw: '<sector> <ring> [timestamp_s]'",
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate ground_truth.yaml"
    )
    parser.add_argument(
        "--summary", action="store_true", help="Show GT coverage summary"
    )
    parser.add_argument("--gt-path", default=GT_PATH_DEFAULT, help="Path to YAML")
    args = parser.parse_args()

    if args.validate:
        errors = validate_ground_truth(args.gt_path)
        if errors:
            print(f"VALIDATION ERRORS ({len(errors)}):")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)
        else:
            print("Ground truth validation: OK")
            sys.exit(0)

    if args.summary:
        print_summary(args.gt_path)
        sys.exit(0)

    if not args.video:
        parser.print_help()
        sys.exit(1)

    if args.throw:
        # Quick-add mode (non-interactive)
        fname = os.path.basename(args.video)
        data = load_or_create_gt(args.gt_path)
        existing = (
            data["videos"].get(fname, {}).get("throws", [])
            if fname in data["videos"]
            else []
        )
        for t_str in args.throw:
            entry = parse_throw_string(t_str)
            existing.append(entry)
            print(f"Added: {entry}")
        data["videos"][fname] = {"description": "", "throws": existing}
        save_gt(args.gt_path, data)
        print(f"Saved {len(existing)} throws for {fname}")
    else:
        interactive_add(args.gt_path, args.video)


if __name__ == "__main__":
    main()
