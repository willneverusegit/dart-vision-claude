# Web-Frontend: FastAPI + HTML/JS Spezifikation

> Lies dieses Dokument, wenn du an `src/web/`, `static/`, oder `templates/` arbeitest.

---

## Übersicht

Das Web-Frontend liefert:
1. **Live-Videostream** (MJPEG über HTTP oder WebSocket)
2. **Echtzeit-Scoreboard** (WebSocket-Events)
3. **Spielsteuerung** (Spielmodus wählen, Spieler verwalten, Undo)
4. **Kalibrierungs-UI** (4-Punkt-Kalibrierung im Browser)
5. **Einstellungen** (Kamera-Quelle, Thresholds, etc.)

### Tech-Stack
- **Backend:** FastAPI + Uvicorn
- **Templating:** Jinja2
- **Echtzeit:** WebSocket (JSON-Protokoll)
- **Video:** MJPEG StreamingResponse
- **Frontend:** Vanilla JS (ES6+), HTML5, CSS3 (kein Framework)
- **Dartboard-Visualisierung:** SVG (interaktiv)

---

## FastAPI Server (`src/main.py`)

### Entry Point
```python
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager

from src.cv.pipeline import DartPipeline
from src.game.engine import GameEngine
from src.web.routes import router
from src.web.events import EventManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage CV pipeline and game engine lifecycle."""
    # Startup
    pipeline = DartPipeline(
        camera_src=0,
        on_dart_detected=app.state.event_manager.broadcast_detection,
        debug=False
    )
    pipeline.start()
    app.state.pipeline = pipeline
    app.state.game_engine = GameEngine()
    yield
    # Shutdown
    pipeline.stop()


app = FastAPI(title="Dart-Vision", lifespan=lifespan)
app.state.event_manager = EventManager()

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Routes
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
```

---

## API Endpoints (`src/web/routes.py`)

### REST Endpoints

| Method | Path | Beschreibung | Request Body | Response |
|--------|------|-------------|-------------|----------|
| GET | `/` | Haupt-UI (HTML) | — | HTML |
| GET | `/api/state` | Aktueller Spielzustand | — | JSON: GameState |
| POST | `/api/game/new` | Neues Spiel starten | `{mode, players, starting_score}` | JSON: GameState |
| POST | `/api/game/undo` | Letzten Wurf rückgängig | — | JSON: GameState |
| POST | `/api/game/next-player` | Nächster Spieler | — | JSON: GameState |
| POST | `/api/game/remove-darts` | Darts entfernt (Turn reset) | — | JSON: `{ok: true}` |
| GET | `/api/calibration` | Kalibrierungsstatus | — | JSON: CalibConfig |
| POST | `/api/calibration/manual` | 4-Punkt-Kalibrierung | `{points: [[x,y],...]}` | JSON: `{ok, error?}` |
| GET | `/api/stats` | Performance-Statistiken | — | JSON: FPS, Latency, CPU |
| GET | `/video/feed` | MJPEG Live-Stream | — | `multipart/x-mixed-replace` |

### WebSocket Endpoint

| Path | Beschreibung |
|------|-------------|
| `ws://host:8000/ws` | Bidirektionale Echtzeit-Kommunikation |

