# Project Context — Dart-Vision

## Projektziel

CPU-optimiertes Dart-Scoring-System mit Computer Vision. Erkennt Dart-Wuerfe per Kamera, mappt Treffer auf Dartboard-Segmente, fuehrt Spielstand in Echtzeit.

## Tech Stack

- **Backend:** Python 3.14, FastAPI, Uvicorn
- **CV:** OpenCV (opencv-contrib-python), NumPy
- **Frontend:** Vanilla JS, HTML/CSS, WebSocket + MJPEG
- **Tests:** pytest, pytest-asyncio, pytest-cov
- **Config:** YAML (PyYAML)
- **Plattform:** Windows 11, CPU-only (kein GPU)

## Architektur

- `src/main.py` — App-Start, Lifespan, globaler Zustand
- `src/web/routes.py` — REST + WebSocket + MJPEG
- `src/cv/pipeline.py` — Single-Camera-Orchestrierung
- `src/cv/multi_camera.py` — Multi-Cam-Pipeline
- `src/cv/detector.py` — Dart-Impact-Erkennung (Shape + temporal confirmation)
- `src/cv/calibration.py` — ArUco/ChArUco Board-Kalibrierung
- `src/game/engine.py` — Spiellogik (X01, Cricket, Free Play)
- `src/utils/config.py` — YAML-Config-Management mit Schema-Validierung

## Aktueller Stand (2026-03-17)

- 483 Tests, ~72% Coverage
- Single-Cam stabil, Multi-Cam funktional aber sensibel
- P1-P6, P13-P17 erledigt (Input-Validierung, CV-Validierung, Frontend-Fehlerbehandlung, Config-Schema)
- P7-P12 offen (UX, Performance-Monitoring, Multi-Cam UX, UI-Design, E2E mit echten Clips, Detector Area-Range)

## Constraints

- CPU-only Laptop als Zielplattform
- Kein Deep Learning, keine GPU-Pflicht
- Single-Cam ist Hauptpfad, Multi-Cam High-Risk
- Config-Dateien sind reale Betriebsdaten
- Hit-Candidate-Review-Flow (kein Auto-Scoring)

## Offene Fragen

- Wie robust ist die Erkennung bei realer Beleuchtung? (P11: echte Videoclips fehlen)
- Outer-Bull-Erkennung zu schwach (P12: area_min Problem)
- Multi-Cam UX fuer Nicht-Experten noch nicht bedienbar (P9)
