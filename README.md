# Dart-Vision

CPU-optimiertes Computer-Vision-System zur automatischen Dart-Treffererkennung und zum Scoring.

## Aktueller Stand

- Single-Camera ist der stabile Hauptpfad.
- Multi-Camera ist bereits weit entwickelt, aber noch sensibler im Betrieb.
- Das System ist bewusst auf **CPU-only** ausgelegt.
- Der aktuelle Projektstatus ist dokumentiert in `PROJEKTSTAND_2026-03-16.md`.

## Quickstart

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Dann im Browser oeffnen:

- `http://localhost:8000`

## Projektstruktur

- `src/` - Backend, CV-Pipeline, Spiel-Engine, Web-Schicht
- `static/` - JavaScript und CSS fuer die Weboberflaeche
- `templates/` - HTML-Templates
- `config/` - Kalibrierungs- und Multi-Cam-Konfiguration
- `tests/` - Unit-, Integrations- und Benchmark-Tests

## Dokumentation

### Fuer Menschen

- `PROJEKTSTAND_2026-03-16.md` - verifizierter Projektstatus, Hardware-Abgleich, Risiken, Prioritaeten
- `MULTI_CAM_INSTRUCTIONS.md` - detaillierte Multi-Cam-Hinweise
- `MULTI_CAM_WORKFLOW.md` - Multi-Cam-Workflow und Kalibrierungsablauf

### Fuer Coding Agents

- `AGENTS.md` - zentrale Repo-Anweisung, primar fuer Codex und allgemeine Coding Agents
- `AGEND.md` - Alias auf `AGENTS.md`
- `CLAUDE.md` - Claude-Code-spezifischer Einstieg
- `agent_docs/INDEX.md` - Einstieg in die strukturierte Agent-Doku
- `agent_docs/codex.md` - Codex-spezifische Arbeitsweise in diesem Repo
- `agent_docs/claude_code.md` - Claude-Code-spezifische Arbeitsweise in diesem Repo

## Empfohlene Lesereihenfolge fuer Agents

### Codex

1. `AGENTS.md`
2. `agent_docs/INDEX.md`
3. `agent_docs/codex.md`
4. aufgabenspezifische Dateien in `agent_docs/`
5. erst dann betroffene Code-Module

### Claude Code

1. `CLAUDE.md`
2. `agent_docs/INDEX.md`
3. `agent_docs/claude_code.md`
4. aufgabenspezifische Dateien in `agent_docs/`
5. erst dann betroffene Code-Module

## Architektur in Kurzform

- CV-Backend: Python + OpenCV + NumPy
- Web: FastAPI + MJPEG + WebSocket
- Frontend: Vanilla JS + HTML + CSS
- Spiellogik: X01, Cricket, Free Play
- Kalibrierung: ArUco, ChArUco, manuelle Board-Ausrichtung

## Hardware-Zielbild

Zielplattform ist ein normaler Laptop ohne dedizierte GPU. Die Entwicklung soll sich an konservativen CPU- und Speichergrenzen orientieren. Details stehen in:

- `C:/Users/domes/OneDrive/Desktop/Laptop_hardware/hardware_constraints.md`
- `agent_docs/hardware_constraints.md`

## Typische Testkommandos

```powershell
python -m pytest -q
python -m pytest tests/test_pipeline.py tests/test_web.py -q
python -m pytest tests/test_multi_camera.py tests/test_multi_cam_config.py -q
python -m tests.benchmark_pipeline --duration 5 --cameras 1
```

