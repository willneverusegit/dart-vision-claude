"""Tests for extended checkout table and Double-In support."""

import pytest
from src.game.checkout import get_checkout, CHECKOUTS
from src.game.engine import GameEngine


def _throw(score, sector, multiplier, ring):
    return {"score": score, "sector": sector, "multiplier": multiplier, "ring": ring}


class TestPreferredCheckouts:
    """Verify that preferred standard checkouts are used as first suggestion."""

    def test_170_is_t20_t20_d25(self):
        results = get_checkout(170)
        assert results[0] == "T20 T20 D25"

    def test_160_is_t20_t20_d20(self):
        results = get_checkout(160)
        assert results[0] == "T20 T20 D20"

    def test_100_is_t20_d20(self):
        results = get_checkout(100)
        assert results[0] == "T20 D20"

    def test_40_is_d20(self):
        results = get_checkout(40)
        assert results[0] == "D20"

    def test_32_is_d16(self):
        results = get_checkout(32)
        assert results[0] == "D16"

    def test_50_is_d25(self):
        results = get_checkout(50)
        assert results[0] == "D25"

    def test_all_achievable_scores_have_checkouts(self):
        # Scores 159, 162, 163, 165, 166, 168, 169 are impossible checkouts
        impossible = {159, 162, 163, 165, 166, 168, 169}
        for score in range(2, 171):
            if score in impossible:
                assert score not in CHECKOUTS or CHECKOUTS[score] == [], \
                    f"Score {score} should be impossible but has checkout"
            else:
                assert score in CHECKOUTS, f"Missing checkout for {score}"
                assert len(CHECKOUTS[score]) > 0, f"Empty checkout for {score}"

    def test_no_invalid_doubles(self):
        """No path should reference D21 or higher (max double is D20, plus D25)."""
        for score, paths in CHECKOUTS.items():
            for path in paths:
                for part in path.split():
                    if part.startswith("D") and part != "D25":
                        num = int(part[1:])
                        assert 1 <= num <= 20, f"Invalid double {part} in checkout for {score}"


class TestCheckoutDartsFiltering:
    """Test that darts_left filtering works correctly."""

    def test_3dart_checkout_hidden_with_1_dart(self):
        # 170 needs 3 darts, should not appear with 1 dart left
        assert get_checkout(170, 1) == []

    def test_3dart_checkout_hidden_with_2_darts(self):
        # 170 needs 3 darts, should not appear with 2 darts
        assert get_checkout(170, 2) == []

    def test_2dart_checkout_available_with_2_darts(self):
        result = get_checkout(100, 2)
        assert len(result) > 0
        assert result[0] == "T20 D20"

    def test_1dart_double_available(self):
        result = get_checkout(40, 1)
        assert "D20" in result

    def test_remaining_checkout_after_first_dart(self):
        """After throwing T20 (60 points), remaining 41 should show S1 D20."""
        # Simulates: starting at 101, threw T20, remaining = 41, 2 darts left
        result = get_checkout(41, 2)
        assert len(result) > 0
        assert result[0] == "S1 D20"


class TestDoubleIn:
    """Test Double-In variant for X01."""

    @pytest.fixture
    def engine(self):
        return GameEngine()

    def test_double_in_rejects_single(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=301, double_in=True)
        engine.register_throw(_throw(20, 20, 1, "single"))
        state = engine.get_state()
        # Single throw should not count
        assert state["scores"]["Alice"] == 301

    def test_double_in_accepts_double(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=301, double_in=True)
        engine.register_throw(_throw(40, 20, 2, "double"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 261

    def test_double_in_accepts_bull(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=301, double_in=True)
        engine.register_throw(_throw(50, 25, 2, "inner_bull"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 251

    def test_double_in_subsequent_throws_count(self, engine):
        """After doubling in, subsequent throws count normally."""
        engine.new_game(mode="x01", players=["Alice"], starting_score=301, double_in=True)
        engine.register_throw(_throw(40, 20, 2, "double"))  # doubles in
        engine.register_throw(_throw(20, 20, 1, "single"))  # this should count
        state = engine.get_state()
        assert state["scores"]["Alice"] == 241

    def test_double_in_triple_rejected(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=501, double_in=True)
        engine.register_throw(_throw(60, 20, 3, "triple"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 501  # Triple doesn't count

    def test_normal_game_no_double_in(self, engine):
        """Without double_in, singles count immediately."""
        engine.new_game(mode="x01", players=["Alice"], starting_score=301, double_in=False)
        engine.register_throw(_throw(20, 20, 1, "single"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 281

    def test_double_in_flag_in_api(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=301, double_in=True)
        state = engine.get_state()
        assert state["double_in"] is True

    def test_double_in_multiple_misses_then_double(self, engine):
        """Multiple non-double throws ignored, then double starts scoring."""
        engine.new_game(mode="x01", players=["Alice"], starting_score=301, double_in=True)
        engine.register_throw(_throw(20, 20, 1, "single"))  # ignored
        engine.register_throw(_throw(19, 19, 1, "single"))  # ignored
        engine.register_throw(_throw(40, 20, 2, "double"))  # doubles in!
        state = engine.get_state()
        assert state["scores"]["Alice"] == 261
