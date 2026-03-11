"""Tests for game mode helpers."""

from src.game.modes import (
    get_checkout_suggestion,
    is_valid_x01_finish,
    format_score_display,
    CRICKET_NUMBERS,
)


class TestCheckoutSuggestion:
    def test_known_checkout_170(self):
        assert get_checkout_suggestion(170) == "T20 T20 Bull"

    def test_known_checkout_40(self):
        assert get_checkout_suggestion(40) == "D20"

    def test_known_checkout_50(self):
        assert get_checkout_suggestion(50) == "Bull"

    def test_unknown_checkout(self):
        assert get_checkout_suggestion(999) is None

    def test_checkout_2(self):
        assert get_checkout_suggestion(2) == "D1"


class TestIsValidFinish:
    def test_zero_not_valid(self):
        assert is_valid_x01_finish(0) is False

    def test_negative_not_valid(self):
        assert is_valid_x01_finish(-5) is False

    def test_one_not_valid(self):
        assert is_valid_x01_finish(1) is False

    def test_above_170_not_valid(self):
        assert is_valid_x01_finish(171) is False

    def test_impossible_scores(self):
        for s in [159, 162, 163, 165, 166, 168, 169]:
            assert is_valid_x01_finish(s) is False, f"{s} should be impossible"

    def test_valid_finishes(self):
        for s in [2, 40, 100, 140, 170]:
            assert is_valid_x01_finish(s) is True, f"{s} should be valid"


class TestFormatScoreDisplay:
    def test_inner_bull(self):
        assert format_score_display(50, 1, "inner_bull") == "Bull"

    def test_outer_bull(self):
        assert format_score_display(25, 1, "outer_bull") == "25"

    def test_miss(self):
        assert format_score_display(0, 0, "miss") == "Miss"

    def test_single(self):
        assert format_score_display(20, 1, "single") == "20"

    def test_double(self):
        assert format_score_display(40, 2, "double") == "D20"

    def test_triple(self):
        assert format_score_display(60, 3, "triple") == "T20"


class TestCricketNumbers:
    def test_cricket_numbers_list(self):
        assert CRICKET_NUMBERS == [20, 19, 18, 17, 16, 15, 25]
