# Spiellogik: Engine, Modi, Zustandsmaschine

> Lies dieses Dokument, wenn du an `src/game/` arbeitest.

---

## Übersicht

Die Spiellogik ist von der CV-Pipeline entkoppelt. Sie empfängt Score-Events und verwaltet den Spielzustand.

### Zustandsmaschine

```
IDLE → SETUP → PLAYING → TURN_IN_PROGRESS → TURN_COMPLETE → PLAYING → ... → GAME_OVER
          │                    │
          │              [dart detected]
          │                    │
          │              darts_thrown < 3?
          │              YES → TURN_IN_PROGRESS
          │              NO  → TURN_COMPLETE
          │                    │
          │              [remove_darts / next_player]
          │                    │
          │              → PLAYING (next player)
          │
          └── [new_game] → SETUP
```

---

## Pydantic Models (`src/game/models.py`)

```python
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class GameMode(str, Enum):
    X01 = "x01"
    CRICKET = "cricket"
    FREE = "free"


class GamePhase(str, Enum):
    IDLE = "idle"
    PLAYING = "playing"
    GAME_OVER = "game_over"


class ThrowResult(BaseModel):
    """A single dart throw result."""
    score: int                      # Total points (e.g., 60 for T20)
    sector: int                     # Base sector (e.g., 20)
    multiplier: int                 # 1, 2, or 3
    ring: str                       # "single", "double", "triple", "inner_bull", etc.
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PlayerState(BaseModel):
    """State of a single player."""
    name: str
    score: int                      # Remaining score (X01) or total (Free)
    throws_history: list[list[ThrowResult]] = []  # List of turns, each a list of throws
    current_turn: list[ThrowResult] = []
    # Cricket-specific
    cricket_marks: dict[int, int] = {}  # {20: 3, 19: 2, ...}


class GameState(BaseModel):
    """Complete game state, serializable to JSON."""
    mode: GameMode = GameMode.X01
    phase: GamePhase = GamePhase.IDLE
    players: list[PlayerState] = []
    current_player_index: int = 0
    round_number: int = 1
    starting_score: int = 501
    winner: str | None = None

    # Derived properties
    @property
    def current_player(self) -> PlayerState | None:
        if self.players:
            return self.players[self.current_player_index]
        return None

    @property
    def darts_thrown(self) -> int:
        if self.current_player:
            return len(self.current_player.current_turn)
        return 0

    @property
    def darts_remaining(self) -> int:
        return 3 - self.darts_thrown

    @property
    def turn_total(self) -> int:
        if self.current_player:
            return sum(t.score for t in self.current_player.current_turn)
        return 0

    def to_api_dict(self) -> dict:
        """Serialize for API/WebSocket."""
        cp = self.current_player
        return {
            "mode": self.mode.value,
            "phase": self.phase.value,
            "current_player": cp.name if cp else None,
            "current_player_index": self.current_player_index,
            "players": [
                {
                    "name": p.name,
                    "score": p.score,
                    "current_turn": [t.score for t in p.current_turn],
                    "cricket_marks": p.cricket_marks,
                }
                for p in self.players
            ],
            "scores": {p.name: p.score for p in self.players},
            "current_turn": [t.score for t in cp.current_turn] if cp else [],
            "turn_total": self.turn_total,
            "darts_thrown": self.darts_thrown,
            "darts_remaining": self.darts_remaining,
            "round": self.round_number,
            "winner": self.winner,
        }
```

---

## GameEngine (`src/game/engine.py`)

