---
name: stats-telemetry
description: Performance-Monitoring, FPS/Queue-Alerts, Session-Logging, Metriken — aktivieren wenn an src/utils/telemetry.py, logger.py, fps.py gearbeitet wird
type: domain
---

## Wann nutzen

- Änderungen an TelemetryHistory, Ring-Buffer, Alert-Logik
- Session-Logging, Log-Rotation, Session-ID
- FPS-Tracking, Queue-Druck-Monitoring
- Neue Metriken oder Telemetrie-Endpunkte
- Triangulations-Metriken (triangulation_telemetry.py)
- CPU-Monitoring via psutil

## Pflichtlektüre vor Arbeit

1. `src/utils/telemetry.py` — TelemetryHistory lesen
2. `tests/test_telemetry.py` — 17 Tests, Pattern verstehen
3. `agent_docs/current_state.md` → Telemetrie-Abschnitt

## Schlüsselregeln

1. **Ring-Buffer-Größe 300 Samples** — nicht ohne Grund erhöhen (Speicher auf Ziel-Laptop).
2. **Alert-Sustain-Intervall 5s**: FPS/Queue-Alerts feuern erst nach 5s anhaltender Über-/Unterschreitung — nicht auf single-sample triggern.
3. **Logging idempotent**: Kein doppeltes Handler-Registrieren — `logger.py` prüft bestehende Handler.
4. **Session-ID konsistent**: 8-Zeichen UUID-Prefix in allen Log-Zeilen derselben Session.
5. **psutil optional**: CPU-Monitoring nur wenn psutil verfügbar — kein Hard-Fail wenn fehlt.
6. **Telemetrie async**: Sammlung im Lifespan-Task (1s-Intervall) — nicht synchron in Request-Pfad.
7. **P22 offen**: Telemetrie-Export als JSONL/CSV noch nicht implementiert.

## Offene Todos (aktive P-Items)

| P-Nr | Titel | Status |
|------|-------|--------|
| P22 | Telemetrie-Export (JSONL/CSV Download, Session-ID-Verknüpfung) | OFFEN |
| P32 | Triangulation Telemetrie (Erfolgsrate, Reproj-Fehler, Z-Depth) | KRITISCH |

## Risiko-Einschätzung

**NIEDRIG** — Telemetrie ist ein reines Beobachtungssystem ohne Steuerungseinfluss auf die Pipeline.
Vorsicht bei: Threading (Telemetrie läuft in eigenem Async-Task), WebSocket-Broadcast bei Alert-Wechsel.
