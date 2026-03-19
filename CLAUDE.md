# CLAUDE.md

Dart-Vision: kamerabasiertes Dart-Erkennungssystem (Python/FastAPI/OpenCV).

## Modulstruktur

- `src/cv/` — Computer Vision: Kalibrierung, Erkennung, Pipeline, Tip-Detection, Multi-Cam
- `src/game/` — Spiellogik: Engine, Modi, Checkout-Berechnung
- `src/web/` — FastAPI-Server: Routes, Events, Video-Stream
- `src/utils/` — Config, Logging, Telemetrie

## Befehle

```bash
pip install -r requirements.txt        # Abhaengigkeiten installieren
python -m src.main                     # App starten (FastAPI + Kamera)
python -m pytest -q                    # Tests ausfuehren
python -m pytest --cov=src -q          # Tests mit Coverage
ruff check src/ tests/                 # Linting
scripts/pre_commit_check.sh            # Pre-Commit Quality Gate
python scripts/record_camera.py --duration 30 --show  # Kamera-Aufnahme fuer Testvideos
python scripts/test_all_videos.py --marker-size 100 --marker-spacing 365  # Batch-Video-Test
```

## Umgebung

- Windows: `.venv/Scripts/python.exe` nutzen wenn `.venv/` existiert
- Ruff-Hook laeuft automatisch nach jedem Python-Edit (PostToolUse)
- JS-Syntax-Check (`node -c`) laeuft automatisch nach JS-Edits (PostToolUse)
- context7 MCP Server verfuegbar fuer OpenCV/FastAPI-Docs

## Lesepfade

Vor Arbeit an Code: `agent_docs/current_state.md` lesen fuer den aktuellen Stand.

| Aufgabentyp | Zusaetzlich lesen |
|-------------|-------------------|
| Single-Cam / Runtime | `architecture.md` → `development_workflow.md` |
| Multi-Cam | `architecture.md` → `priorities.md` → `MULTI_CAM_INSTRUCTIONS.md` |
| Kalibrierung | `hardware_constraints.md` → `development_workflow.md` |
| Pitfall-Bereich | `pitfalls.md` fuer bekannte Stolpersteine |

## Repo-Regeln (Kurzform)

- Single-Camera = stabiler Hauptpfad, nicht verschlechtern
- CPU-only gewollt — keine GPU/ML ohne expliziten Userwunsch
- `testvids/*.mp4` nicht committen, nur `ground_truth.yaml`
- Frontend: nur `_showError()` in app.js, kein `_showToast`
- Sensible Dateien (`main.py`, `routes.py`, `multi_camera.py`): defensiv aendern
- Vollstaendige Regeln: siehe `AGENTS.md`

## Verfuegbare Automations

- `/run-diagnostics` — Kamera-Diagnostik
- `/session-log` — Session-Abschluss (Log, priorities, current_state)
- `/save-session` — Kompletter Session-Abschluss (alle Protokolle gebuendelt)
- `/task-splitter` — Aufgaben in parallele Agenten zerlegen
- `.claude/agents/calibration-reviewer.md` — Review-Agent fuer Kalibrierung
- `/agentic-os:init` — Memory-System in neuem Projekt initialisieren
- `/agentic-os:status` — System-Health und Memory-Status anzeigen
- `/agentic-os:sync` — Learnings zwischen Projekt und Global synchronisieren

## Session-Start Prioritaet

Bei jedem Session-Start ZUERST `agentic-os:heartbeat` ausfuehren — noch vor anderen Skill-Checks.
Dies hat Vorrang vor dem superpowers:using-superpowers Hook.
Danach den normalen superpowers-Workflow befolgen.

## Prozess-Regeln

Alle Prozess-Regeln (Iteration-Logging, Fortschrittsdoku, Session-Start/-Ende) stehen in `agent_docs/agent_workflow.md`.

## Abschlussformat

Nenne am Ende: geaenderte Dateien, ausgefuehrte Tests, offene Risiken.
