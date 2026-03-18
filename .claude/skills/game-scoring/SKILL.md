---
name: game-scoring
description: Spiellogik X01/Cricket/FreePlay, Score-Berechnung, Checkout — aktivieren wenn an src/game/ gearbeitet wird
type: domain
---

## Wann nutzen

- Änderungen an Spielmodi (X01, Cricket, FreePlay)
- Score-Berechnung, Checkout-Tabelle, Undo-Logik
- Spieler-Verwaltung, Turn-Handling, ThrowResult-Verarbeitung
- Neue Spielvarianten (Double-In, Handicap etc.)

## Pflichtlektüre vor Arbeit

1. `agent_docs/current_state.md` — Game-Engine-Status
2. `src/game/models.py` — Dataclasses lesen bevor engine.py geändert wird
3. `src/game/engine.py` — State-Machine verstehen
4. `tests/test_game.py`, `tests/test_checkout.py` — bestehende Tests

## Schlüsselregeln

1. **Spielregeln deterministisch**: Jede Regeländerung braucht direkte Testabdeckung.
2. **new_game() validiert**: starting_score (1-10000), non-empty players — Grenzen nicht entfernen.
3. **register_throw() schützt gegen >3 Darts**: Auto-complete Turn bei >3. Pflichtfelder werden geprüft.
4. **Cricket-Sektoren**: Nur 15-20 und 25 erlaubt — Validierung bei Bedarf prüfen.
5. **Checkout-Tabelle**: Abdeckung 2-170 (P7+P18). Neue Varianten mit Tests implementieren.
6. **ThrowResult-Felder**: Vor register_throw() alle Pflichtfelder prüfen — kein stilles Korrumpieren des Spielstands.
7. **Keine API-Breaks ohne Tests**: engine.py ist downstream von routes.py — Signatur-Änderungen propagieren.
8. **Checkout nach Wurf anpassen**: P18 — Checkout-Vorschlag für 2./3. Dart der Runde noch offen.

## Offene Todos (aktive P-Items)

| P-Nr | Titel | Status |
|------|-------|--------|
| P18 | Checkout-Tabelle: 2-Dart/3-Dart Pfade + Double-In-Variante | OFFEN |

## Risiko-Einschätzung

**NIEDRIG-MITTEL** — engine.py ist gut getestet (P14). Neue Spielvarianten sind isolierbar.
Vorsicht bei: Undo-Logik, Turn-Boundary-Handling, Score-Overflow-Fällen (Bust).
