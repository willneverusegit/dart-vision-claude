"""Extra engine tests for coverage gaps."""

from src.game.engine import GameEngine


class TestEngineCoverage:
    def test_register_throw_not_playing(self):
        """register_throw should return state without changes when not playing."""
        engine = GameEngine()
        result = engine.register_throw({
            "score": 20, "sector": 20, "multiplier": 1, "ring": "single"
        })
        assert result["phase"] == "idle"

    def test_next_player_not_playing(self):
        """next_player should do nothing when game is not in playing phase."""
        engine = GameEngine()
        engine.next_player()
        # No error raised

    def test_undo_empty_stack(self):
        """undo should do nothing when stack is empty."""
        engine = GameEngine()
        engine.undo_last_throw()
        # No error raised

    def test_cricket_scoring_excess_marks(self):
        """Cricket: marks beyond 3 should score points if opponents not closed."""
        engine = GameEngine()
        engine.new_game(mode="cricket", players=["Alice", "Bob"])
        # Triple 20 (3 marks)
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        # Another triple 20 should score points (3 x 20 = 60)
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        state = engine.get_state()
        alice = state["players"][0]
        assert alice["score"] == 60  # Excess marks score

    def test_cricket_closed_number_scoring(self):
        """Cricket: already closed number scores if opponents not closed."""
        engine = GameEngine()
        engine.new_game(mode="cricket", players=["Alice", "Bob"])
        # Alice turn 1: Close 20, 19, 18 (auto-advance to Bob after 3 darts)
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        engine.register_throw({"score": 57, "sector": 19, "multiplier": 3, "ring": "triple"})
        engine.register_throw({"score": 54, "sector": 18, "multiplier": 3, "ring": "triple"})
        # Bob turn 1: 3 irrelevant throws (auto-advance back to Alice)
        for _ in range(3):
            engine.register_throw({"score": 1, "sector": 1, "multiplier": 1, "ring": "single"})
        # Alice turn 2: score on closed 20 (Bob hasn't closed it)
        engine.register_throw({"score": 20, "sector": 20, "multiplier": 1, "ring": "single"})
        state = engine.get_state()
        alice = state["players"][0]
        assert alice["score"] == 20  # Scored on closed number

    def test_cricket_bull_maps_to_25(self):
        """Cricket: sector 50 (inner bull) should map to 25."""
        engine = GameEngine()
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw({"score": 50, "sector": 50, "multiplier": 1, "ring": "inner_bull"})
        state = engine.get_state()
        alice = state["players"][0]
        marks = alice.get("cricket_marks", {})
        # Check 25 key (could be string or int depending on serialization)
        mark_25 = marks.get(25, marks.get("25", 0))
        assert mark_25 >= 1

    def test_cricket_win_condition(self):
        """Cricket: player wins when all numbers closed and highest score."""
        engine = GameEngine()
        engine.new_game(mode="cricket", players=["Alice"])
        # Close all cricket numbers
        for sector in [20, 19, 18, 17, 16, 15]:
            engine.register_throw({"score": sector * 3, "sector": sector, "multiplier": 3, "ring": "triple"})
        # Close bull
        engine.register_throw({"score": 50, "sector": 50, "multiplier": 1, "ring": "inner_bull"})
        engine.register_throw({"score": 50, "sector": 50, "multiplier": 1, "ring": "inner_bull"})
        engine.register_throw({"score": 50, "sector": 50, "multiplier": 1, "ring": "inner_bull"})
        state = engine.get_state()
        assert state["phase"] == "game_over"

    def test_free_play_accumulates(self):
        """Free play should accumulate scores."""
        engine = GameEngine()
        engine.new_game(mode="free", players=["Test"])
        engine.register_throw({"score": 20, "sector": 20, "multiplier": 1, "ring": "single"})
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        state = engine.get_state()
        assert state["players"][0]["score"] == 80

    def test_undo_max_stack(self):
        """Undo stack should limit to max_undo entries."""
        engine = GameEngine()
        engine.new_game(mode="free", players=["Test"])
        for i in range(25):
            engine.register_throw({"score": 1, "sector": 1, "multiplier": 1, "ring": "single"})
        assert len(engine._undo_stack) <= engine._max_undo

    def test_next_player_with_current_turn(self):
        """next_player should complete current turn before switching."""
        engine = GameEngine()
        engine.new_game(mode="x01", players=["A", "B"])
        engine.register_throw({"score": 20, "sector": 20, "multiplier": 1, "ring": "single"})
        engine.next_player()
        state = engine.get_state()
        assert state["current_player_index"] == 1

    def test_round_increments_when_wrapping(self):
        """Round number should increment when wrapping back to first player."""
        engine = GameEngine()
        engine.new_game(mode="x01", players=["A", "B"])
        assert engine.state.round_number == 1
        engine.next_player()  # -> B
        engine.next_player()  # -> A, round 2
        assert engine.state.round_number == 2
