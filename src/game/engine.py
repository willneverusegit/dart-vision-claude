"""GameEngine: manages game state, scoring logic, and undo stack."""

import logging
from src.game.models import GameState, GameMode, GamePhase, PlayerState, ThrowResult, CricketVariant

logger = logging.getLogger(__name__)


class GameEngine:
    """Manages game state and scoring logic."""

    def __init__(self) -> None:
        self.state = GameState()
        self._undo_stack: list[GameState] = []
        self._redo_stack: list[GameState] = []
        self._max_undo = 20

    def new_game(self, mode: str = "x01", players: list[str] | None = None,
                 starting_score: int = 501, double_in: bool = False,
                 starting_scores: dict[str, int] | None = None,
                 cricket_variant: str = "standard",
                 target_score: int | None = None) -> None:
        """Start a new game.

        Args:
            starting_scores: Per-player handicap, e.g. {"Alice": 301, "Bob": 501}.
                           Overrides starting_score for named players.
            cricket_variant: "standard" or "cut_throat".
        """
        if not isinstance(starting_score, int) or starting_score <= 0 or starting_score > 10000:
            raise ValueError(f"starting_score must be int 1-10000, got {starting_score!r}")
        if players is None:
            players = ["Player 1"]
        if not isinstance(players, list) or len(players) == 0:
            raise ValueError(f"players must be a non-empty list, got {players!r}")

        game_mode = GameMode(mode)
        cv = CricketVariant(cricket_variant) if cricket_variant in ("standard", "cut_throat") else CricketVariant.STANDARD
        player_states = []

        for name in players:
            # Handicap: per-player starting score overrides global
            player_start = starting_score
            if starting_scores and name in starting_scores:
                ps = starting_scores[name]
                if isinstance(ps, int) and 2 <= ps <= 10000:
                    player_start = ps

            initial_score = player_start if game_mode == GameMode.X01 else 0
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
            double_in=double_in,
            cricket_variant=cv,
            target_score=target_score if isinstance(target_score, int) and target_score > 0 else None,
        )
        self._undo_stack.clear()
        self._redo_stack.clear()
        logger.info("New game: mode=%s, players=%s, start=%d", mode, players, starting_score)

    def register_throw(self, score_result: dict) -> dict:
        """Register a detected dart throw. Returns updated game state dict."""
        if self.state.phase != GamePhase.PLAYING:
            return self.get_state()

        # Validate required keys
        required_keys = {"score", "sector", "multiplier", "ring"}
        missing = required_keys - set(score_result.keys())
        if missing:
            logger.warning("register_throw: missing keys %s in score_result", missing)
            return self.get_state()

        self._push_undo()

        player = self.state.current_player
        if player is None:
            return self.get_state()

        # Auto-complete turn if already at 3 darts
        if len(player.current_turn) >= 3:
            self._complete_turn()

        throw = ThrowResult(
            score=score_result["score"],
            sector=score_result["sector"],
            multiplier=score_result["multiplier"],
            ring=score_result["ring"],
        )

        # Mode-specific scoring
        if self.state.mode == GameMode.X01:
            self._score_x01(player, throw)
        elif self.state.mode == GameMode.CRICKET:
            self._score_cricket(player, throw)
        else:  # FREE
            self._score_free(player, throw)

        player.current_turn.append(throw)

        # Auto-advance after 3 darts (unless game just ended)
        if len(player.current_turn) >= 3 and self.state.phase == GamePhase.PLAYING:
            self._complete_turn()
            self.state.current_player_index = (
                (self.state.current_player_index + 1) % len(self.state.players)
            )
            if self.state.current_player_index == 0:
                self.state.round_number += 1

        return self.get_state()

    # --- X01 Scoring ---

    def _score_x01(self, player: PlayerState, throw: ThrowResult) -> None:
        """X01 scoring: subtract from remaining. Bust if below 0 or no double finish."""
        # Double-In: if player hasn't scored yet, first scoring throw must be a double
        if self.state.double_in and player.score == self.state.starting_score:
            # Check if player already doubled-in earlier this turn
            doubled_in = any(
                t.multiplier == 2 or t.ring == "inner_bull"
                for t in player.current_turn
            )
            if not doubled_in:
                if throw.multiplier != 2 and throw.ring != "inner_bull":
                    # Non-double throw before doubling in — doesn't count
                    return

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

    # Valid cricket sectors (15-20 and Bull)
    CRICKET_SECTORS = frozenset({15, 16, 17, 18, 19, 20, 25})

    def _score_cricket(self, player: PlayerState, throw: ThrowResult) -> None:
        """Cricket scoring: mark numbers 15-20 and bull. 3 marks to close."""
        target = throw.sector
        if target == 50:
            target = 25  # Inner bull counts as bull
        if target not in player.cricket_marks:
            logger.debug("Cricket: sector %d is not a cricket number, no marks added", throw.sector)
            return  # Not a cricket number — dart still counts toward the turn

        marks_to_add = throw.multiplier
        current_marks = player.cricket_marks[target]

        cut_throat = self.state.cricket_variant == CricketVariant.CUT_THROAT

        if current_marks >= 3:
            # Already closed: score points if opponents have not closed it
            all_closed = all(
                p.cricket_marks.get(target, 0) >= 3
                for p in self.state.players if p != player
            )
            if not all_closed:
                points = target * marks_to_add
                if cut_throat:
                    self._cricket_give_points_to_open(player, target, points)
                else:
                    player.score += points
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
                    points = target * excess
                    if cut_throat:
                        self._cricket_give_points_to_open(player, target, points)
                    else:
                        player.score += points

        if self._check_cricket_win(player):
            self.state.winner = player.name
            self.state.phase = GamePhase.GAME_OVER

    def _cricket_give_points_to_open(self, thrower: PlayerState, target: int, points: int) -> None:
        """Cut Throat: give points to all opponents who haven't closed the target."""
        for p in self.state.players:
            if p != thrower and p.cricket_marks.get(target, 0) < 3:
                p.score += points

    def _check_cricket_win(self, player: PlayerState) -> bool:
        """Check if player has won cricket (all closed + best score).

        Standard: highest score wins. Cut Throat: lowest score wins.
        """
        all_closed = all(v >= 3 for v in player.cricket_marks.values())
        if not all_closed:
            return False
        if self.state.cricket_variant == CricketVariant.CUT_THROAT:
            return all(player.score <= p.score for p in self.state.players)
        return all(player.score >= p.score for p in self.state.players)

    # --- Free Play Scoring ---

    def _score_free(self, player: PlayerState, throw: ThrowResult) -> None:
        """Free play: accumulate score. Check target if set."""
        player.score += throw.score
        if self.state.target_score and player.score >= self.state.target_score:
            self.state.winner = player.name
            self.state.phase = GamePhase.GAME_OVER
            logger.info("Free Play winner: %s (reached %d)", player.name, self.state.target_score)

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
            self._redo_stack.append(self.state.model_copy(deep=True))
            self.state = self._undo_stack.pop()
            logger.info("Undo performed")

    def redo(self) -> None:
        """Redo the last undone action."""
        if self._redo_stack:
            self._undo_stack.append(self.state.model_copy(deep=True))
            self.state = self._redo_stack.pop()
            logger.info("Redo performed")

    def toggle_pause(self) -> None:
        """Toggle between PLAYING and PAUSED."""
        if self.state.phase == GamePhase.PLAYING:
            self.state.phase = GamePhase.PAUSED
            logger.info("Game paused")
        elif self.state.phase == GamePhase.PAUSED:
            self.state.phase = GamePhase.PLAYING
            logger.info("Game resumed")

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
        self._redo_stack.clear()  # New action invalidates redo history