### Route-Implementierung
```python
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

router = APIRouter()


# --- HTML ---
@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return request.app.state.templates.TemplateResponse(
        "index.html", {"request": request}
    )


# --- MJPEG Stream ---
@router.get("/video/feed")
async def video_feed(request: Request):
    pipeline = request.app.state.pipeline

    async def generate_frames():
        while True:
            frame = pipeline.get_annotated_frame()
            if frame is not None:
                import cv2
                ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + buffer.tobytes()
                        + b"\r\n"
                    )
            import asyncio
            await asyncio.sleep(0.033)  # ~30 FPS max

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# --- Game API ---
class NewGameRequest(BaseModel):
    mode: str = "x01"           # "x01", "cricket", "free"
    players: list[str] = ["Player 1"]
    starting_score: int = 501   # Nur für X01


@router.post("/api/game/new")
async def new_game(request: Request, body: NewGameRequest):
    engine = request.app.state.game_engine
    engine.new_game(mode=body.mode, players=body.players, starting_score=body.starting_score)
    request.app.state.pipeline.reset_turn()
    return engine.get_state()


@router.post("/api/game/undo")
async def undo_throw(request: Request):
    engine = request.app.state.game_engine
    engine.undo_last_throw()
    return engine.get_state()


@router.post("/api/game/next-player")
async def next_player(request: Request):
    engine = request.app.state.game_engine
    engine.next_player()
    request.app.state.pipeline.reset_turn()
    return engine.get_state()


@router.post("/api/game/remove-darts")
async def remove_darts(request: Request):
    request.app.state.pipeline.reset_turn()
    return {"ok": True}


# --- Calibration ---
class CalibrationRequest(BaseModel):
    points: list[list[float]]   # 4 Punkte: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]


@router.post("/api/calibration/manual")
async def manual_calibration(request: Request, body: CalibrationRequest):
    pipeline = request.app.state.pipeline
    try:
        import numpy as np
        src_points = np.array(body.points, dtype=np.float32)
        # Standard board destination (400x400 ROI)
        dst_points = np.float32([[0, 0], [400, 0], [400, 400], [0, 400]])
        pipeline.set_calibration(src_points, dst_points)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/state")
async def get_state(request: Request):
    engine = request.app.state.game_engine
    return engine.get_state()


@router.get("/api/stats")
async def get_stats(request: Request):
    pipeline = request.app.state.pipeline
    return pipeline.fps_counter.get_stats()


# --- WebSocket ---
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    event_manager = websocket.app.state.event_manager
    event_manager.add_client(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming commands from frontend
            import json
            msg = json.loads(data)
            # Future: handle calibration clicks, settings changes, etc.
    except WebSocketDisconnect:
        event_manager.remove_client(websocket)
```

---

## WebSocket Event Protocol (`src/web/events.py`)

### Server → Client Events (JSON)

```json
// Dart detected
{
    "type": "dart_detected",
    "data": {
        "score": 60,
        "sector": 20,
        "multiplier": 3,
        "ring": "triple",
        "position": [205, 180],
        "confidence": 0.85,
        "dart_number": 2
    }
}

// Game state update
{
    "type": "game_state",
    "data": {
        "mode": "x01",
        "current_player": "Player 1",
        "current_player_index": 0,
        "scores": {"Player 1": 441, "Player 2": 501},
        "current_turn": [60],
        "turn_total": 60,
        "darts_thrown": 1,
        "darts_remaining": 2,
        "round": 1,
        "winner": null
    }
}

// Performance stats
{
    "type": "stats",
    "data": {
        "fps_median": 18.5,
        "fps_p95": 12.3,
        "latency_ms": 45,
        "cpu_percent": 42
    }
}

// Calibration status
{
    "type": "calibration",
    "data": {
        "valid": true,
        "method": "manual",
        "last_update": "2026-03-10T21:00:00Z"
    }
}

// Error
{
    "type": "error",
    "data": {
        "message": "Camera disconnected",
        "code": "CAMERA_LOST"
    }
}
```

### Client → Server Events (JSON)

```json
// Manual score correction
{
    "type": "manual_score",
    "data": {
        "score": 20,
        "multiplier": 1
    }
}

// Undo last throw
{
    "type": "undo"
}

// Next player
{
    "type": "next_player"
}

// Remove darts (turn complete)
{
    "type": "remove_darts"
}
```

### EventManager Implementierung
```python
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class EventManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        self._clients: list[WebSocket] = []

    def add_client(self, ws: WebSocket) -> None:
        self._clients.append(ws)
        logger.info("WebSocket client connected (%d total)", len(self._clients))

    def remove_client(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)
        logger.info("WebSocket client disconnected (%d total)", len(self._clients))

    async def broadcast(self, event_type: str, data: dict) -> None:
        message = json.dumps({"type": event_type, "data": data})
        disconnected = []
        for client in self._clients:
            try:
                await client.send_text(message)
            except Exception:
                disconnected.append(client)
        for client in disconnected:
            self.remove_client(client)

    def broadcast_detection(self, score_result: dict) -> None:
        """Sync wrapper for CV pipeline callback."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast("dart_detected", score_result))
        except RuntimeError:
            pass  # No event loop running (e.g., during testing)
```

