# Game-Scoring Domain Reference

## Datei-Map

| Datei | Zweck | Status |
|-------|-------|--------|
| `src/game/engine.py` | X01/Cricket/FreePlay State-Machine | P14 ✅ gehärtet |
| `src/game/models.py` | Dataclasses: Game, Turn, Player, ThrowResult | Type-safe |
| `src/game/checkout.py` | Checkout-Tabelle 2-170 | P7+P18 ✅ |
| `src/game/modes.py` | Mode-Enum-Definitionen | Static |

## Spielmodi

| Modus | Beschreibung | Besonderheiten |
|-------|-------------|----------------|
| X01 (301/501/701) | Runter auf 0, Bust bei Überwurf | Checkout braucht Double, Bust-Handling |
| Cricket | 15-20 + Bull 3x treffen | Nur Sektoren 15-20 + 25 valid |
| FreePlay | Kein Spielziel, freies Werfen | Keine Bust-Logik |

## ThrowResult Datenstruktur

```python
ThrowResult(
    score: int,       # Rohpunkte (z.B. 60 für T20)
    sector: int,      # Board-Sektor (1-20, 25=Bull)
    multiplier: int,  # 1=Single, 2=Double, 3=Triple
    ring: str,        # "single", "double", "triple", "bull", "outer_bull"
    tip: Optional[tuple],  # Pixel-Koordinate Dart-Spitze
)
```

## Checkout-Tabelle

- Abdeckung: Score 2-170 (alles was ausscheckbar ist)
- API: `GET /api/game/checkout?score=<n>` → Liste möglicher Checkout-Pfade
- Frontend zeigt Vorschlag bei letztem Dart im Turn an
- P18 offen: 2-Dart/3-Dart Standard-Checkouts + Double-In

## Wichtige Testdateien

| Datei | Testet |
|-------|--------|
| `tests/test_game.py` | Engine-State-Machine, Spielmodi |
| `tests/test_checkout.py` | Checkout-Tabelle (11 Tests, P7) |
| `tests/test_input_validation.py` | new_game(), register_throw() Validierung (P13/P14) |

## Architektur-Notizen

- Game-Engine ist downstream von `src/web/routes.py` — API-Signatur-Änderungen propagieren
- `GameEngine` wird beim App-Start in `src/main.py` als Singleton erstellt
- WebSocket-Events bei Spielstand-Änderung via `EventManager.broadcast()`
- Spielstand ist rein in-memory — kein DB-Backend
