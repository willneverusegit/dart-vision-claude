"""Checkout suggestions for X01 games."""

# Common checkouts: score -> list of suggested throws (most common first)
# Format: each suggestion is a string like "T20 D16" or "T19 T12 D18"
CHECKOUTS: dict[int, list[str]] = {}

# Preferred "standard" checkouts used by professional players.
# These override the algorithmically generated first suggestion.
# Source: PDC / BDO standard checkout chart.
PREFERRED_CHECKOUTS: dict[int, list[str]] = {
    170: ["T20 T20 D25"],
    167: ["T20 T19 D25"],
    164: ["T20 T18 D25"],
    161: ["T20 T17 D25"],
    160: ["T20 T20 D20"],
    158: ["T20 T20 D19"],
    157: ["T20 T19 D20"],
    156: ["T20 T20 D18"],
    155: ["T20 T19 D19"],
    154: ["T20 T18 D20"],
    153: ["T20 T19 D18"],
    152: ["T20 T20 D16"],
    151: ["T20 T17 D20"],
    150: ["T20 T18 D18"],
    149: ["T20 T19 D16"],
    148: ["T20 T16 D20"],
    147: ["T20 T17 D18"],
    146: ["T20 T18 D16"],
    145: ["T20 T15 D20"],
    144: ["T20 T20 D12"],
    143: ["T20 T17 D16"],
    142: ["T20 T14 D20"],
    141: ["T20 T19 D12"],
    140: ["T20 T20 D10"],
    139: ["T20 T13 D20"],
    138: ["T20 T18 D12"],
    137: ["T20 T15 D16"],
    136: ["T20 T20 D8"],
    135: ["T20 T17 D12"],
    134: ["T20 T14 D16"],
    133: ["T20 T19 D8"],
    132: ["T20 T16 D12"],
    131: ["T20 T13 D16"],
    130: ["T20 T18 D8"],
    129: ["T19 T16 D12"],
    128: ["T18 T14 D16"],
    127: ["T20 T17 D8"],
    126: ["T19 T19 D6"],
    125: ["T20 T15 D10", "S25 T20 D20"],
    124: ["T20 T16 D8"],
    123: ["T19 T16 D9"],
    122: ["T18 T18 D7"],
    121: ["T20 T11 D14", "T17 T10 D20"],
    120: ["T20 S20 D20"],
    119: ["T19 T12 D13"],
    118: ["T20 S18 D20"],
    117: ["T20 S17 D20"],
    116: ["T20 S16 D20"],
    115: ["T20 S15 D20"],
    114: ["T20 S14 D20"],
    113: ["T20 S13 D20"],
    112: ["T20 T12 D8"],
    111: ["T20 S11 D20", "T19 S14 D20"],
    110: ["T20 S10 D20", "T20 D25"],
    109: ["T20 S9 D20", "T19 T12 D8"],
    108: ["T20 S8 D20", "T20 S16 D16"],
    107: ["T20 S7 D20", "T19 S10 D20"],
    106: ["T20 S6 D20", "T20 T10 D8"],
    105: ["T20 S5 D20", "T19 S8 D20"],
    104: ["T20 S4 D20", "T18 S10 D20"],
    103: ["T20 S3 D20", "T19 S6 D20"],
    102: ["T20 S2 D20", "T20 T10 D6"],
    101: ["T20 S1 D20", "T17 S10 D20"],
    100: ["T20 D20"],
    99: ["T19 S10 D16", "T19 D21"],  # T19 D21 invalid, keep first
    98: ["T20 D19"],
    97: ["T19 D20"],
    96: ["T20 D18"],
    95: ["T19 D19", "T20 S3 D16", "S25 T20 D5"],
    94: ["T18 D20"],
    93: ["T19 D18"],
    92: ["T20 D16"],
    91: ["T17 D20"],
    90: ["T20 D15", "T18 D18"],
    89: ["T19 D16"],
    88: ["T16 D20"],
    87: ["T17 D18"],
    86: ["T18 D16"],
    85: ["T15 D20", "T19 D14"],
    84: ["T20 D12"],
    83: ["T17 D16"],
    82: ["T14 D20", "D25 D16"],
    81: ["T19 D12", "T15 D18"],
    80: ["T20 D10"],
    79: ["T13 D20", "T19 D11"],
    78: ["T18 D12"],
    77: ["T15 D16", "T19 D10"],
    76: ["T20 D8"],
    75: ["T17 D12"],
    74: ["T14 D16"],
    73: ["T19 D8"],
    72: ["T16 D12"],
    71: ["T13 D16"],
    70: ["T18 D8", "T10 D20"],
    69: ["T19 D6", "S19 D25"],
    68: ["T20 D4", "T16 D10"],
    67: ["T17 D8", "T9 D20"],
    66: ["T10 D18", "T14 D12"],
    65: ["T19 D4", "S25 D20"],
    64: ["T16 D8", "T8 D20"],
    63: ["T13 D12", "T17 D6"],
    62: ["T10 D16", "T12 D13"],
    61: ["T15 D8", "T7 D20"],
    60: ["S20 D20"],
    59: ["S19 D20"],
    58: ["S18 D20"],
    57: ["S17 D20"],
    56: ["S16 D20", "T16 D4"],
    55: ["S15 D20"],
    54: ["S14 D20"],
    53: ["S13 D20"],
    52: ["S12 D20", "T12 D8"],
    51: ["S11 D20", "S19 D16"],
    50: ["D25"],
    49: ["S9 D20", "S17 D16"],
    48: ["S8 D20", "S16 D16"],
    47: ["S7 D20", "S15 D16"],
    46: ["S6 D20", "S14 D16"],
    45: ["S5 D20", "S13 D16"],
    44: ["S4 D20", "S12 D16"],
    43: ["S3 D20", "S11 D16"],
    42: ["S2 D20", "S10 D16"],
    41: ["S1 D20", "S9 D16"],
    40: ["D20"],
    39: ["S7 D16", "S19 D10"],
    38: ["D19"],
    37: ["S5 D16", "S17 D10"],
    36: ["D18"],
    35: ["S3 D16"],
    34: ["D17"],
    33: ["S1 D16", "S17 D8"],
    32: ["D16"],
    31: ["S15 D8", "S7 D12"],
    30: ["D15"],
    29: ["S13 D8", "S5 D12"],
    28: ["D14"],
    27: ["S11 D8", "S3 D12"],
    26: ["D13"],
    25: ["S9 D8", "S1 D12"],
    24: ["D12"],
    23: ["S7 D8"],
    22: ["D11"],
    21: ["S5 D8"],
    20: ["D10"],
    19: ["S3 D8", "S7 D6"],
    18: ["D9"],
    17: ["S1 D8", "S5 D6"],
    16: ["D8"],
    15: ["S7 D4"],
    14: ["D7"],
    13: ["S5 D4"],
    12: ["D6"],
    11: ["S3 D4"],
    10: ["D5"],
    9: ["S1 D4"],
    8: ["D4"],
    7: ["S3 D2"],
    6: ["D3"],
    5: ["S1 D2"],
    4: ["D2"],
    3: ["S1 D1"],
    2: ["D1"],
}