---

## MJPEG Video Stream (`src/web/stream.py`)

Der Video-Stream nutzt HTTP multipart/x-mixed-replace (MJPEG). Das ist browser-kompatibel, CPU-freundlich und benötigt kein WebSocket.

### Warum MJPEG statt WebSocket-Video?
- Einfacher zu implementieren
- Nativer `<img>` Tag Support in allen Browsern
- Kein Client-seitiger Decoder nötig
- JPEG-Qualität steuerbar (Bandbreite vs. Qualität)

### Einbindung im HTML
```html
<img id="video-stream" src="/video/feed" alt="Live Camera Feed" />
```

---

## Frontend: HTML Template (`templates/index.html`)

### Layout-Struktur
```
┌─────────────────────────────────────────────────────┐
│                    DART-VISION                       │ ← Header
├──────────────────────┬──────────────────────────────┤
│                      │                              │
│   Live Video Feed    │     SVG Dartboard            │
│   (MJPEG Stream)     │     (interaktiv)             │
│                      │                              │
│   [640x480]          │     [400x400]                │
│                      │                              │
├──────────────────────┴──────────────────────────────┤
│                                                     │
│   ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│   │  Player 1   │  │  Player 2   │  │  Player 3 │  │ ← Scoreboard
│   │  Score: 441 │  │  Score: 501 │  │  Score:501│  │
│   │  [current]  │  │             │  │           │  │
│   └─────────────┘  └─────────────┘  └───────────┘  │
│                                                     │
│   Current Turn: T20 (60) + S5 (5) = 65             │ ← Turn Info
│   Darts remaining: 1                                │
│                                                     │
├─────────────────────────────────────────────────────┤
│   [New Game]  [Undo]  [Next Player]  [Remove Darts] │ ← Controls
│   [Calibrate] [Settings]                            │
├─────────────────────────────────────────────────────┤
│   FPS: 18 | Latency: 42ms | CPU: 38%               │ ← Status Bar
└─────────────────────────────────────────────────────┘
```

