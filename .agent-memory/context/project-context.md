# Project Context — DartVision

*Last updated: 2026-03-18 (P29-P32 Multi-Cam implementiert, Diagnostik-Analyse, Tuning-Guide erweitert)*

## Projektziel
Lokales Dart-Scoring-System mit Computer Vision zur automatischen Treffererkennung auf einer Dartscheibe. CPU-only, Windows-Laptop, kein Cloud-Zwang.

## Tech Stack

| Component | Technology | Version | Note |
|-----------|-----------|---------|------|
| Language | Python | 3.14 | |
| Backend | FastAPI | — | REST + WebSocket |
| CV | OpenCV + NumPy | — | CPU-only, keine GPU |
| Frontend | Vanilla JS / HTML / CSS | — | Web Audio API |
| Tests | pytest | — | 620 Tests, ~73% Coverage |
| Config | YAML | — | calibration_config.yaml |

## Architektur

```
ThreadedCamera
    → DartPipeline
        → MotionDetector (MOG2, Trigger)
        → FrameDiffDetector (Before/After-Diff, Positionsbestimmung) [P19]
        → DartImpactDetector (Confirmed-Registry)
        → BoardGeometry → Score
    → WebSocket → Frontend
```

- Single-Camera: stabiler Hauptpfad
- Multi-Camera (Stereo-Triangulation): experimentell, High-Risk
- Game Engine: X01, Cricket, Free Play

## Active Constraints

- CPU-only, keine GPU-Pflicht
- Hardwarelast konservativ halten (Windows i5-Laptop)
- Kalibrierungsdateien nicht leichtfertig aendern
- Multi-Cam ist High-Risk-Bereich — defensive Aenderungen

## Module Status

| Modul | Status | Note |
|-------|--------|------|
| Single-Cam Pipeline | stabil | FrameDiffDetector seit P19 |
| FrameDiffDetector | stabil | Before/After-Diff, P19 |
| Game Engine | stabil | X01, Cricket, Free Play |
| Board-Geometrie | stabil | ArUco 4-stufig, Qualitaetsmetrik |
| Kamera-Reconnect | stabil | Exp. Backoff, Health-API |
| Telemetrie | stabil | FPS, Drops, Queue, RAM, Chart, Alerting |
| Multi-Camera | experimentell | P29-P32 implementiert: Intrinsics-Validation, Triangulation-Telemetry, Camera-Health, Stereo-Progress |
| Tip-Detection | stabil | P20 erledigt — minAreaRect + Kontur-Halbierung, 18/18 validiert |
| Tip vs Centroid Scoring | validiert | P25 — 22 Tests beweisen Tip > Centroid bei Segmentgrenzen |
| Kontur-Robustheit | stabil | P21 — Elongation-Filter (min_elongation=1.5) + Closing |
| Diff-Diagnostics | neu | Speichert Diff-Masken/Konturen bei jedem Treffer (DARTVISION_DIAGNOSTICS_DIR) |
| Live Tuning | stabil | CV-Parameter-API, Frontend-Slider, Diagnostics-Toggle, Tuning-Guide mit Latenz-Kapitel |
| Light Theme | stabil | P23 — Toggle im Header, localStorage, prefers-color-scheme |
| E2E echte Clips | offen | P11 — synthetisch OK, echte Clips fehlen |

## Key Decisions (quick reference)

- **2026-03-17**: Before/After-Frame-Diff als primaerer Detektor statt MOG2-Centroid — Centroid zeigt immer auf Flight, Diff nutzt stabilen Post-Wurf-Frame (→ decisions.json#2026-03-17-frame-diff-over-mog2-centroid)
- **2026-03-17**: MOG2 bei reset_turn() zuruecksetzen — MOG2 adaptiert Dart in Hintergrund, naechster Wurf erzeugt kein Signal mehr (→ decisions.json#2026-03-17-mog2-reset-between-turns)
- **2026-03-17**: Tip-Detection via Kontur-Halbierung statt Centroid — Centroid liegt ~28px daneben, minAreaRect + Breitenvergleich findet Spitze zuverlaessig (→ decisions.json#2026-03-17-tip-detection-narrowing)

## Known Limitations / Tech Debt

- `DartDetection.frame_count` wird im FrameDiffDetector als "settle_frames" (Konfiguration) verwendet, nicht als echte Frame-Zaehlung — wird bei P20 bereinigt
- `DartImpactDetector.detect()` ist im Single-Cam-Pfad seit P19 nicht mehr aktiv (nur noch Multi-Cam und Tests)
- ~~Tip-Detection noch nicht gegen Board-Scoring validiert~~ → P25 erledigt, Tip ist zuverlaessiger

## Open Questions

- ~~Wie verhalten sich diff_threshold=50 und settle_frames=5 am echten Board?~~ → Realtest 17.03: Erkennung funktioniert, aber Latenz zu hoch. motion_threshold ist Flaschenhals.
- Multi-Cam: P29-P32 implementiert, Integration noch nicht live getestet
- Kamera-Qualitaet: ID 0 (schlechte Cam) zeigt Latenz-Probleme — bessere Kamera testen