def _build_checkouts():
    """Build lookup table for checkouts 2-170.

    Preferred standard checkouts are used first, then algorithmic
    generation fills gaps and adds alternatives.
    """
    # Start with preferred checkouts
    for score, paths in PREFERRED_CHECKOUTS.items():
        CHECKOUTS[score] = list(paths)

    # Phase 1: Direct double finishes (2-40 even numbers + Bull)
    for d_val, d_name in [(i * 2, f"D{i}") for i in range(1, 21)] + [(50, "D25")]:
        _add_path(d_val, d_name)

    # Phase 2: Single + Double finishes
    for d_val, d_name in [(i * 2, f"D{i}") for i in range(1, 21)] + [(50, "D25")]:
        for s in range(1, 21):
            score = s + d_val
            if score <= 60:
                _add_path(score, f"S{s} {d_name}")
        score_sb = 25 + d_val
        if score_sb <= 75:
            _add_path(score_sb, f"S25 {d_name}")

    # Phase 3: Triple + Double finishes (for 61-170)
    for t in range(1, 21):
        t_val = t * 3
        t_name = f"T{t}"
        for d in range(1, 21):
            d_val = d * 2
            d_name = f"D{d}"
            score = t_val + d_val
            if 2 <= score <= 170:
                _add_path(score, f"{t_name} {d_name}")
        score_tb = t_val + 50
        if score_tb <= 170:
            _add_path(score_tb, f"{t_name} D25")

    # Phase 4: Triple + Triple + Double finishes
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
                    path = f"{t2_name} {t1_name} D{d}" if t2 > t1 else f"{t1_name} {t2_name} D{d}"
                    _add_path(score, path)
            score_ttb = t1_val + t2_val + 50
            if 2 <= score_ttb <= 170:
                path = f"{t2_name} {t1_name} D25" if t2 > t1 else f"{t1_name} {t2_name} D25"
                _add_path(score_ttb, path)

    # Phase 5: Triple + Single + Double (fill remaining gaps)
    for t in range(1, 21):
        t_val = t * 3
        t_name = f"T{t}"
        for s in range(1, 21):
            for d in range(1, 21):
                d_val = d * 2
                score = t_val + s + d_val
                if 2 <= score <= 170:
                    _add_path(score, f"{t_name} S{s} D{d}")


def _add_path(score: int, path: str) -> None:
    """Add a checkout path if not already present and under limit."""
    if score not in CHECKOUTS:
        CHECKOUTS[score] = [path]
    elif len(CHECKOUTS[score]) < 3 and path not in CHECKOUTS[score]:
        CHECKOUTS[score].append(path)


_build_checkouts()

# Clean up: remove invalid T19 D21 entry if it slipped in
for score, paths in CHECKOUTS.items():
    CHECKOUTS[score] = [p for p in paths if "D21" not in p and "D22" not in p]


def get_checkout(remaining: int, darts_left: int = 3) -> list[str]:
    """Get checkout suggestions for a remaining score.

    Returns up to 3 suggestions, filtered by number of darts available.
    """
    if remaining < 2 or remaining > 170:
        return []
    suggestions = CHECKOUTS.get(remaining, [])
    # Filter by darts available (spaces separate darts, so count+1 = dart count)
    filtered = [s for s in suggestions if s.count(" ") < darts_left]
    return filtered[:3]