### Grundgerüst
```html
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dart-Vision</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <header>
        <h1>Dart-Vision</h1>
        <div id="connection-status" class="status-dot"></div>
    </header>

    <main>
        <section class="video-section">
            <div class="video-container">
                <img id="video-stream" src="/video/feed" alt="Live Camera">
                <div id="fps-overlay" class="overlay-text">FPS: --</div>
            </div>
            <div class="dartboard-container" id="dartboard-svg">
                <!-- SVG dartboard rendered by dartboard.js -->
            </div>
        </section>

        <section class="scoreboard-section" id="scoreboard">
            <!-- Dynamically rendered by scoreboard.js -->
        </section>

        <section class="turn-info" id="turn-info">
            <div class="turn-darts" id="turn-darts"></div>
            <div class="turn-total" id="turn-total">Turn: 0</div>
            <div class="darts-remaining" id="darts-remaining">Darts: 3</div>
        </section>

        <section class="controls">
            <button id="btn-new-game" class="btn btn-primary">Neues Spiel</button>
            <button id="btn-undo" class="btn btn-secondary">Rückgängig</button>
            <button id="btn-next-player" class="btn btn-secondary">Nächster Spieler</button>
            <button id="btn-remove-darts" class="btn btn-accent">Darts entfernen</button>
            <button id="btn-calibrate" class="btn btn-outline">Kalibrieren</button>
            <button id="btn-settings" class="btn btn-outline">Einstellungen</button>
        </section>
    </main>

    <footer>
        <span id="stats-fps">FPS: --</span>
        <span id="stats-latency">Latenz: --ms</span>
        <span id="stats-cpu">CPU: --%</span>
    </footer>

    <!-- Modals -->
    <div id="modal-new-game" class="modal hidden">
        <div class="modal-content">
            <h2>Neues Spiel</h2>
            <label>Spielmodus:
                <select id="game-mode">
                    <option value="x01" selected>X01 (301/501/701)</option>
                    <option value="cricket">Cricket</option>
                    <option value="free">Freies Spiel</option>
                </select>
            </label>
            <label>Startwert (X01):
                <select id="starting-score">
                    <option value="301">301</option>
                    <option value="501" selected>501</option>
                    <option value="701">701</option>
                </select>
            </label>
            <div id="players-list">
                <input type="text" class="player-name" value="Spieler 1" />
            </div>
            <button id="btn-add-player" class="btn btn-small">+ Spieler</button>
            <div class="modal-actions">
                <button id="btn-start-game" class="btn btn-primary">Spiel starten</button>
                <button class="btn btn-outline modal-close">Abbrechen</button>
            </div>
        </div>
    </div>

    <div id="modal-calibration" class="modal hidden">
        <div class="modal-content">
            <h2>Board-Kalibrierung</h2>
            <p>Klicke die 4 Ecken des Dartboards im Uhrzeigersinn an (oben-links → oben-rechts → unten-rechts → unten-links).</p>
            <img id="calibration-frame" src="/video/feed" alt="Calibration" style="cursor: crosshair;">
            <div id="calibration-points"></div>
            <div class="modal-actions">
                <button id="btn-apply-calibration" class="btn btn-primary" disabled>Anwenden</button>
                <button id="btn-reset-calibration" class="btn btn-secondary">Zurücksetzen</button>
                <button class="btn btn-outline modal-close">Abbrechen</button>
            </div>
        </div>
    </div>

    <script src="/static/js/websocket.js"></script>
    <script src="/static/js/dartboard.js"></script>
    <script src="/static/js/scoreboard.js"></script>
    <script src="/static/js/app.js"></script>
</body>
</html>
```

---

## Frontend: CSS (`static/css/style.css`)

### Design-Vorgaben
- **Dark Theme** (Hintergrund: `#1a1a2e`, Akzent: `#e94560`)
- **Monospace-Font** für Scores (Roboto Mono oder system monospace)
- **Sans-Serif** für UI-Elemente (Inter oder system sans-serif)
- **Responsive:** Funktioniert auf Laptop + Tablet
- **Hoher Kontrast:** Weiß auf Dunkel für Lesbarkeit aus Entfernung

### Farbpalette
```css
:root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #0f3460;
    --accent: #e94560;
    --accent-hover: #ff6b6b;
    --text-primary: #ffffff;
    --text-secondary: #a0a0b0;
    --text-muted: #606070;
    --success: #00d2ff;
    --warning: #ffa502;
    --error: #ff4757;
    --border: #2a2a4a;
    --font-mono: 'Roboto Mono', 'Courier New', monospace;
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
```

### Wichtige Klassen
```css
body {
    background: var(--bg-primary);
    color: var(--text-primary);
    font-family: var(--font-sans);
    margin: 0;
    min-height: 100vh;
}

/* Scoreboard Karten — groß und gut lesbar */
.player-card {
    background: var(--bg-card);
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
    border: 2px solid var(--border);
    transition: border-color 0.3s;
}

.player-card.active {
    border-color: var(--accent);
    box-shadow: 0 0 20px rgba(233, 69, 96, 0.3);
}

.player-score {
    font-family: var(--font-mono);
    font-size: 3rem;
    font-weight: 700;
    color: var(--text-primary);
}

/* Buttons */
.btn {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary {
    background: var(--accent);
    color: white;
}

.btn-primary:hover {
    background: var(--accent-hover);
}

/* Video Container */
.video-container {
    position: relative;
    border-radius: 12px;
    overflow: hidden;
    border: 2px solid var(--border);
}

.video-container img {
    width: 100%;
    height: auto;
    display: block;
}

/* Status Dot */
.status-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--error);
}

.status-dot.connected {
    background: var(--success);
}
```

