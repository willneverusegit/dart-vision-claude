"""Pydantic models for game state serialization."""

from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime, timezone


class GameMode(str, Enum):
    """Available game modes."""
    X01 = "x01"
    CRICKET = "cricket"
    FREE = "free"


class GamePhase(str, Enum):
    """Game state machine phases."""
    IDLE = "idle"
    PLAYING = "playing"
    GAME_OVER = "game_over"


class ThrowResult(BaseModel):
    """A single dart throw result."""
    score: int              # Total points (e.g., 60 for T20)
    sector: int             # Base sector (e.g., 20)
    multiplier: int         # 1, 2, or 3
    ring: str               # "single", "double", "triple", etc.
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlayerState(BaseModel):
    """State of a single player."""
    name: str
    score: int                                       # Remaining (X01) or total (Free/Cricket)
    throws_history: list[list[ThrowResult]] = []     # List of turns
    current_turn: list[ThrowResult] = []
    cricket_marks: dict[int, int] = {}               # {20: 3, 19: 2, ...}


class GameState(BaseModel):
    """Complete game state, serializable to JSON."""
    mode: GameMode = GameMode.X01
    phase: GamePhase = GamePhase.IDLE
    players: list[PlayerState] = []
    current_player_index: int = 0
    round_number: int = 1
    starting_score: int = 501
    winner: str | None = None

    @property
    def current_player(self) -> PlayerState | None:
        """Get active player."""
        if self.players:
            return self.players[self.current_player_index]
        return None

    @property
    def darts_thrown(self) -> int:
        """Number of darts thrown in current turn."""
        if self.current_player:
            return len(self.current_player.current_turn)
        return 0

    @property
    def darts_remaining(self) -> int:
        """Darts left in current turn (max 3)."""
        return 3 - self.darts_thrown

    @property
    def turn_total(self) -> int:
        """Sum of scores in current turn."""
        if self.current_player:
            return sum(t.score for t in self.current_player.current_turn)
        return 0

    def _get_checkout_suggestion(self) -> list[str]:
        """Get checkout suggestions for current player in X01."""
        if self.mode != GameMode.X01 or not self.current_player:
            return []
        remaining = self.current_player.score
        darts_left = self.darts_remaining
        if remaining > 170 or remaining < 2 or darts_left == 0:
            return []
        from src.game.checkout import get_checkout
        return get_checkout(remaining, darts_left)

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
            "checkout": self._get_checkout_suggestion(),
        }
