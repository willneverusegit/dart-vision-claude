"""Game mode helpers and checkout tables."""


# X01 checkout suggestions (common finishes)
X01_CHECKOUTS: dict[int, str] = {
    170: "T20 T20 Bull",
    167: "T20 T19 Bull",
    164: "T20 T18 Bull",
    161: "T20 T17 Bull",
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
    # Common lower finishes
    100: "T20 D20",
    99: "T19 D21",
    80: "T20 D10",
    60: "20 D20",
    50: "Bull",
    40: "D20",
    36: "D18",
    32: "D16",
    20: "D10",
    16: "D8",
    10: "D5",
    8: "D4",
    6: "D3",
    4: "D2",
    2: "D1",
}


def get_checkout_suggestion(remaining: int) -> str | None:
    """Get a checkout suggestion for X01 remaining score."""
    return X01_CHECKOUTS.get(remaining)


def is_valid_x01_finish(remaining: int) -> bool:
    """Check if remaining score can be finished in 3 darts or fewer."""
    if remaining <= 0:
        return False
    if remaining > 170:
        return False
    if remaining == 1:
        return False  # Cannot finish on 1 (need a double)
    # 159, 162, 163, 165, 166, 168, 169 are impossible
    impossible = {159, 162, 163, 165, 166, 168, 169}
    return remaining not in impossible


CRICKET_NUMBERS: list[int] = [20, 19, 18, 17, 16, 15, 25]


def format_score_display(score: int, multiplier: int, ring: str) -> str:
    """Format score for display (e.g., 'T20', 'D16', 'Bull')."""
    if ring == "inner_bull":
        return "Bull"
    if ring == "outer_bull":
        return "25"
    if ring == "miss":
        return "Miss"
    prefix = ""
    if multiplier == 2:
        prefix = "D"
    elif multiplier == 3:
        prefix = "T"
    sector = score // multiplier if multiplier > 0 else 0
    return f"{prefix}{sector}"