---

## Frontend: JavaScript

### `static/js/websocket.js` — WebSocket Client
```javascript
class DartWebSocket {
    constructor(url = `ws://${window.location.host}/ws`) {
        this.url = url;
        this.ws = null;
        this.listeners = {};
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.connect();
    }

    connect() {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            console.log("WebSocket connected");
            this.reconnectDelay = 1000;
            document.getElementById("connection-status")?.classList.add("connected");
            this.emit("connected");
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                this.emit(msg.type, msg.data);
            } catch (e) {
                console.error("WebSocket parse error:", e);
            }
        };

        this.ws.onclose = () => {
            document.getElementById("connection-status")?.classList.remove("connected");
            console.log(`WebSocket closed, reconnecting in ${this.reconnectDelay}ms...`);
            setTimeout(() => this.connect(), this.reconnectDelay);
            this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
        };

        this.ws.onerror = (error) => {
            console.error("WebSocket error:", error);
        };
    }

    on(eventType, callback) {
        if (!this.listeners[eventType]) this.listeners[eventType] = [];
        this.listeners[eventType].push(callback);
    }

    emit(eventType, data = null) {
        (this.listeners[eventType] || []).forEach(cb => cb(data));
    }

    send(type, data = {}) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type, data }));
        }
    }
}
```

### `static/js/dartboard.js` — SVG Dartboard

Erstelle ein interaktives SVG-Dartboard, das:
- Die 20 Sektoren korrekt darstellt (Standard-Dartboard-Layout)
- Erkannte Treffer mit einem roten Punkt markiert
- Beim Klick auf einen Sektor einen manuellen Score-Eintrag ermöglicht

Die SVG-Generierung soll programmatisch erfolgen (nicht als statische Datei), damit die Sektoren korrekt berechnet werden.

```javascript
class DartboardRenderer {
    constructor(containerId, size = 400) {
        this.container = document.getElementById(containerId);
        this.size = size;
        this.center = size / 2;
        this.sectorOrder = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                            3, 19, 7, 16, 8, 11, 14, 9, 12, 5];
        this.markers = [];
        this.render();
    }

    render() {
        // Create SVG programmatically with proper sectors, rings, numbers
        // Colors: black/white for sectors, red/green for double/triple rings
        // Use <path> elements with arc calculations
        // Add sector number labels outside the board
        ...
    }

    addMarker(x, y, score) {
        // Add a red dot at (x, y) with score tooltip
        ...
    }

    clearMarkers() {
        this.markers.forEach(m => m.remove());
        this.markers = [];
    }
}
```

### `static/js/scoreboard.js` — Scoreboard Rendering
```javascript
class Scoreboard {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
    }

    update(gameState) {
        // Render player cards with scores
        // Highlight active player
        // Show turn details (thrown darts, turn total)
        // Show remaining score for X01
        // Show Cricket state (marks per number)
        ...
    }
}
```

### `static/js/app.js` — Main Application
```javascript
document.addEventListener("DOMContentLoaded", () => {
    const ws = new DartWebSocket();
    const scoreboard = new Scoreboard("scoreboard");
    const dartboard = new DartboardRenderer("dartboard-svg");

    // Event Handlers
    ws.on("dart_detected", (data) => {
        // 1. Highlight sector on SVG dartboard
        dartboard.addMarker(data.position[0], data.position[1], data.score);
        // 2. Play sound feedback (optional)
        // 3. Update will come via game_state event
    });

    ws.on("game_state", (data) => {
        scoreboard.update(data);
        updateTurnInfo(data);
    });

    ws.on("stats", (data) => {
        document.getElementById("stats-fps").textContent = `FPS: ${data.fps_median.toFixed(1)}`;
        document.getElementById("stats-latency").textContent = `Latenz: ${data.latency_ms}ms`;
        document.getElementById("stats-cpu").textContent = `CPU: ${data.cpu_percent}%`;
    });

    // Button Handlers
    document.getElementById("btn-new-game").addEventListener("click", () => {
        document.getElementById("modal-new-game").classList.remove("hidden");
    });

    document.getElementById("btn-start-game").addEventListener("click", async () => {
        const mode = document.getElementById("game-mode").value;
        const startingScore = parseInt(document.getElementById("starting-score").value);
        const playerInputs = document.querySelectorAll(".player-name");
        const players = Array.from(playerInputs).map(i => i.value || "Spieler");

        const res = await fetch("/api/game/new", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ mode, players, starting_score: startingScore })
        });
        const state = await res.json();
        scoreboard.update(state);
        dartboard.clearMarkers();
        document.getElementById("modal-new-game").classList.add("hidden");
    });

    document.getElementById("btn-undo").addEventListener("click", async () => {
        const res = await fetch("/api/game/undo", { method: "POST" });
        const state = await res.json();
        scoreboard.update(state);
    });

    document.getElementById("btn-next-player").addEventListener("click", async () => {
        const res = await fetch("/api/game/next-player", { method: "POST" });
        const state = await res.json();
        scoreboard.update(state);
        dartboard.clearMarkers();
    });

    document.getElementById("btn-remove-darts").addEventListener("click", async () => {
        await fetch("/api/game/remove-darts", { method: "POST" });
        dartboard.clearMarkers();
    });

    // Calibration modal
    document.getElementById("btn-calibrate").addEventListener("click", () => {
        document.getElementById("modal-calibration").classList.remove("hidden");
        setupCalibrationUI();
    });

    // Close modals
    document.querySelectorAll(".modal-close").forEach(btn => {
        btn.addEventListener("click", () => {
            btn.closest(".modal").classList.add("hidden");
        });
    });
});

