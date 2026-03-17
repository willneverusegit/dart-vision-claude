"""Checkout suggestions for X01 games."""

# Common checkouts: score -> list of suggested throws (most common first)
# Format: each suggestion is a string like "T20 D16" or "T19 T12 D18"
CHECKOUTS: dict[int, list[str]] = {}

def _build_checkouts():
    """Build lookup table for checkouts 2-170."""
    # Phase 1: Direct double finishes (2-40 even numbers + Bull)
    for d_val, d_name in [(i * 2, f"D{i}") for i in range(1, 21)] + [(50, "D25")]:
        CHECKOUTS[d_val] = [d_name]

    # Phase 2: Single + Double finishes
    for d_val, d_name in [(i * 2, f"D{i}") for i in range(1, 21)] + [(50, "D25")]:
        for s in range(1, 21):
            score = s + d_val
            if score <= 60 and score not in CHECKOUTS:
                CHECKOUTS[score] = [f"S{s} {d_name}"]

        # Single Bull + Double
        score_sb = 25 + d_val
        if score_sb <= 75 and score_sb not in CHECKOUTS:
            CHECKOUTS[score_sb] = [f"S25 {d_name}"]

    # Phase 3: Triple + Double finishes (for 61-170)
    for t in range(1, 21):
        t_val = t * 3
        t_name = f"T{t}"
        for d in range(1, 21):
            d_val = d * 2
            d_name = f"D{d}"
            score = t_val + d_val
            if 2 <= score <= 170:
                path = f"{t_name} {d_name}"
                if score not in CHECKOUTS:
                    CHECKOUTS[score] = [path]
                elif len(CHECKOUTS[score]) < 3:
                    CHECKOUTS[score].append(path)
        # Triple + Bull
        score_tb = t_val + 50
        if score_tb <= 170:
            path = f"{t_name} D25"
            if score_tb not in CHECKOUTS:
                CHECKOUTS[score_tb] = [path]
            elif len(CHECKOUTS[score_tb]) < 3:
                CHECKOUTS[score_tb].append(path)

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
                    if score not in CHECKOUTS:
                        CHECKOUTS[score] = [path]
                    elif len(CHECKOUTS[score]) < 3 and path not in CHECKOUTS[score]:
                        CHECKOUTS[score].append(path)
            # Triple + Triple + Bull
            score_ttb = t1_val + t2_val + 50
            if 2 <= score_ttb <= 170:
                path = f"{t2_name} {t1_name} D25" if t2 > t1 else f"{t1_name} {t2_name} D25"
                if score_ttb not in CHECKOUTS:
                    CHECKOUTS[score_ttb] = [path]
                elif len(CHECKOUTS[score_ttb]) < 3 and path not in CHECKOUTS[score_ttb]:
                    CHECKOUTS[score_ttb].append(path)

    # Two-dart paths: Triple + Single + Double (for missing scores)
    for t in range(1, 21):
        t_val = t * 3
        t_name = f"T{t}"
        for s in range(1, 21):
            for d in range(1, 21):
                d_val = d * 2
                score = t_val + s + d_val
                if 2 <= score <= 170 and score not in CHECKOUTS:
                    CHECKOUTS[score] = [f"{t_name} S{s} D{d}"]
                elif 2 <= score <= 170 and len(CHECKOUTS.get(score, [])) < 3:
                    CHECKOUTS.setdefault(score, []).append(f"{t_name} S{s} D{d}")

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
