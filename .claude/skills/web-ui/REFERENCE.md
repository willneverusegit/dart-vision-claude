# Web/UI Domain Reference

## Datei-Map

| Datei | Zweck | Coverage | Status |
|-------|-------|----------|--------|
| `src/web/routes.py` | REST-Endpunkte, Kalibrierung, Multi-Cam, MJPEG | 66% | HIGH-RISK, 70KB |
| `src/web/events.py` | WebSocket-Verbindungen + thread-sicheres Broadcasting | ~80% | Stabil, 3.5KB |
| `src/web/stream.py` | MJPEG/JPEG-Helpers | - | Einfach, stabil |
| `src/web/camera_health.py` | CameraState-Enum, Health-Tracking | - | P2 ✅ |
| `src/web/stereo_progress.py` | Multi-Cam Kalibrier-Fortschritt via WebSocket | - | Task-spezifisch |
| `static/js/app.js` | Haupt-App-Logik, Tuning-UI | - | P10+P16+P23 ✅ |
| `static/js/dartboard.js` | Board-Visualisierung, Geometry-Fetch | - | P16 ✅ abgesichert |
| `static/js/scoreboard.js` | Scoreboard-Rendering, Badges | - | P7 ✅ |
| `static/js/websocket.js` | WebSocket-Client | - | P16 ✅ |
| `static/css/style.css` | Responsive Design, Dark/Light Theme | - | P10+P23 ✅ |
| `templates/index.html` | App-Entry-Point | - | Stabil |

## Wichtige API-Endpunkte

| Endpunkt | Methode | Zweck |
|----------|---------|-------|
| `/api/game/new` | POST | Neues Spiel starten |
| `/api/hits/{id}/correct` | PUT | Treffer korrigieren |
| `/api/game/manual-score` | POST | Manueller Score |
| `/api/game/checkout` | GET | Checkout-Vorschlag |
| `/api/camera/health` | GET | Kamera-Status |
| `/api/stats` | GET | FPS, Dropped, Queue, RAM |
| `/api/telemetry/history` | GET | Telemetrie-Verlauf + Alerts |
| `/api/multi/readiness` | GET | Multi-Cam pro-Kamera Diagnose |
| `/video_feed` | GET | MJPEG-Stream |

## WebSocket-Events

| Event | Richtung | Bedeutung |
|-------|----------|-----------|
| `hit_candidate` | Server→Client | Neuer Treffer-Kandidat |
| `game_update` | Server→Client | Spielstand geändert |
| `camera_state` | Server→Client | Kamera connected/reconnecting/disconnected |
| `telemetry_alert` | Server→Client | FPS/Queue-Alert Statuswechsel |

## Frontend-Patterns

- **Fehler anzeigen**: `this._showError("Nachricht")` — kein `_showToast()`
- **fetch-Pattern**: immer `if (!response.ok) { this._showError(...); return; }` vor JSON-Parse
- **WebSocket**: onerror unterscheidet Netzwerkfehler vs. Nachrichtenfehler (P16)
- **Theme**: CSS Custom Properties in `:root` (dark) und `:root.light-theme` — kein Inline-Style
- **Responsive**: Breakpoints 375px (Mobile) und 768px (Tablet) — bestehende Patterns fortführen

## Architektur-Entscheidungen

- **ADR-004**: FastAPI + Vanilla JS, kein Build-Step, kein SPA-Framework
- routes.py ist sensibel: Threading + App-Lifecycle + API zusammen — neue Komplexität als Service kapseln
- WebSocket-Broadcast immer via `EventManager`, nicht direkt
