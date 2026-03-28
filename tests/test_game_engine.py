"""Unit tests for GameEngine: X01, Cricket, Free Play."""

import pytest
from src.game.engine import GameEngine


@pytest.fixture
def engine():
    return GameEngine()


def _throw(score: int, sector: int, multiplier: int, ring: str) -> dict:
    """Helper to create a throw result dict."""
    return {"score": score, "sector": sector, "multiplier": multiplier, "ring": ring}


class TestX01:
    def test_new_game_501(self, engine):
        engine.new_game(mode="x01", players=["Alice", "Bob"], starting_score=501)
        state = engine.get_state()
        assert state["mode"] == "x01"
        assert state["scores"]["Alice"] == 501
        assert state["scores"]["Bob"] == 501

    def test_score_subtraction(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=501)
        engine.register_throw(_throw(60, 20, 3, "triple"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 441

    def test_bust_below_zero(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=50)
        engine.register_throw(_throw(60, 20, 3, "triple"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 50  # Bust

    def test_bust_leaves_one(self, engine):
        """Score of 1 is impossible to finish (need double), so bust."""
        engine.new_game(mode="x01", players=["Alice"], starting_score=41)
        engine.register_throw(_throw(40, 20, 2, "double"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 41  # Bust: would leave 1

    def test_double_out_win(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=40)
        engine.register_throw(_throw(40, 20, 2, "double"))
        state = engine.get_state()
        assert state["winner"] == "Alice"
        assert state["phase"] == "game_over"

    def test_bull_finish(self, engine):
        """Inner bull (50) should count as valid finish."""
        engine.new_game(mode="x01", players=["Alice"], starting_score=50)
        engine.register_throw(_throw(50, 25, 2, "inner_bull"))
        state = engine.get_state()
        assert state["winner"] == "Alice"

    def test_non_double_finish_busts(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=20)
        engine.register_throw(_throw(20, 20, 1, "single"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 20  # Bust
        assert state["winner"] is None

    def test_undo(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=501)
        engine.register_throw(_throw(60, 20, 3, "triple"))
        assert engine.get_state()["scores"]["Alice"] == 441
        engine.undo_last_throw()
        assert engine.get_state()["scores"]["Alice"] == 501

    def test_three_darts_completes_turn(self, engine):
        engine.new_game(mode="x01", players=["Alice", "Bob"], starting_score=501)
        for _ in range(3):
            engine.register_throw(_throw(20, 20, 1, "single"))
        state = engine.get_state()
        assert state["darts_thrown"] == 0  # Turn archived, current_turn cleared

    def test_two_player_auto_advance(self, engine):
        """After 3 darts, player auto-advances to next player."""
        engine.new_game(mode="x01", players=["Alice", "Bob"], starting_score=501)
        assert engine.get_state()["current_player"] == "Alice"
        for _ in range(3):
            engine.register_throw(_throw(20, 20, 1, "single"))
        # Auto-advance: after 3 darts, now Bob's turn
        assert engine.get_state()["current_player"] == "Bob"

    def test_301_game(self, engine):
        engine.new_game(mode="x01", players=["A"], starting_score=301)
        assert engine.get_state()["scores"]["A"] == 301


class TestCricket:
    def test_mark_number(self, engine):
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw(_throw(60, 20, 3, "triple"))
        state = engine.get_state()
        # JSON serialization: keys become strings
        marks = state["players"][0]["cricket_marks"]
        assert marks.get(20, marks.get("20")) == 3  # Closed

    def test_non_cricket_number_ignored(self, engine):
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw(_throw(3, 3, 1, "single"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 0

    def test_score_on_open_number(self, engine):
        engine.new_game(mode="cricket", players=["Alice", "Bob"])
        # Alice triples 20 (closes it)
        engine.register_throw(_throw(60, 20, 3, "triple"))
        # Alice scores another 20 (Bob hasn't closed it)
        engine.register_throw(_throw(20, 20, 1, "single"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 20

    def test_initial_marks_zero(self, engine):
        engine.new_game(mode="cricket", players=["Alice"])
        state = engine.get_state()
        marks = state["players"][0]["cricket_marks"]
        assert all(v == 0 for v in marks.values())
        # Keys may be int or str depending on serialization
        expected_keys = {15, 16, 17, 18, 19, 20, 25}
        actual_keys = set()
        for k in marks.keys():
            actual_keys.add(int(k))
        assert actual_keys == expected_keys


    def test_sector_0_ignored(self, engine):
        """Sector 0 (miss) should not affect cricket marks."""
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw(_throw(0, 0, 1, "miss"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 0

    def test_sector_14_ignored(self, engine):
        """Sector 14 is not a cricket number and should be ignored."""
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw(_throw(14, 14, 1, "single"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 0

    def test_sector_21_ignored(self, engine):
        """Sector 21 does not exist but should be handled gracefully."""
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw(_throw(21, 21, 1, "single"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 0

    def test_inner_bull_maps_to_25(self, engine):
        """Inner bull (sector 50) should map to 25 for cricket."""
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw(_throw(50, 50, 2, "inner_bull"))
        state = engine.get_state()
        marks = state["players"][0]["cricket_marks"]
        bull_marks = marks.get(25, marks.get("25"))
        assert bull_marks == 2


    def test_non_cricket_throw_still_counts_as_dart(self, engine):
        """A throw at a non-cricket sector uses one of the 3 darts per turn."""
        engine.new_game(mode="cricket", players=["Alice", "Bob"])
        engine.register_throw(_throw(7, 7, 1, "single"))  # Non-cricket
        state = engine.get_state()
        assert state["darts_thrown"] == 1
        assert state["scores"]["Alice"] == 0

    def test_three_non_cricket_throws_complete_turn(self, engine):
        """Three non-cricket darts should complete the turn normally."""
        engine.new_game(mode="cricket", players=["Alice", "Bob"])
        for sector in [1, 3, 7]:
            engine.register_throw(_throw(sector, sector, 1, "single"))
        state = engine.get_state()
        assert state["darts_thrown"] == 0  # Turn archived
        assert state["scores"]["Alice"] == 0

    def test_outer_bull_single_mark(self, engine):
        """Outer bull (sector 25, multiplier 1) adds 1 mark on bull."""
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw(_throw(25, 25, 1, "outer_bull"))
        state = engine.get_state()
        marks = state["players"][0]["cricket_marks"]
        bull_marks = marks.get(25, marks.get("25"))
        assert bull_marks == 1

    def test_double_bull_two_marks(self, engine):
        """Double bull (sector 25, multiplier 2) adds 2 marks on bull."""
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw(_throw(50, 25, 2, "inner_bull"))
        state = engine.get_state()
        marks = state["players"][0]["cricket_marks"]
        bull_marks = marks.get(25, marks.get("25"))
        assert bull_marks == 2

    def test_cricket_win_all_closed_highest_score(self, engine):
        """Player wins when all numbers closed and score >= all opponents."""
        engine.new_game(mode="cricket", players=["Alice", "Bob"])
        # Alice's turn 1: close 15, 16, 17 (3 triples = 3 darts → auto-advance to Bob)
        for sector in [15, 16, 17]:
            engine.register_throw(_throw(sector * 3, sector, 3, "triple"))
        # Bob's turn 1: 3 irrelevant throws (auto-advance back to Alice)
        for _ in range(3):
            engine.register_throw(_throw(1, 1, 1, "single"))
        # Alice's turn 2: close 18, 19, 20
        for sector in [18, 19, 20]:
            engine.register_throw(_throw(sector * 3, sector, 3, "triple"))
        # Bob's turn 2
        for _ in range(3):
            engine.register_throw(_throw(1, 1, 1, "single"))
        # Alice's turn 3: close Bull (3 singles)
        engine.register_throw(_throw(25, 25, 1, "outer_bull"))
        engine.register_throw(_throw(25, 25, 1, "outer_bull"))
        engine.register_throw(_throw(25, 25, 1, "outer_bull"))
        state = engine.get_state()
        assert state["winner"] == "Alice"
        assert state["phase"] == "game_over"

    def test_cricket_all_sectors_boundary(self, engine):
        """Sectors 14 and below, and 21 and above are not cricket sectors."""
        engine.new_game(mode="cricket", players=["Alice"])
        for sector in [1, 2, 10, 14, 21, 22]:
            engine.register_throw(_throw(sector, sector, 1, "single"))
        state = engine.get_state()
        marks = state["players"][0]["cricket_marks"]
        assert all(
            marks.get(k, marks.get(str(k))) == 0
            for k in [15, 16, 17, 18, 19, 20, 25]
        )

    def test_cricket_sectors_constant(self):
        """Verify CRICKET_SECTORS class constant matches cricket_marks keys."""
        from src.game.engine import GameEngine
        assert GameEngine.CRICKET_SECTORS == frozenset({15, 16, 17, 18, 19, 20, 25})

    def test_excess_marks_score_points(self, engine):
        """After closing a number, excess marks score points if opponent hasn't closed."""
        engine.new_game(mode="cricket", players=["Alice", "Bob"])
        # Alice closes 20 with triple
        engine.register_throw(_throw(60, 20, 3, "triple"))
        # Alice hits another triple 20 — Bob hasn't closed it, so 60 points
        engine.register_throw(_throw(60, 20, 3, "triple"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 60


class TestFreePlay:
    def test_score_accumulates(self, engine):
        engine.new_game(mode="free", players=["Alice"])
        engine.register_throw(_throw(60, 20, 3, "triple"))
        engine.register_throw(_throw(25, 25, 1, "outer_bull"))
        state = engine.get_state()
        assert state["scores"]["Alice"] == 85

    def test_free_play_no_winner(self, engine):
        engine.new_game(mode="free", players=["Alice"])
        for _ in range(10):
            engine.register_throw(_throw(50, 25, 2, "inner_bull"))
        state = engine.get_state()
        assert state["winner"] is None


class TestUndoStack:
    def test_multiple_undos(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=501)
        engine.register_throw(_throw(60, 20, 3, "triple"))
        engine.register_throw(_throw(57, 19, 3, "triple"))
        assert engine.get_state()["scores"]["Alice"] == 384
        engine.undo_last_throw()
        assert engine.get_state()["scores"]["Alice"] == 441
        engine.undo_last_throw()
        assert engine.get_state()["scores"]["Alice"] == 501

    def test_undo_when_empty(self, engine):
        """Undo with empty stack should not crash."""
        engine.new_game(mode="x01", players=["Alice"], starting_score=501)
        engine.undo_last_throw()  # No throw to undo
        assert engine.get_state()["scores"]["Alice"] == 501

    def test_no_action_when_idle(self, engine):
        """Register throw when no game active should be a no-op."""
        state = engine.register_throw(_throw(60, 20, 3, "triple"))
        assert state["phase"] == "idle"
