# Architecture

## Laufzeitmodell

Die Anwendung startet ueber `src/main.py`.

Beim App-Start werden aufgebaut:

- `GameEngine`
- `EventManager`
- ein globales `app_state`-Dict
- genau ein Hintergrundpfad fuer:
  - Single-Camera oder
  - Multi-Camera

Das System ist aktuell stark zustandsbehaftet und kombiniert:

- FastAPI-Routen
- Hintergrundthreads fuer CV
- WebSocket-Events fuer das Frontend

## Hauptdatenfluss Single-Camera

1. Kamera liefert Frames
2. Frame wird ggf. remapped
3. ROI wird auf Board-Sicht normalisiert
4. Motion Detection filtert ruhige Frames
5. Dart-Erkennung liefert Trefferkandidaten
6. Geometrie mappt Pixel auf Score
7. Treffer wird als Kandidat ueber WebSocket an UI gesendet
8. Nutzer bestaetigt, verwirft oder korrigiert den Treffer
9. `GameEngine` aktualisiert den Spielstand

## Hauptdatenfluss Multi-Camera

1. pro Kamera eine eigene `DartPipeline`
2. jede Pipeline liefert lokale Erkennungen
3. `MultiCameraPipeline` puffert detections zeitlich
4. bei passender Datenlage:
   - Triangulation oder
   - Voting-Fallback
5. Ergebnis wird als gemeinsamer Trefferkandidat publiziert

## Wichtige Dateien

### Einstieg und App-Lifecycle

- `src/main.py`  
  App-Start, Lifespan, globaler Zustand, Hintergrundthreads.

### Web-Schicht

- `src/web/routes.py`  
  REST-Endpunkte, Kalibrierung, Multi-Cam-Start/Stop, MJPEG-Feeds.

- `src/web/events.py`  
  WebSocket-Verbindungen und thread-sicheres Broadcasting.

- `src/web/stream.py`  
  JPEG-Encoding und MJPEG-Helfer.

### CV-Schicht

- `src/cv/pipeline.py`  
  Single-Camera-Orchestrierung.

- `src/cv/capture.py`  
  Threaded Camera mit bounded queue.

- `src/cv/replay.py`  
  Replay-Quelle fuer deterministische Offline-Tests.

- `src/cv/motion.py`  
  MOG2-basierte Bewegungserkennung.

- `src/cv/detector.py`  
  Formbasierte Dart-Erkennung mit zeitlicher Bestaetigung.

- `src/cv/geometry.py`  
  Mapping von Treffern auf Dart-Score.

- `src/cv/board_calibration.py`  
  Board-spezifische Kalibrierung.

- `src/cv/camera_calibration.py`  
  Lens-/Intrinsics-Kalibrierung.

- `src/cv/remapping.py`  
  Kombination aus Lens- und Board-Remap.

- `src/cv/multi_camera.py`  
  Mehrkamera-Orchestrierung, Fusion, Triangulation, Fallback.

- `src/cv/stereo_calibration.py` und `src/cv/stereo_utils.py`  
  Stereo-Hilfslogik.

### Spiel-Logik

- `src/game/engine.py`
- `src/game/models.py`
- `src/game/modes.py`

### Frontend

- `templates/index.html`
- `static/js/app.js`
- `static/js/dartboard.js`
- `static/js/scoreboard.js`
- `static/js/websocket.js`
- `static/css/style.css`

### Konfiguration

- `config/calibration_config.yaml`
- `config/multi_cam.yaml`

### Tests

- `tests/test_pipeline.py`
- `tests/test_web.py`
- `tests/test_multi_camera.py`
- `tests/test_multi_cam_config.py`
- `tests/test_calibration.py`
- `tests/benchmark_pipeline.py`

## Architektur-Risiken fuer Agents

### 1. `main.py` und `routes.py` sind High-Risk-Dateien

Warum:

- dort treffen Threading, App-Lifecycle, API und Runtime-Zustand zusammen
- kleine Aenderungen koennen Start/Stop oder Eventfluss brechen

### 2. `multi_camera.py` ist funktional wertvoll, aber sensibel

Warum:

- mehrere Threads
- Timing-Fenster
- externe Kalibrierungsdaten
- verschiedene Fallback-Pfade

### 3. `config/*.yaml` sind echte Betriebsdaten

Warum:

- die App liest diese Daten aktiv zur Laufzeit
- Aenderungen an Schluesseln oder Schema muessen kontrolliert erfolgen

## Empfehlung fuer Aenderungen

- Kleine CV-Aenderungen bevorzugt in dedizierten Modulen vornehmen.
- Lifecycle-Aenderungen nur mit Tests und klarer Begruendung.
- UI-Aenderungen in `static/js/app.js` moeglichst lokal kapseln.
- Neue Systeme nicht zuerst in `routes.py` verankern, wenn sie besser als Service oder Helper passen.

