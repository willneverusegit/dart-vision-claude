# AGENTS.md — Dart-Vision: CPU-optimiertes Dart-Scoring-System

> Dieses Dokument wird von Codex CLI und Claude Code als Haupt-Instruktion gelesen.
> Detaillierte Modul-Spezifikationen liegen in `agent_docs/`. Lies diese bedarfsweise.

---

## Project Overview

**Dart-Vision** ist ein CPU-optimiertes Computer-Vision-System zur automatischen Dart-Treffererkennung und Scoring. Es besteht aus:

1. **CV-Backend** (Python): Kamera-Capture, Board-Kalibrierung, Dart-Detektion, Scoring-Logik
2. **Web-Frontend** (FastAPI + HTML/JS/CSS): Live-Videostream, Scoreboard, Spielmodi-Steuerung

Das System läuft auf Standard-Laptops (CPU-only, kein GPU erforderlich) mit einer USB-Webcam (720p–1080p).

### Architektur-Diagramm (ASCII)

```
┌─────────────┐    WebSocket/SSE     ┌──────────────────────┐
│  Browser UI  │◄────────────────────►│  FastAPI Server       │
│  (HTML/JS)   │    JSON events       │  (uvicorn, port 8000) │
└─────────────┘                      └──────────┬───────────┘
                                                │
                                     ┌──────────▼───────────┐
                                     │   CV Pipeline Engine  │
                                     │                       │
                                     │  ┌─────────────────┐  │
                                     │  │ ThreadedCamera   │  │
                                     │  └────────┬────────┘  │
                                     │  ┌────────▼────────┐  │
                                     │  │ CalibManager     │  │
                                     │  └────────┬────────┘  │
                                     │  ┌────────▼────────┐  │
                                     │  │ ROIProcessor     │  │
                                     │  └────────┬────────┘  │
                                     │  ┌────────▼────────┐  │
                                     │  │ MotionDetector   │  │
                                     │  │ (MOG2 Gating)    │  │
                                     │  └────────┬────────┘  │
                                     │  ┌────────▼────────┐  │
                                     │  │ DartDetector     │  │
                                     │  └────────┬────────┘  │
                                     │  ┌────────▼────────┐  │
                                     │  │ FieldMapper      │  │
                                     │  │ (Scoring)        │  │
                                     │  └─────────────────┘  │
                                     └───────────────────────┘
```

---

## Technology Stack

- **Runtime:** Python 3.11+
- **CV Library:** OpenCV 4.x (`opencv-contrib-python`)
- **Web Framework:** FastAPI + Uvicorn
- **Frontend:** Vanilla JS + HTML5 + CSS3 (kein React/Vue — bewusst minimal)
- **Config:** PyYAML
- **Dependencies:** NumPy, Jinja2
- **Testing:** pytest, pytest-cov
- **Linting:** ruff
- **Type Checking:** mypy (optional, empfohlen)

---

## Environment Setup

### Prerequisites
- Python 3.11+
- pip oder uv
- Eine USB-Webcam (720p+)

### Initial Setup
```bash
# Repo klonen und Umgebung einrichten
cd dart-vision
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

pip install -r requirements.txt
```

### requirements.txt
```
opencv-contrib-python>=4.8.0
numpy>=1.24.0
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pyyaml>=6.0
jinja2>=3.1.0
python-multipart>=0.0.6
websockets>=12.0
pytest>=8.0.0
pytest-cov>=4.1.0
ruff>=0.2.0
```

---

## Project Structure

```
dart-vision/
├── AGENTS.md                    # Diese Datei (Haupt-Instruktion)
├── agent_docs/                  # Detaillierte Modul-Spezifikationen
│   ├── 01_cv_pipeline.md        # CV-Pipeline: Capture → Detect → Score
│   ├── 02_web_frontend.md       # Web-Frontend: FastAPI + HTML/JS
│   ├── 03_game_logic.md         # Spielmodi: X01, Cricket, Free Play
│   ├── 04_calibration.md        # Kalibrierungs-Workflow im Detail
│   └── 05_testing.md            # Test-Protokoll und Akzeptanzkriterien
├── requirements.txt
├── config/
│   └── calibration_config.yaml  # Kalibrierungsdaten (auto-generiert)
├── src/
│   ├── __init__.py
│   ├── main.py                  # FastAPI App Entry Point
│   ├── cv/
│   │   ├── __init__.py
│   │   ├── capture.py           # ThreadedCamera (Producer/Consumer)
│   │   ├── calibration.py       # CalibrationManager (ChArUco + Manual)
│   │   ├── roi.py               # ROIProcessor (Homography + Polar)
│   │   ├── motion.py            # MotionDetector (MOG2 Gating)
│   │   ├── detector.py          # DartImpactDetector (Shape + Temporal)
│   │   ├── field_mapper.py      # FieldMapper (Sector + Ring Scoring)
│   │   └── pipeline.py          # DartPipeline (Orchestrator)
│   ├── game/
│   │   ├── __init__.py
│   │   ├── engine.py            # GameEngine (Spielzustand, Runden)
│   │   ├── modes.py             # X01, Cricket, Free Play
│   │   └── models.py            # Pydantic Models für Game State
│   ├── web/
│   │   ├── __init__.py
│   │   ├── routes.py            # FastAPI Routes (REST + WebSocket)
│   │   ├── stream.py            # MJPEG Video Stream Endpoint
│   │   └── events.py            # SSE/WebSocket Event Manager
│   └── utils/
│       ├── __init__.py
│       ├── fps.py               # FPSCounter
│       ├── logger.py            # StructuredLogger (JSON)
│       └── config.py            # Config Loader/Writer (atomic)
├── static/
│   ├── css/
│   │   └── style.css            # Dark-Theme Scoreboard
│   ├── js/
│   │   ├── app.js               # Main Frontend Logic
│   │   ├── scoreboard.js        # Scoreboard-Rendering
│   │   ├── dartboard.js         # SVG Dartboard Visualisierung
│   │   └── websocket.js         # WebSocket Client
│   └── img/
│       └── dartboard.svg        # SVG Dartboard Template
├── templates/
│   └── index.html               # Jinja2 Haupt-Template
└── tests/
    ├── __init__.py
    ├── test_field_mapper.py     # Unit: Sektor/Ring-Mapping
    ├── test_detector.py         # Unit: Detection Logic
    ├── test_calibration.py      # Unit: Kalibrierung
    ├── test_game_engine.py      # Unit: Spiellogik
    ├── test_pipeline.py         # Integration: Pipeline E2E
    └── conftest.py              # Fixtures (Mock Frames, Config)
```

