# Session 2026-03-17: P20 Pending-Hit-Lifecycle

## Erledigt
- Zentrale Pending-Hit-Helper in `src/main.py` eingefuehrt: `add_pending_hit()`, `expire_pending_hits()`, `pop_pending_hit()`, `get_pending_hits_snapshot()`, `clear_pending_hits()`.
- Serverseitige TTL (`30s`) und harte Obergrenze (`10`) fuer offene Kandidaten umgesetzt.
- Periodisches Pending-Hit-Cleanup in Single- und Multi-Pipeline-Loop eingebaut.
- `/api/hits/pending`, `/api/stats` und WebSocket-Initialzustand auf die serverseitig bereinigte Pending-Hit-Sicht umgestellt.
- Neue Stats-Felder fuer Timeout- und Overflow-Lifecycle verifiziert.
- Gesamte Test-Suite erfolgreich durchlaufen: `505 passed`.

## Probleme
- Der erste Overflow-Test war versehentlich schon im TTL-Pfad, weil die Test-Timestamps zu alt waren.

## Gelernt
- Bei shared runtime queues muessen Timeout und Overflow als zwei getrennte Zeitachsen getestet werden.
- Wenn Lifespan-Setup globalen State zurücksetzt, muessen Route-Tests ihre Manipulation nach dem `TestClient`-Start platzieren.

## Folgepunkte
- `P23` ist jetzt der naechste saubere Anschluss: `app_state`-Mutation fuer Lifecycle und Pending-Hits weiter kapseln.
