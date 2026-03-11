# Dart-Vision 🎯

CPU-optimiertes Computer-Vision-System zur automatischen Dart-Treffererkennung und Scoring.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Dann im Browser öffnen: `http://localhost:8000`

## Für Coding Agents

Dieses Repo enthält eine vollständige Instruktion für AI Coding Agents:

- **`AGENTS.md`** — Haupt-Instruktion (Codex CLI, Claude Code, Cursor, Copilot)
- **`CLAUDE.md`** — Symlink auf AGENTS.md (Claude Code Kompatibilität)
- **`agent_docs/`** — Detaillierte Modul-Spezifikationen (Progressive Disclosure)

### Empfohlener Workflow

```bash
# Codex CLI
codex "Implementiere Phase 1: CV-Core Module (src/cv/)"

# Claude Code
claude "Lies AGENTS.md und implementiere Phase 1: CV-Core Module"
```

## Architektur

- **CV-Backend:** Python + OpenCV (klassische CV, kein Deep Learning)
- **Web-Frontend:** FastAPI + Vanilla JS (Dark Theme, WebSocket)
- **Spiellogik:** X01, Cricket, Free Play

## Hardware-Anforderungen

- Standard-Laptop (CPU-only, kein GPU)
- USB-Webcam (720p+)
- Python 3.11+
