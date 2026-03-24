---
name: api-endpoint-audit
description: Scannt FastAPI-Endpoints in routes.py und prueft ob jeder Endpoint durch mindestens einen Test abgedeckt ist. Findet ungetestete Routen und fehlende Error-Cases.
---

# API Endpoint Audit

Findet ungetestete FastAPI-Endpoints und fehlende Test-Coverage.

## Workflow

### 1. Alle Endpoints extrahieren

Suche in `src/web/routes.py` nach Route-Dekoratoren:

```
grep -n "@app\.\(get\|post\|put\|delete\|websocket\)" src/web/routes.py
```

Erstelle eine Liste aller Endpoints mit HTTP-Methode und Pfad.

### 2. Test-Coverage pruefen

Suche in `tests/test_routes*.py` nach Test-Funktionen die jeden Endpoint testen:

```
grep -rn "def test_.*<endpoint_name_pattern>" tests/test_routes*.py
```

Fuer jeden Endpoint pruefen:
- Gibt es mindestens einen Happy-Path-Test?
- Gibt es Error-Case-Tests (404, 400, fehlende Parameter)?
- Bei POST-Endpoints: Werden Validierungsfehler getestet?

### 3. Report ausgeben

```
API ENDPOINT AUDIT
==================
Endpoints gesamt: X
Getestet:         Y (Z%)
Ungetestet:       N

✅ GET  /api/status              → test_routes_coverage.py:42
✅ POST /api/calibrate/start     → test_routes_coverage2.py:15
⚠️ GET  /api/multi/readiness     → KEIN TEST
⚠️ POST /api/cv-params           → Nur Happy-Path, kein Error-Case

Empfehlung: Tests fuer folgende Endpoints erstellen: [Liste]
```

### 4. Besondere Aufmerksamkeit

- WebSocket-Endpoints (`@app.websocket`) brauchen async Tests
- Endpoints mit `camera_preview_lock` muessen Concurrency testen
- Multi-Cam-Endpoints (`/api/multi/*`) muessen Single-Cam-Fallback testen
- Kalibrierungs-Endpoints muessen fehlende Config testen
