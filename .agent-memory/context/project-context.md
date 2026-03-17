# Project Context — DartVision

## Projektziel
Lokales Dart-Scoring-System mit Computer Vision zur automatischen Treffererkennung auf einer Dartscheibe.

## Tech Stack
- **Backend:** Python 3.14, FastAPI, WebSockets
- **CV:** OpenCV, NumPy (CPU-only, keine GPU)
- **Frontend:** Vanilla JS, HTML/CSS, Web Audio API
- **Tests:** pytest
- **Config:** YAML (calibration_config.yaml)

## Architektur
- Single-Camera als stabiler Hauptpfad
- Multi-Camera (Stereo-Triangulation) als experimenteller Pfad
- CV-Pipeline: ArUco-Detektion → Board-Erkennung → Motion Detection → Hit Scoring
- Game Engine: X01, Cricket, Free Play
- WebSocket-basierter Eventfluss (Treffer, Kamerastatus, Telemetrie)

## Constraints
- CPU-only, keine GPU-Pflicht
- Hardwarelast konservativ halten
- Kalibrierungsdateien nicht leichtfertig aendern
- Multi-Cam ist High-Risk-Bereich

## Aktueller Status (2026-03-17)
- P1-P7 und P8, P10, P13-P17 erledigt
- Stabil: Single-Cam, Game Engine, Board-Geometrie, WebSocket-Events, Pipeline-Lifecycle
- Telemetrie, Diagnose-CLI, Windows-Startskript vorhanden
- E2E-Replay-Tests mit synthetischen Clips implementiert

## Offene Fragen
- Echtmaterial-Validierung steht noch aus
- Multi-Cam Robustheit noch nicht produktionsreif
