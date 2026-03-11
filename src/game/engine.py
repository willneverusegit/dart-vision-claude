"""GameEngine: manages game state, scoring logic, and undo stack."""

import logging
from src.game.models import GameState, GameMode, GamePhase, PlayerState, ThrowResult

logger = logging.getLogger(__name__)


class GameEngine:
    """Manages game state and scoring logic."""

    def __init__(self) -> None:
        self.state = GameState()
        self._undo_stack: list[GameState] = []
        self._max_undo = 20

    def new_game(self, mode: str = "x01", players: list[str] | None = None,
                 starting_score: int = 501) -> None:
        """Start a new game."""
        if players is None:
            players = ["Player 1"]

        game_mode = GameMode(mode)
        player_states = []

        for name in players:
            initial_score = starting_score if game_mode == GameMode.X01 else 0
            cricket_marks: dict[int, int] = {}
            if game_mode == GameMode.CRICKET:
                cricket_marks = {n: 0 for n in [20, 19, 18, 17, 16, 15, 25]}

            player_states.append(PlayerState(
                name=name,
                score=initial_score,
                cricket_marks=cricket_marks,
            ))

        self.state = GameState(
            mode=game_mode,
            phase=GamePhase.PLAYING,
            players=player_states,
            current_player_index=0,
            round_number=1,
            starting_score=starting_score,
        )
        self._undo_stack.clear()
        logger.info("New game: mode=%s, players=%s, start=%d", mode, players, starting_score)

    def register_throw(self, score_result: dict) -> dict:
        """Register a detected dart throw. Returns updated game state dict."""
        if self.state.phase != GamePhase.PLAYING:
            return self.get_state()

        self._push_undo()

        throw = ThrowResult(
            score=score_result["score"],
            sector=score_result["sector"],
            multiplier=score_result["multiplier"],
            ring=score_result["ring"],
        )

        player = self.state.current_player
        if player is None:
            return self.get_state()

        # Mode-specific scoring
        if self.state.mode == GameMode.X01:
            self._score_x01(player, throw)
        elif self.state.mode == GameMode.CRICKET:
            self._score_cricket(player, throw)
        else:  # FREE
            self._score_free(player, throw)

        player.current_turn.append(throw)

        # Check if turn is complete (3 darts)
        if len(player.current_turn) >= 3:
            self._complete_turn()

        return self.get_state()

    # --- X01 Scoring ---

    def _score_x01(self, player: PlayerState, throw: ThrowResult) -> None:
        """X01 scoring: subtract from remaining. Bust if below 0 or no double finish."""
        new_score = player.score - throw.score

        if new_score < 0:
            self._bust_turn(player)
            return

        if new_score == 0:
            if throw.multiplier == 2 or throw.ring == "inner_bull":
                player.score = 0
                self.state.winner = player.name
                self.state.phase = GamePhase.GAME_OVER
                logger.info("Winner: %s", player.name)
            else:
                self._bust_turn(player)
            return

        if new_score == 1:
            self._bust_turn(player)
            return

        player.score = new_score

    def _bust_turn(self, player: PlayerState) -> None:
        """Reset player score to start of turn (bust)."""
        turn_points = sum(t.score for t in player.current_turn)
        player.score += turn_points  # Restore points from this turn
        player.current_turn.clear()
        self._complete_turn()

    # --- Cricket Scoring ---

    def _score_cricket(self, player: PlayerState, throw: ThrowResult) -> None:
        """Cricket scoring: mark numbers 15-20 and bull. 3 marks to close."""
        target = throw.sector
        if target == 50:
            target = 25  # Inner bull counts as bull
        if target not in player.cricket_marks:
            return  # Not a cricket number

        marks_to_add = throw.multiplier
        current_marks = player.cricket_marks[target]

        if current_marks >= 3:
            # Already closed: score points if opponents have not closed it
            all_closed = all(
                p.cricket_marks.get(target, 0) >= 3
                for p in self.state.players if p != player
            )
            if not all_closed:
                player.score += target * marks_to_add
        else:
            new_marks = current_marks + marks_to_add
            player.cricket_marks[target] = min(new_marks, 3)
            if new_marks > 3:
                all_closed = all(
                    p.cricket_marks.get(target, 0) >= 3
                    for p in self.state.players if p != player
                )
                if not all_closed:
                    excess = new_marks - 3
                    player.score += target * excess

        if self._check_cricket_win(player):
            self.state.winner = player.name
            self.state.phase = GamePhase.GAME_OVER

    def _check_cricket_win(self, player: PlayerState) -> bool:
        """Check if player has won cricket (all closed + highest score)."""
        all_closed = all(v >= 3 for v in player.cricket_marks.values())
        if not all_closed:
            return False
        return all(player.score >= p.score for p in self.state.players)

    # --- Free Play Scoring ---

    def _score_free(self, player: PlayerState, throw: ThrowResult) -> None:
        """Free play: just accumulate score."""
        player.score += throw.score

    # --- Turn Management ---

    def _complete_turn(self) -> None:
        """End current turn and archive throws."""
        player = self.state.current_player
        if player:
            player.throws_history.append(list(player.current_turn))
            player.current_turn.clear()

    def next_player(self) -> None:
        """Advance to the next player."""
        if self.state.phase != GamePhase.PLAYING:
            return

        self._push_undo()

        player = self.state.current_player
        if player and player.current_turn:
            self._complete_turn()

        self.state.current_player_index = (
            (self.state.current_player_index + 1) % len(self.state.players)
        )
        if self.state.current_player_index == 0:
            self.state.round_number += 1

    # --- Undo ---

    def undo_last_throw(self) -> None:
        """Undo the last registered throw."""
        if self._undo_stack:
            self.state = self._undo_stack.pop()
            logger.info("Undo performed")

    def end_game(self) -> None:
        """End the current game and reset to idle state."""
        self.state = GameState()
        self._undo_stack.clear()
        logger.info("Game ended manually")

    # --- State Access ---

    def get_state(self) -> dict:
        """Get serializable game state."""
        return self.state.to_api_dict()

    def _push_undo(self) -> None:
        """Save current state to undo stack."""
        if len(self._undo_stack) >= self._max_undo:
            self._undo_stack.pop(0)
        self._undo_stack.append(self.state.model_copy(deep=True))
