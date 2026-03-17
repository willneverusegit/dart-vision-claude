# Project Context - Dart-Vision

## Projektziel

CPU-optimiertes Dart-Scoring-System mit klassischer Computer Vision. Das System soll auf einem Windows-Laptop ohne dedizierte GPU stabil laufen, Treffer als Kandidaten ausgeben und kontrolliert verbuchen.

## Tech Stack

- Backend: Python 3.14, FastAPI, Uvicorn
- CV: OpenCV (opencv-contrib-python), NumPy
- Frontend: Vanilla JS, HTML/CSS, WebSocket + MJPEG
- Tests: pytest, pytest-asyncio, pytest-cov
- Konfiguration: YAML (PyYAML)
- Plattform: Windows 11, CPU-only

## Architektur-Ueberblick

- `src/main.py` - App-Lifecycle, globale Pipeline-Steuerung, Thread-Start/Stop
- `src/web/routes.py` - REST, MJPEG, WebSocket-Endpunkte, Multi-Cam-Steuerung
- `src/cv/pipeline.py` - Single-Camera-CV-Pipeline
- `src/cv/multi_camera.py` - Multi-Cam-Orchestrierung und Fusion
- `src/cv/calibration.py` - Board/Lens-Kalibrierungslogik
- `src/game/engine.py` - Spielregeln und Turn-Flow
- `src/utils/config.py` - YAML-Laden/Speichern plus Schema-Validierung

## Aktueller Stand (2026-03-17)

- 494 Tests bestanden
- 76% Gesamt-Coverage
- Single-Cam stabiler Hauptpfad
- Multi-Cam funktional, aber weiterhin Hardening-Fokus
- Backlog erweitert: neue Prioritaeten P19-P23 fuer Runtime-Haertung und Wartbarkeit
- Self-improvement-Workflow ist aktiv nutzbar und als atomarer Memory-Sync dokumentiert

## Module-Status

- `main.py`: 78% Coverage, Lifecycle mit Thread-Handles und Stop-Events
- `routes.py`: 66% Coverage, grosse Sammeldatei mit weiterem Entkopplungsbedarf
- `pipeline.py`: 75% Coverage, stabile Basis
- `multi_camera.py`: 61% Coverage, Timing/Burst-Faelle priorisiert
- `calibration.py`: 53% Coverage, gezielte Aufteilung und Tests priorisiert

## Aktive Constraints

- CPU-only bleibt verbindlich (kein Deep Learning, kein GPU-Zwang)
- Single-Cam darf durch Multi-Cam-Arbeit nicht regressieren
- Konfig-Dateien sind Betriebsdaten, keine Wegwerfdateien
- Defensives Threading und bounded queues beibehalten
- Kalibrierung ist Kernfunktion, nicht optionales Feature

## Key Decisions

- ADR-001: CPU-only Architektur
- ADR-002: Single-Cam als stabiler Hauptpfad
- ADR-003: ThreadedCamera plus Stop-Events statt Process-Pool
- ADR-004: FastAPI plus Vanilla JS ohne SPA-Framework
- ADR-005: Agent-Selbstverbesserung ueber persistente Doku

## Tech Debt

- Blockierende `_time.sleep(...)`-Wartepfade in async Routen
- Fehlende serverseitige TTL fuer `pending_hits`
- Calibration-Monolith mit relativ schwacher Testabdeckung
- Multi-Cam-Fusionsbuffer aktuell auf "letzten Treffer je Kamera" begrenzt
- `app_state`-Mutation ist verteilt und nur teilweise vertraglich gekapselt

## Offene Fragen

- Wie verhaelt sich E2E-Accuracy auf echten Kamera-Clips ueber verschiedene Lichtbedingungen?
- Welche Burst-/Timing-Regeln sind fuer Multi-Cam-Fusion am robustesten im Realbetrieb?
- Welcher minimale Refactor-Schnitt fuer `calibration.py` erzielt den besten Coverage-Gewinn ohne API-Bruch?
