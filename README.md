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

### Einzelkamera (Standard)
- Standard-Laptop (CPU-only, kein GPU)
- USB-Webcam (720p+)
- Python 3.11+

### Multi-Kamera (optional)
- 2+ USB-Kameras (identische Modelle empfohlen)
- USB-Hub mit ausreichend Bandbreite (USB 3.0+ empfohlen)
- Empfohlene Platzierung: 60-90 Grad Winkel zueinander, 50-80 cm Abstand zum Board
- Alle Kameras muessen das Dartboard vollstaendig sehen

## Multi-Kamera Setup

### Kalibrier-Workflow
1. **Lens Setup** pro Kamera: ChArUco-Board vor jede Kamera halten
2. **Board Alignment** pro Kamera: ArUco-Marker oder manuelle 4-Punkt-Auswahl
3. **Stereo-Kalibrierung** pro Kamera-Paar: ChArUco-Board gleichzeitig in beiden Kamera-Sichtfeldern

### API-Routen (Multi-Kamera)
| Route | Methode | Beschreibung |
|-------|---------|--------------|
| `/api/multi/start` | POST | Multi-Pipeline starten (Body: `{"cameras": [...]}`) |
| `/api/multi/stop` | POST | Multi-Pipeline stoppen |
| `/api/multi/status` | GET | Status aller aktiven Kameras (FPS, Kalibrierung) |
| `/api/calibration/stereo` | POST | Stereo-Kalibrierung zwischen zwei Kameras |
| `/video/feed/{camera_id}` | GET | MJPEG-Stream einer spezifischen Kamera |

### Frontend
- **Multi-Cam Button**: Oeffnet Setup-Modal fuer Kamera-Konfiguration
- **Video-Grid**: Zeigt alle aktiven Kamera-Streams nebeneinander
- **Stereo-Kalibrierung**: Im Modal mit Live-Vorschau beider Kameras