```python
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
        if players is None:
            players = ["Player 1"]

        game_mode = GameMode(mode)
        player_states = []

        for name in players:
            initial_score = starting_score if game_mode == GameMode.X01 else 0
            cricket_marks = {}
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

        # Save state for undo
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

    def _score_x01(self, player: PlayerState, throw: ThrowResult) -> None:
        """X01 scoring: subtract from remaining. Bust if below 0 or finish without double."""
        new_score = player.score - throw.score

        if new_score < 0:
            # Bust: reset to score before this turn
            self._bust_turn(player)
            return

        if new_score == 0:
            # Check for double-out (optional rule, default: enabled)
            if throw.multiplier == 2 or throw.ring == "inner_bull":
                player.score = 0
                self.state.winner = player.name
                self.state.phase = GamePhase.GAME_OVER
                logger.info("Winner: %s", player.name)
            else:
                # Bust: didn't finish on double
                self._bust_turn(player)
            return

        if new_score == 1:
            # Can't finish with 1 (need double), bust
            self._bust_turn(player)
            return

        player.score = new_score

    def _bust_turn(self, player: PlayerState) -> None:
        """Reset player score to start of turn (bust)."""
        turn_points = sum(t.score for t in player.current_turn)
        player.score += turn_points  # Restore points from this turn
        player.current_turn.clear()
        # Force end of turn
        self._complete_turn()

    def _score_cricket(self, player: PlayerState, throw: ThrowResult) -> None:
        """Cricket scoring: mark numbers 15-20 and bull. 3 marks to close."""
        target = throw.sector
        if target == 25 or target == 50:
            target = 25  # Bull
        if target not in player.cricket_marks:
            return  # Not a cricket number

        marks_to_add = throw.multiplier
        current_marks = player.cricket_marks[target]

        if current_marks >= 3:
            # Already closed — check if opponents have closed it too
            all_closed = all(
                p.cricket_marks.get(target, 0) >= 3
                for p in self.state.players
            )
            if not all_closed:
                # Score points for excess marks
                excess = marks_to_add
                player.score += target * excess
        else:
            new_marks = current_marks + marks_to_add
            player.cricket_marks[target] = min(new_marks, 3)
            if new_marks > 3:
                # Score excess marks if not all opponents closed
                all_closed = all(
                    p.cricket_marks.get(target, 0) >= 3
                    for p in self.state.players if p != player
                )
                if not all_closed:
                    excess = new_marks - 3
                    player.score += target * excess

        # Check for cricket win: all numbers closed + highest/equal score
        if self._check_cricket_win(player):
            self.state.winner = player.name
            self.state.phase = GamePhase.GAME_OVER

    def _check_cricket_win(self, player: PlayerState) -> bool:
        all_closed = all(v >= 3 for v in player.cricket_marks.values())
        if not all_closed:
            return False
        return all(player.score >= p.score for p in self.state.players)

    def _score_free(self, player: PlayerState, throw: ThrowResult) -> None:
        """Free play: just accumulate score."""
        player.score += throw.score

    def _complete_turn(self) -> None:
        """End current turn and move to next player."""
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

    def undo_last_throw(self) -> None:
        """Undo the last registered throw."""
        if self._undo_stack:
            self.state = self._undo_stack.pop()
            logger.info("Undo performed")

    def get_state(self) -> dict:
        """Get serializable game state."""
        return self.state.to_api_dict()

    def _push_undo(self) -> None:
        if len(self._undo_stack) >= self._max_undo:
            self._undo_stack.pop(0)
        self._undo_stack.append(self.state.model_copy(deep=True))
```

---

## Spielmodi im Detail

### X01 (301 / 501 / 701)

- **Start:** Jeder Spieler beginnt mit dem gewählten Score (z.B. 501)
- **Scoring:** Score wird subtrahiert
- **Bust-Regel:** Score darf nicht unter 0 fallen, nicht auf 1 landen, und muss mit einem Double (oder Inner Bull) beendet werden
- **Gewinner:** Erster Spieler mit exakt 0 Punkten

### Cricket

- **Zahlen:** 15, 16, 17, 18, 19, 20, Bull (25)
- **Marks:** 3 Marks zum "Schließen" einer Zahl
- **Scoring:** Nach 3 Marks darf man auf offene Zahlen der Gegner punkten
- **Gewinner:** Alle Zahlen geschlossen UND höchster (oder gleicher) Score

### Free Play

- **Keine Regeln:** Einfach Punkte sammeln
- **Kein Gewinner:** Endloses Spiel zum Üben
- **Nützlich für:** Kalibrierungs-Tests, Training

---

## Undo-Stack

- Maximal 20 Undo-Schritte (konfigurierbar)
- Jeder `register_throw()` und `next_player()` Aufruf pushed einen State-Snapshot
- `undo_last_throw()` restored den vorherigen State
- Deep-Copy via Pydantic `model_copy(deep=True)`
