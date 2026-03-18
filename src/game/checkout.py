"""Checkout suggestions for X01 games."""

# Common checkouts: score -> list of suggested throws (most common first)
# Format: each suggestion is a string like "T20 D16" or "T19 T12 D18"
CHECKOUTS: dict[int, list[str]] = {}

# Standard professional checkouts (PDC-preferred paths).
# These are inserted first so they appear as the top suggestion.
_STANDARD_CHECKOUTS: dict[int, str] = {
    170: "T20 T20 D25",
    167: "T20 T19 D25",
    164: "T20 T18 D25",
    161: "T20 T17 D25",
    160: "T20 T20 D20",
    158: "T20 T20 D19",
    157: "T20 T19 D20",
    156: "T20 T20 D18",
    155: "T20 T19 D19",
    154: "T20 T18 D20",
    153: "T20 T19 D18",
    152: "T20 T20 D16",
    151: "T20 T17 D20",
    150: "T20 T18 D18",
    149: "T20 T19 D16",
    148: "T20 T16 D20",
    147: "T20 T17 D18",
    146: "T20 T18 D16",
    145: "T20 T15 D20",
    144: "T20 T20 D12",
    143: "T20 T17 D16",
    142: "T20 T14 D20",
    141: "T20 T19 D12",
    140: "T20 T20 D10",
    139: "T20 T13 D20",
    138: "T20 T18 D12",
    137: "T20 T15 D16",
    136: "T20 T20 D8",
    135: "T20 T17 D12",
    134: "T20 T14 D16",
    133: "T20 T19 D8",
    132: "T20 T16 D12",
    131: "T20 T13 D16",
    130: "T20 T18 D8",
    129: "T19 T16 D12",
    128: "T18 T14 D16",
    127: "T20 T17 D8",
    126: "T19 T19 D6",
    125: "T20 T15 D10",  # or T18 T19 D7
    124: "T20 T16 D8",
    123: "T19 T16 D9",
    122: "T18 T18 D7",
    121: "T20 T11 D14",
    120: "T20 S20 D20",
    119: "T19 T12 D13",
    118: "T20 S18 D20",
    117: "T20 S17 D20",
    116: "T20 S16 D20",
    115: "T20 S15 D20",
    114: "T20 S14 D20",
    113: "T20 S13 D20",
    112: "T20 S12 D20",
    111: "T20 S19 D16",
    110: "T20 S10 D20",
    109: "T20 S9 D20",
    108: "T20 S16 D16",
    107: "T19 S10 D20",
    106: "T20 S6 D20",
    105: "T20 S5 D20",
    104: "T18 S10 D20",
    103: "T20 S3 D20",
    102: "T20 S10 D16",
    101: "T20 S1 D20",
    100: "T20 D20",
    99: "T19 S10 D16",
    98: "T20 D19",
    97: "T19 D20",
    96: "T20 D18",
    95: "T19 D19",
    94: "T18 D20",
    93: "T19 D18",
    92: "T20 D16",
    91: "T17 D20",
    90: "T18 D18",
    89: "T19 D16",
    88: "T16 D20",
    87: "T17 D18",
    86: "T18 D16",
    85: "T15 D20",
    84: "T20 D12",
    83: "T17 D16",
    82: "T14 D20",
    81: "T19 D12",
    80: "T20 D10",
    79: "T13 D20",
    78: "T18 D12",
    77: "T15 D16",
    76: "T20 D8",
    75: "T17 D12",
    74: "T14 D16",
    73: "T19 D8",
    72: "T16 D12",
    71: "T13 D16",
    70: "T18 D8",
    69: "T19 D6",
    68: "T20 D4",
    67: "T17 D8",
    66: "T10 D18",
    65: "T19 D4",
    64: "T16 D8",
    63: "T13 D12",
    62: "T10 D16",
    61: "T15 D8",
}


def _build_checkouts():
    """Build lookup table for checkouts 2-170."""
    # Pre-populate with standard professional checkouts
    for score, path in _STANDARD_CHECKOUTS.items():
        CHECKOUTS[score] = [path]

    def _add(score: int, path: str) -> None:
        """Add a checkout path if not duplicate and under limit of 3."""
        if score not in CHECKOUTS:
            CHECKOUTS[score] = [path]
        elif len(CHECKOUTS[score]) < 3 and path not in CHECKOUTS[score]:
            CHECKOUTS[score].append(path)

    # Phase 1: Direct double finishes (2-40 even numbers + Bull)
    for d_val, d_name in [(i * 2, f"D{i}") for i in range(1, 21)] + [(50, "D25")]:
        _add(d_val, d_name)

    # Phase 2: Single + Double finishes
    for d_val, d_name in [(i * 2, f"D{i}") for i in range(1, 21)] + [(50, "D25")]:
        for s in range(1, 21):
            score = s + d_val
            if score <= 60:
                _add(score, f"S{s} {d_name}")

        # Single Bull + Double
        score_sb = 25 + d_val
        if score_sb <= 75:
            _add(score_sb, f"S25 {d_name}")

    # Phase 3: Triple + Double finishes (for 61-170)
    for t in range(1, 21):
        t_val = t * 3
        t_name = f"T{t}"
        for d in range(1, 21):
            d_val = d * 2
            score = t_val + d_val
            if 2 <= score <= 170:
                _add(score, f"{t_name} D{d}")
        # Triple + Bull
        score_tb = t_val + 50
        if score_tb <= 170:
            _add(score_tb, f"{t_name} D25")

    # Triple + Triple + Double finishes (for high scores like 170)
    for t1 in range(1, 21):
        t1_val = t1 * 3
        t1_name = f"T{t1}"
        for t2 in range(t1, 21):
            t2_val = t2 * 3
            t2_name = f"T{t2}"
            for d in range(1, 21):
                d_val = d * 2
                score = t1_val + t2_val + d_val
                if 2 <= score <= 170:
                    # Put highest triple first
                    path = f"{t2_name} {t1_name} D{d}" if t2 > t1 else f"{t1_name} {t2_name} D{d}"
                    _add(score, path)
            # Triple + Triple + Bull
            score_ttb = t1_val + t2_val + 50
            if 2 <= score_ttb <= 170:
                path = f"{t2_name} {t1_name} D25" if t2 > t1 else f"{t1_name} {t2_name} D25"
                _add(score_ttb, path)

    # Two-dart paths: Triple + Single + Double (for missing scores)
    for t in range(1, 21):
        t_val = t * 3
        t_name = f"T{t}"
        for s in range(1, 21):
            for d in range(1, 21):
                d_val = d * 2
                score = t_val + s + d_val
                if 2 <= score <= 170:
                    _add(score, f"{t_name} S{s} D{d}")

_build_checkouts()

def get_checkout(remaining: int, darts_left: int = 3) -> list[str]:
    """Get checkout suggestions for a remaining score.

    Returns up to 3 suggestions, filtered by number of darts available.
    """
    if remaining < 2 or remaining > 170:
        return []
    suggestions = CHECKOUTS.get(remaining, [])
    # Filter by darts available
    filtered = [s for s in suggestions if s.count(" ") < darts_left]
    return filtered[:3]
