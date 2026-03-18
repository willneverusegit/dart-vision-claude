# Meta/Infra Domain Reference

## Datei-Map

| Datei | Zweck | Coverage | Status |
|-------|-------|----------|--------|
| `src/main.py` | App-Start, FastAPI-Lifespan, globaler Zustand, Hintergrundthreads | 78% | HIGH-RISK |
| `src/utils/config.py` | YAML-Laden/-Speichern + Schema-Validierung | ~85% | P17 ✅ gehärtet |
| `src/cv/capture.py` | ThreadedCamera mit bounded queue, Reconnect-State-Machine | 72% | P2 ✅ |
| `src/diagnose.py` | Startup-Diagnose: Python, Deps, Kameras, Config, Kalibrierung | ~80% | P5 ✅ |
| `tests/conftest.py` | Pytest-Fixtures | - | Stabil |
| `tests/e2e/` | E2E-Replay-Tests, Synthetic-Clip-Generator | - | P1 ✅ |
| `scripts/pre_commit_check.sh` | Quality Gate | - | Aktiv als CI |
| `scripts/record_camera.py` | Kamera-Aufnahme für Testvideos | - | P39 ✅ |
| `scripts/test_all_videos.py` | Batch-Video-Test | - | P39 ✅ |

## App-Lifecycle (main.py)

```python
# FastAPI Lifespan-Kontext:
startup:
  → setup_logging()
  → GameEngine()
  → EventManager()
  → app_state = {}
  → start_pipeline()  # Single oder Multi-Cam
  → start_telemetry_task()  # async, 1s-Intervall

shutdown:
  → shutdown_event.set()
  → pipeline.stop()
  → join all threads
```

## ThreadedCamera State-Machine (capture.py)

```
CONNECTED → (USB-Fehler/Timeout) → RECONNECTING → (Verbindung wieder) → CONNECTED
RECONNECTING → (max retries) → DISCONNECTED
```
- Exponentieller Backoff: 1, 2, 4, 8, ... 30s
- State-Change-Callback: WebSocket-Broadcast via EventManager

## Config-Schema (config.py)

```python
load_calibration_config()      # Lädt + validiert mit Warn-Logging (kein Raise)
save_stereo_pair()             # Prüft Matrix-Shapes, ValueError bei ungültigem Input
save_board_transform()         # Prüft Matrix-Shapes
validate_calibration_config()  # Schema-Prüfung: Keys, Typen, Matrix-Shapes
validate_matrix_shape()        # Matrix-Dimensions-Check
```

## Test-Infrastruktur

| Typ | Anzahl | Zweck |
|-----|--------|-------|
| Unit | 400+ | Einzelne Module isoliert |
| Integration | 80+ | Pipeline, Game, Web-Layer |
| E2E/Benchmark | 60+ | Synthetic Replay, Performance |
| Gesamt | 540 | Stand 2026-03-17, ~73% Coverage |

**Wichtige Testbefehle:**
```bash
python -m pytest -q                                    # Alle Tests
python -m pytest tests/test_pipeline.py -q             # Single-Cam-spezifisch
python -m pytest tests/test_multi_camera.py -q         # Multi-Cam (fragiler)
python -m pytest tests/e2e/test_replay_e2e.py -q       # E2E
python -m pytest --cov=src -q                          # Mit Coverage
```

## Windows-Spezifika

- `.venv/Scripts/python.exe` nutzen wenn `.venv/` existiert
- `start.bat` aktiviert venv automatisch + Diagnose vor Server-Start
- Kamera-Indizes: USB-Kameras können beim Standby disconnecten
- Pfade: immer `os.path.join` oder Forward-Slashes

## Architektur-Entscheidungen

- **ADR-003**: ThreadedCamera + Stop-Events (kein Process-Pool) — GIL-Limitation akzeptiert
- **ADR-005**: Agent-Selbstverbesserung via Docs — priorities.md + current_state.md nach jeder Session