function updateTurnInfo(state) {
    const turnDarts = document.getElementById("turn-darts");
    const turnTotal = document.getElementById("turn-total");
    const dartsRemaining = document.getElementById("darts-remaining");

    turnDarts.innerHTML = state.current_turn
        .map(s => `<span class="dart-score">${s}</span>`)
        .join(" + ");
    turnTotal.textContent = `Turn: ${state.turn_total}`;
    dartsRemaining.textContent = `Darts: ${state.darts_remaining}`;
}

function setupCalibrationUI() {
    const img = document.getElementById("calibration-frame");
    const points = [];
    const pointsDisplay = document.getElementById("calibration-points");
    const applyBtn = document.getElementById("btn-apply-calibration");

    img.onclick = (e) => {
        if (points.length >= 4) return;
        const rect = img.getBoundingClientRect();
        const x = ((e.clientX - rect.left) / rect.width) * img.naturalWidth;
        const y = ((e.clientY - rect.top) / rect.height) * img.naturalHeight;
        points.push([x, y]);
        pointsDisplay.innerHTML = points
            .map((p, i) => `Punkt ${i + 1}: (${p[0].toFixed(0)}, ${p[1].toFixed(0)})`)
            .join("<br>");
        if (points.length === 4) {
            applyBtn.disabled = false;
        }
    };

    applyBtn.onclick = async () => {
        const res = await fetch("/api/calibration/manual", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({ points })
        });
        const result = await res.json();
        if (result.ok) {
            document.getElementById("modal-calibration").classList.add("hidden");
        } else {
            alert("Kalibrierung fehlgeschlagen: " + result.error);
        }
    };

    document.getElementById("btn-reset-calibration").onclick = () => {
        points.length = 0;
        pointsDisplay.innerHTML = "";
        applyBtn.disabled = true;
    };
}
```

---

## Kalibrierungs-UI im Browser

Die Kalibrierung erfolgt visuell:
1. User öffnet Modal → sieht Live-Kamerabild (Einzelframe)
2. User klickt 4 Board-Ecken im Uhrzeigersinn
3. Punkte werden angezeigt und an `/api/calibration/manual` gesendet
4. Backend berechnet Homography und aktualisiert Pipeline

Dies ersetzt die CLI-basierte Kalibrierung für den normalen Betrieb.
