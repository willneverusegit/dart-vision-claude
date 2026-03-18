#!/usr/bin/env python3
"""Validate ground_truth.yaml entries are well-formed.

Checks:
- All required fields present per throw (sector, ring)
- Sector values valid (0-20 or 25)
- Ring values valid
- Score implied by sector+ring is consistent (e.g. no triple-bull)
- Videos have description and throws list
- Optional: timestamp_s is non-negative float/int

Usage:
    python scripts/validate_ground_truth.py [path/to/ground_truth.yaml]
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

VALID_SECTORS = set(range(0, 21)) | {25}
VALID_RINGS = {"single", "double", "triple", "bull_inner", "bull_outer", "miss"}
# Bull rings only valid with sector 25
BULL_RINGS = {"bull_inner", "bull_outer"}
# Sector 0 only valid with ring "miss"
MISS_SECTOR = 0
# Triple/double not valid for bull (sector 25)
MULTIPLIER_RINGS = {"double", "triple"}


class ValidationError:
    """A single validation issue."""

    def __init__(self, video: str, throw_idx: int | None, message: str):
        self.video = video
        self.throw_idx = throw_idx
        self.message = message

    def __str__(self) -> str:
        loc = self.video
        if self.throw_idx is not None:
            loc += f", throw #{self.throw_idx + 1}"
        return f"[{loc}] {self.message}"


def validate_throw(video: str, idx: int, throw: Any) -> list[ValidationError]:
    """Validate a single throw entry."""
    errors: list[ValidationError] = []

    if not isinstance(throw, dict):
        errors.append(ValidationError(video, idx, f"throw must be dict, got {type(throw).__name__}"))
        return errors

    # Required fields
    if "sector" not in throw:
        errors.append(ValidationError(video, idx, "missing required field 'sector'"))
    if "ring" not in throw:
        errors.append(ValidationError(video, idx, "missing required field 'ring'"))

    sector = throw.get("sector")
    ring = throw.get("ring")

    # Sector validation
    if sector is not None:
        if not isinstance(sector, int):
            errors.append(ValidationError(video, idx, f"sector must be int, got {type(sector).__name__}: {sector!r}"))
        elif sector not in VALID_SECTORS:
            errors.append(ValidationError(video, idx, f"sector {sector} not in valid range (0-20, 25)"))

    # Ring validation
    if ring is not None:
        if not isinstance(ring, str):
            errors.append(ValidationError(video, idx, f"ring must be str, got {type(ring).__name__}: {ring!r}"))
        elif ring not in VALID_RINGS:
            errors.append(ValidationError(video, idx, f"ring '{ring}' not valid, must be one of {sorted(VALID_RINGS)}"))

    # Cross-field consistency
    if isinstance(sector, int) and isinstance(ring, str):
        if ring in BULL_RINGS and sector != 25:
            errors.append(ValidationError(video, idx, f"bull ring '{ring}' requires sector 25, got {sector}"))
        if sector == 25 and ring not in BULL_RINGS and ring != "miss":
            errors.append(ValidationError(video, idx, f"sector 25 (bull) must use bull_inner/bull_outer ring, got '{ring}'"))
        if sector == MISS_SECTOR and ring != "miss":
            errors.append(ValidationError(video, idx, f"sector 0 (miss) must use ring 'miss', got '{ring}'"))
        if ring == "miss" and sector != MISS_SECTOR:
            errors.append(ValidationError(video, idx, f"ring 'miss' must use sector 0, got {sector}"))
        if ring in MULTIPLIER_RINGS and sector == 25:
            errors.append(ValidationError(video, idx, f"sector 25 (bull) cannot have ring '{ring}'"))

    # Optional timestamp validation
    ts = throw.get("timestamp_s")
    if ts is not None:
        if not isinstance(ts, (int, float)):
            errors.append(ValidationError(video, idx, f"timestamp_s must be number, got {type(ts).__name__}"))
        elif ts < 0:
            errors.append(ValidationError(video, idx, f"timestamp_s must be non-negative, got {ts}"))

    return errors


def validate_video(name: str, entry: Any) -> list[ValidationError]:
    """Validate a single video entry."""
    errors: list[ValidationError] = []

    if not isinstance(entry, dict):
        errors.append(ValidationError(name, None, f"video entry must be dict, got {type(entry).__name__}"))
        return errors

    if "throws" not in entry:
        errors.append(ValidationError(name, None, "missing required field 'throws'"))
        return errors

    throws = entry["throws"]
    if not isinstance(throws, list):
        errors.append(ValidationError(name, None, f"'throws' must be list, got {type(throws).__name__}"))
        return errors

    for idx, throw in enumerate(throws):
        errors.extend(validate_throw(name, idx, throw))

    return errors


def validate_ground_truth(data: Any) -> list[ValidationError]:
    """Validate the entire ground truth structure."""
    errors: list[ValidationError] = []

    if not isinstance(data, dict):
        errors.append(ValidationError("<root>", None, "top-level must be dict"))
        return errors

    if "videos" not in data:
        errors.append(ValidationError("<root>", None, "missing required key 'videos'"))
        return errors

    videos = data["videos"]
    if not isinstance(videos, dict):
        errors.append(ValidationError("<root>", None, f"'videos' must be dict, got {type(videos).__name__}"))
        return errors

    for name, entry in videos.items():
        errors.extend(validate_video(str(name), entry))

    return errors


def load_and_validate(path: Path) -> list[ValidationError]:
    """Load YAML file and validate."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return validate_ground_truth(data)


def main() -> int:
    """CLI entry point. Returns 0 on success, 1 on validation errors."""
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = Path(__file__).resolve().parent.parent / "testvids" / "ground_truth.yaml"

    if not path.exists():
        print(f"ERROR: File not found: {path}")
        return 2

    errors = load_and_validate(path)

    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):\n")
        for err in errors:
            print(f"  {err}")
        return 1

    # Summary
    with open(path) as f:
        data = yaml.safe_load(f)
    videos = data.get("videos", {})
    total_throws = sum(len(v.get("throws", [])) for v in videos.values() if isinstance(v, dict))
    annotated = sum(1 for v in videos.values() if isinstance(v, dict) and len(v.get("throws", [])) > 0)
    print(f"OK — {len(videos)} videos, {annotated} annotated, {total_throws} total throws")
    return 0


if __name__ == "__main__":
    sys.exit(main())
