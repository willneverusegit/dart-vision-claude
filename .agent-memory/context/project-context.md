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

- 512 Tests bestanden
- 76% Gesamt-Coverage
- Single-Cam stabiler Hauptpfad
- Multi-Cam funktional, aber weiterhin Hardening-Fokus
- P19 abgeschlossen: Async-Wartepfade in Web-Routes laufen nicht-blockierend ueber `asyncio.sleep(...)`
- P20 abgeschlossen: Pending-Hits werden serverseitig per TTL/Obergrenze bereinigt und als Stats/Event-Flow exponiert
- P21 abgeschlossen: Kalibrierungslogik ist intern in Board-Workflows, YAML-Store, Konstanten und gemeinsame ChArUco-Observation-Helfer getrennt
- P22 abgeschlossen: Multi-Cam-Fusion puffert kurze Burst-Folgen jetzt pro Kamera in einem Zeitfenster und fusioniert sie in zeitlicher Reihenfolge statt nur ueber den letzten Treffer je Kamera
- P23 abgeschlossen: Runtime-State fuer Pipeline, Thread-Handles und Multi-Frames ist ueber dedizierte State-Helper und deterministischen Lifespan-Reset gekapselt
- P24 abgeschlossen: historisch getrackte Python-Artefakte sind aus dem Git-Tracking entfernt und der Hygiene-Workflow ist dokumentiert
- Weiterer Fokus liegt jetzt eher auf realer E2E-/Hardware-Verifikation als auf den zuletzt identifizierten Struktur-Hardening-Punkten
- Self-improvement-Workflow ist aktiv nutzbar und als atomarer Memory-Sync dokumentiert

## Module-Status

- `main.py`: 78% Coverage, Lifecycle jetzt mit expliziten State-Helpern fuer Runtime-Reset und Thread-Handles
- `routes.py`: 66% Coverage, grosse Sammeldatei mit weiterem Entkopplungsbedarf
- `pipeline.py`: 75% Coverage, stabile Basis
- `multi_camera.py`: Burst-/Timing-Puffer gehaertet; weitere Arbeit liegt eher in Real-World-Tuning als in Buffer-Semantik
- `calibration.py`: deutlich schlankerer Wrapper ueber Board-/Store-/ChArUco-Helfer; weitere Arbeit liegt eher in Real-World-Verifikation als in Datei-Groesse

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

- `app_state` ist fuer Pipeline-Lifecycle und Multi-Frame-Tracking jetzt teilweise gekapselt; Restschuld bleibt die weitere Entkopplung aus `routes.py`/`main.py`

## Offene Fragen

- Wie verhaelt sich E2E-Accuracy auf echten Kamera-Clips ueber verschiedene Lichtbedingungen?
- Welche Burst-/Timing-Regeln sind fuer Multi-Cam-Fusion am robustesten im Realbetrieb?
- Welcher minimale Refactor-Schnitt fuer `calibration.py` erzielt den besten Coverage-Gewinn ohne API-Bruch?