---

## Commands

### Development
```bash
# Server starten (mit Auto-Reload)
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Nur CV-Pipeline testen (ohne Web)
python -m src.cv.pipeline --source 0 --debug
```

### Testing
```bash
# Einzelne Testdatei
python -m pytest tests/test_field_mapper.py -v

# Gesamte Test-Suite
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# Linting
ruff check src/ tests/
```

### Kalibrierung
```bash
# Manuelle 4-Punkt-Kalibrierung starten
python -m src.cv.calibration --mode manual --source 0

# ChArUco-Kalibrierung
python -m src.cv.calibration --mode charuco --source 0
```

---

## Code Style & Patterns

### Regeln
- **Sprache im Code:** Englisch (Variablen, Kommentare, Docstrings)
- **Sprache in UI/Templates:** Deutsch (kann später internationalisiert werden)
- **Type Hints:** Überall verwenden (Funktionsparameter + Rückgabewerte)
- **Docstrings:** Google-Style für alle öffentlichen Methoden
- **Max Line Length:** 100 Zeichen
- **Imports:** Absolute Imports (`from src.cv.capture import ThreadedCamera`)

### Design-Prinzipien
- **ROI-First:** Alle rechenintensiven Operationen erst nach Board-Isolation
- **Motion-Gated:** Teure Detektion nur bei erkannter Bewegung
- **Fail-Safe:** Jedes Modul hat dokumentierte Fallback-Strategien
- **Atomic Config:** Konfigurationsschreibvorgänge immer über temp-file + os.replace()

### Patterns (Beispiele)

✅ **Gut** — Modul mit klarer Schnittstelle:
```python
# src/cv/motion.py
class MotionDetector:
    """Detects motion using MOG2 background subtraction."""

    def __init__(self, threshold: int = 500, detect_shadows: bool = True) -> None:
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=detect_shadows, varThreshold=50
        )
        self.threshold = threshold

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, bool]:
        """Returns (motion_mask, motion_detected)."""
        ...
```

❌ **Vermeiden** — God-Object, keine Typen:
```python
class Pipeline:
    def do_everything(self, frame):  # Keine Typen, zu viel Verantwortung
        ...
```

---

## Detailed Module Documentation

Lies die folgenden Dateien, wenn du das jeweilige Modul implementierst:

| Datei | Inhalt | Wann lesen? |
|-------|--------|-------------|
| `agent_docs/01_cv_pipeline.md` | CV-Pipeline: Capture, ROI, Motion, Detection, Scoring — komplette Implementierungs-Rezepte mit Code | Bei Arbeit an `src/cv/` |
| `agent_docs/02_web_frontend.md` | FastAPI-Server, WebSocket-Protokoll, MJPEG-Stream, HTML/JS-Frontend | Bei Arbeit an `src/web/`, `static/`, `templates/` |
| `agent_docs/03_game_logic.md` | Spielmodi (X01, Cricket, Free Play), Zustandsmaschine, Undo-Stack | Bei Arbeit an `src/game/` |
| `agent_docs/04_calibration.md` | Kalibrierungs-Workflow, ChArUco vs. Manual, Config-Schema | Bei Arbeit an `src/cv/calibration.py` |
| `agent_docs/05_testing.md` | Testprotokoll, Akzeptanzkriterien, Mock-Strategien, Benchmark-Scripts | Bei Arbeit an `tests/` |

---

## Acceptance Criteria (KPIs)

