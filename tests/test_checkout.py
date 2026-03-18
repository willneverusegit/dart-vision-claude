"""Tests for checkout suggestion module."""

import pytest
from src.game.checkout import get_checkout
from src.game.models import GameState, GameMode, GamePhase, PlayerState


class TestGetCheckout:
    def test_170_starts_with_t20(self):
        results = get_checkout(170)
        assert len(results) > 0
        assert results[0].startswith("T20")

    def test_40_first_is_d20(self):
        results = get_checkout(40)
        assert results[0] == "D20"

    def test_50_first_is_d25(self):
        results = get_checkout(50)
        assert results[0] == "D25"

    def test_32_first_is_d16(self):
        results = get_checkout(32)
        assert results[0] == "D16"

    def test_1_returns_empty(self):
        assert get_checkout(1) == []

    def test_171_returns_empty(self):
        assert get_checkout(171) == []

    def test_0_returns_empty(self):
        assert get_checkout(0) == []

    def test_darts_left_1_double(self):
        result = get_checkout(40, 1)
        assert "D20" in result

    def test_darts_left_1_high_score(self):
        # 100 needs at least 2 darts, so 1 dart = empty
        assert get_checkout(100, 1) == []


class TestStandardCheckouts:
    """Standard professional checkouts should appear first."""

    def test_170_standard(self):
        results = get_checkout(170)
        assert results[0] == "T20 T20 D25"

    def test_100_standard(self):
        results = get_checkout(100)
        assert results[0] == "T20 D20"

    def test_80_standard(self):
        results = get_checkout(80)
        assert results[0] == "T20 D10"

    def test_92_standard(self):
        results = get_checkout(92)
        assert results[0] == "T20 D16"

    def test_99_is_3_dart(self):
        """99 requires 3 darts (no D21 exists)."""
        results = get_checkout(99)
        assert results[0] == "T19 S10 D16"
        # Should not be available with 1 dart
        assert get_checkout(99, 1) == []

    def test_double_still_works(self):
        """Direct doubles should still be available (added after standard)."""
        results = get_checkout(40)
        assert "D20" in results

    def test_standard_alternatives_present(self):
        """High scores should have alternative paths."""
        results = get_checkout(154)
        assert len(results) >= 2
        assert results[0] == "T20 T18 D20"

    def test_all_standard_scores_valid(self):
        """Every standard checkout path must sum to its score."""
        from src.game.checkout import _STANDARD_CHECKOUTS
        for score, path in _STANDARD_CHECKOUTS.items():
            total = 0
            for part in path.split():
                if part.startswith("T"):
                    total += int(part[1:]) * 3
                elif part.startswith("D"):
                    total += int(part[1:]) * 2
                elif part.startswith("S"):
                    total += int(part[1:])
                else:
                    total += int(part)
            assert total == score, f"Standard checkout {score}: '{path}' sums to {total}"


class TestCheckoutInGameState:
    def test_checkout_in_x01_api_dict(self):
        gs = GameState(
            mode=GameMode.X01,
            phase=GamePhase.PLAYING,
            players=[PlayerState(name="Alice", score=40)],
            current_player_index=0,
        )
        api = gs.to_api_dict()
        assert "checkout" in api
        assert "D20" in api["checkout"]

    def test_checkout_empty_when_not_x01(self):
        gs = GameState(
            mode=GameMode.CRICKET,
            phase=GamePhase.PLAYING,
            players=[PlayerState(name="Alice", score=40)],
            current_player_index=0,
        )
        api = gs.to_api_dict()
        assert api["checkout"] == []
