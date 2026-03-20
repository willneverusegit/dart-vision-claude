"""Game mode helpers."""


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

# Valid ring names and sector numbers for input validation
VALID_RINGS: set[str] = {"single", "double", "triple", "inner_bull", "outer_bull", "miss"}
VALID_SECTORS: set[int] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 25, 50}


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
