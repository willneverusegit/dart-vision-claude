---
name: web-ui
description: FastAPI-Endpoints, WebSocket, Frontend-JS/CSS, MJPEG-Stream — aktivieren wenn an src/web/ oder static/ gearbeitet wird
type: domain
---

## Wann nutzen

- Neue oder geänderte API-Endpunkte in routes.py
- WebSocket-Events und Broadcasting
- Frontend-Änderungen in static/js/ oder static/css/
- HTML-Template-Änderungen
- MJPEG-Stream-Handling
- Kamera-Health-Anzeige im Frontend

## Pflichtlektüre vor Arbeit

1. `agent_docs/current_state.md` — Frontend-Features-Stand
2. `agent_docs/pitfalls.md` — kein _showToast, nur _showError()
3. `src/web/routes.py` lesen (HIGH-RISK, 70KB) — bestehende Patterns verstehen
4. Betroffene JS-Datei mit `node -c <file>` nach Änderungen prüfen

## Schlüsselregeln

1. **routes.py ist HIGH-RISK** (70KB, Threading + API + Runtime-Zustand zusammen) — neue Komplexität kapseln, nicht hinein kippen.
2. **Nur `_showError()` in app.js** — kein `_showToast()`, existiert nicht.
3. **Alle fetch-Aufrufe mit `response.ok`-Check** (P16): vor JSON-Parse auf HTTP-Fehler prüfen.
4. **Kein Framework einführen** — Vanilla JS bleibt (ADR-004). Kein React/Vue/Svelte ohne explizite Anfrage.
5. **Neue Logik nicht in routes.py ankern** wenn sie besser als Service oder Helper passt.
6. **WebSocket thread-sicher broadcasten** via `EventManager` — nicht direkt an Connections schreiben.
7. **JavaScript nach Änderung prüfen**: `node -c static/js/<file>.js`
8. **WCAG AA Kontrast** bei Farb-/Theme-Änderungen prüfen.
9. **Input-Validierung in routes.py** (P13): score 0-180, sector, multiplier 1-3, ring — Grenzen nicht entfernen.
10. **Deutsche Fehlermeldungen** in Kalibrierungs-Endpunkten und handlungsorientiert formulieren.

## Offene Todos (aktive P-Items)

| P-Nr | Titel | Status |
|------|-------|--------|
| P9 | Multi-Cam UX: Kamera-Vorschau, Drag-and-Drop, Wizard-Verbesserungen | NIEDRIG |
| P30 | Camera Error Reporting to UI (Multi-Cam per-camera status badges) | KRITISCH |

## Risiko-Einschätzung

**HOCH** für routes.py — Threading, App-Lifecycle und API treffen zusammen.
**NIEDRIG** für isolierte Frontend-Änderungen in static/js/ wenn keine neuen API-Calls eingeführt werden.
Immer nach JS-Änderungen: `node -c` zur Syntax-Prüfung.
