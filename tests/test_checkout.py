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