| Metrik | Akzeptanzkriterium |
|--------|-------------------|
| Median FPS | ≥ 15 FPS (720p, 60s continuous) |
| P95 FPS | ≥ 10 FPS |
| End-to-End Latency | ≤ 200ms (Frame → Score) |
| Hit Localization | ≤ 10mm RMS (20 Darts, Ground Truth) |
| False Positive Rate | ≤ 5% (100 Frames ohne Darts) |
| CPU Usage | ≤ 70% (Durchschnitt, 60s) |
| Memory | ≤ 512 MB RAM |

---

## Implementation Order (Phasen)

Implementiere in dieser Reihenfolge. Jede Phase muss testbar sein, bevor die nächste beginnt.

### Phase 1: CV-Core (src/cv/)
1. `capture.py` — ThreadedCamera mit Bounded Queue
2. `roi.py` — ROIProcessor mit Homography + Polar Unwrap
3. `motion.py` — MotionDetector mit MOG2
4. `detector.py` — DartImpactDetector (Shape + Temporal Confirmation)
5. `field_mapper.py` — FieldMapper (Sektor + Ring → Score)
6. `pipeline.py` — DartPipeline (Orchestrator, verbindet alle Module)

**Validierung Phase 1:** `python -m src.cv.pipeline --source 0 --debug` zeigt OpenCV-Fenster mit HUD-Overlay (FPS, detected score, motion mask).

### Phase 2: Kalibrierung (src/cv/calibration.py)
1. Manuelle 4-Punkt-Kalibrierung (CLI mit Maus-Clicks)
2. ChArUco-basierte Auto-Kalibrierung (optional, höhere Genauigkeit)
3. Atomic Config Write/Load

**Validierung Phase 2:** Kalibrierung über CLI durchführbar, Config wird in `config/calibration_config.yaml` gespeichert.

### Phase 3: Spiellogik (src/game/)
1. `models.py` — Pydantic Models (Player, Turn, GameState)
2. `engine.py` — GameEngine (Zustandsmaschine)
3. `modes.py` — X01 (301/501/701), Cricket, Free Play

**Validierung Phase 3:** Unit-Tests für alle Spielmodi bestehen.

### Phase 4: Web-Frontend (src/web/ + static/ + templates/)
1. `routes.py` — FastAPI REST + WebSocket Endpoints
2. `stream.py` — MJPEG Video Stream
3. `events.py` — Event Manager (Score-Events → WebSocket)
4. `templates/index.html` — Haupt-Layout
5. `static/js/` — Scoreboard, Dartboard-SVG, WebSocket-Client
6. `static/css/style.css` — Dark Theme

**Validierung Phase 4:** Browser öffnen auf `http://localhost:8000`, Live-Stream + Scoreboard sichtbar.

### Phase 5: Integration & Polish
1. Pipeline ↔ GameEngine ↔ WebSocket verbinden
2. Error-Handling und Graceful Degradation
3. Performance-Benchmarks gegen KPIs
4. README.md schreiben

---

## Critical Decision Points

An diesen Stellen MUSST du nachfragen (oder die pragmatische Default-Entscheidung treffen):

| Entscheidung | Pragmatischer Default | Wann nachfragen? |
|-------------|----------------------|-------------------|
| Kamera-Quelle | `cv2.VideoCapture(0)` (erste USB-Cam) | Wenn mehrere Kameras erkannt werden |
| Board-Kalibrierung | Manuelle 4-Punkt-Kalibrierung zuerst | ChArUco nur implementieren, wenn Phase 1+2 stabil |
| Spielmodus-Default | 501 (X01) | Nie — ist Standard |
| Frontend-Framework | Vanilla JS (kein React/Vue) | Nie — bewusste Entscheidung |
| Video-Stream-Methode | MJPEG über HTTP (StreamingResponse) | WebSocket-Stream nur bei Latenz-Problemen |
| CLAHE aktiviert | Ja, immer als Preprocessing | Nie — verbessert Robustheit ohne Kosten |

---

## Permissions

### Erlaubt ohne Rückfrage
- Dateien lesen, erstellen, bearbeiten innerhalb `dart-vision/`
- Tests ausführen (`pytest`)
- Linting (`ruff check`)
- Server starten (`uvicorn`)
- pip install aus requirements.txt

### Rückfrage erforderlich
- Neue externe Dependencies hinzufügen (außer den gelisteten)
- Architektur-Änderungen (andere Ordnerstruktur)
- GPU/CUDA-basierte Lösungen
- Deep-Learning-Modelle (YOLO etc.) — das Projekt ist bewusst klassisch CV

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Kamera nicht erkannt | `cv2.VideoCapture(0)` → versuche `1`, `2`, oder `/dev/video0` |
| Niedrige FPS | ROI-Size verkleinern, Frame-Decimation aktivieren, Resolution auf 720p |
| Viele False Positives | `confirmation_threshold` erhöhen (3 → 5 Frames) |
| Homography ungültig | Identity-Transform als Fallback, Neukalibierung anfordern |
| CLAHE zu aggressiv | `clipLimit` reduzieren (default 2.0 → 1.5) |
| WebSocket-Verbindung bricht ab | Auto-Reconnect im JS-Client mit Exponential Backoff |
