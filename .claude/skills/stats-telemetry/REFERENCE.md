# Stats/Telemetry Domain Reference

## Datei-Map

| Datei | Zweck | Tests | Status |
|-------|-------|-------|--------|
| `src/utils/telemetry.py` | TelemetryHistory Ring-Buffer, FPS/Queue-Alerts | 17 Tests | P8 ✅ |
| `src/utils/logger.py` | Session-basiertes Logging, File-Rotation | 8 Tests | P4 ✅ idempotent |
| `src/utils/fps.py` | FPS-Tracking | - | Einfach |
| `src/utils/triangulation_telemetry.py` | Multi-Cam Triangulations-Metriken | - | Instrumentation |

## TelemetryHistory API

```python
telemetry = TelemetryHistory(max_samples=300)  # Ring-Buffer
telemetry.add_sample(fps, dropped_frames, queue_pressure, ram_mb, cpu_pct=None)
telemetry.get_history()   # → {'fps': [...], 'queue': [...], ...}
telemetry.get_alerts()    # → [{'type': 'fps_low', 'sustained_seconds': 7.3, ...}]
telemetry.get_summary()   # → {'avg_fps': 28.5, 'max_queue': 0.6, ...}
```

**Alert-Schwellen:**
- FPS < 15 für > 5s → `fps_low` Alert
- Queue-Druck > 80% für > 5s → `queue_high` Alert

## WebSocket-Event: `telemetry_alert`

Wird gebroadcastet wenn sich Alert-Zustand ändert (ein-/ausschalten).
Enthält: `alerts: [...]`, `summary: {...}`.

## API-Endpunkte

| Endpunkt | Zweck |
|----------|-------|
| `GET /api/stats` | FPS, Dropped, Queue, RAM (aktuell) |
| `GET /api/telemetry/history` | Ring-Buffer-History + Alerts + Summary |

## Session-Logging

- **Session-ID**: 8-Zeichen UUID-Prefix, gesetzt beim App-Start in `src/main.py`
- **File-Logging**: Via `DARTVISION_LOG_FILE` Env-Variable (5MB, 3 Backups)
- **Idempotenz**: `setup_logging()` kann mehrfach aufgerufen werden ohne Handler-Duplikate
- **JSON-Format**: Optional aktivierbar mit Session-ID

## Wichtige Testdatei

| Datei | Testet |
|-------|--------|
| `tests/test_telemetry.py` | Ring-Buffer, Alert-Sustain, Summary (17 Tests) |
| `tests/test_logger.py` | Idempotenz, Rotation, Session-ID (8 Tests) |
