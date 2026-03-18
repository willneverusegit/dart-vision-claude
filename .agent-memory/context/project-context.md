# Project Context — DartVision

*Last updated: 2026-03-18 (Auto-Agents Welle 2: P33, P51-Cleanup, P52, P61 erledigt, P62 neu)*

## Projektziel
Lokales Dart-Scoring-System mit Computer Vision zur automatischen Treffererkennung auf einer Dartscheibe. CPU-only, Windows-Laptop, kein Cloud-Zwang.

## Tech Stack

| Component | Technology | Version | Note |
|-----------|-----------|---------|------|
| Language | Python | 3.14 | |
| Backend | FastAPI | — | REST + WebSocket |
| CV | OpenCV + NumPy | — | CPU-only, keine GPU |
| Frontend | Vanilla JS / HTML / CSS | — | Web Audio API |
| Tests | pytest | — | 1102 Tests, ~77% Coverage |
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
| Multi-Camera | experimentell | P44-P45, P56 Error Recovery (Auto-Reconnect, Degradation), P30 Error Reporting |
| Homography-Fallback | stabil | P60+P61 — gecachte Homography bei Marker-Occlusion, in Pipeline integriert, homography_age in Stats |
| CSS Theming | stabil | P46+P52 — alle Farben via CSS-Variablen, 3-Way Toggle (dark/light/high-contrast) |
| Telemetrie-Cleanup | stabil | P48+P51 — Rotation, Age-Cleanup, Background-Scheduler, Status/Rotate API |
| Multi-Cam Governors | in Arbeit | P33 — Sync-Depth-Presets validiert, FPS Governor Implementierung ausstehend |
| Stereo Progress | verbessert | P54 — Fehleranzeige bei nicht erkanntem Board, valid_pairs Tracking |
| Tip-Detection | stabil | P20 erledigt — minAreaRect + Kontur-Halbierung, 18/18 validiert |
| Tip vs Centroid Scoring | validiert | P25 — 22 Tests beweisen Tip > Centroid bei Segmentgrenzen |
| Kontur-Robustheit | stabil | P21+P38 — Elongation-Filter + 3-Stufen-Morphologie (Opening→Closing→Elongated) |
| Sub-Pixel Tip | stabil | P38 — cornerSubPix auf 20x20 ROI, min_diff_area 30 fuer Outer Bull |
| Diff-Diagnostics | neu | Speichert Diff-Masken/Konturen bei jedem Treffer (DARTVISION_DIAGNOSTICS_DIR) |
| Live Tuning | stabil | CV-Parameter-API, Frontend-Slider, Diagnostics-Toggle, Tuning-Guide mit Latenz-Kapitel |
| Light Theme | stabil | P23 — Toggle im Header, localStorage, prefers-color-scheme |
| Video Recording | stabil | P39 — VideoRecorder Klasse, API-Endpoints, UI Rec-Button, CLI-Script |
| Video Replay Tests | stabil | P39 — 8 Testvideos (100mm Marker, 365mm Spacing), E2E-Tests, Batch-Script |
| Configurable Markers | stabil | P39 — marker_size_mm + marker_spacing_mm konfigurierbar (CLI + Config) |
| E2E echte Clips | in Arbeit | P11/P39 — Infra steht, Ground-Truth-Annotation der Videos ausstehend |

## Key Decisions (quick reference)

- **2026-03-17**: Before/After-Frame-Diff als primaerer Detektor statt MOG2-Centroid — Centroid zeigt immer auf Flight, Diff nutzt stabilen Post-Wurf-Frame (→ decisions.json#2026-03-17-frame-diff-over-mog2-centroid)
- **2026-03-17**: MOG2 bei reset_turn() zuruecksetzen — MOG2 adaptiert Dart in Hintergrund, naechster Wurf erzeugt kein Signal mehr (→ decisions.json#2026-03-17-mog2-reset-between-turns)
- **2026-03-17**: Tip-Detection via Kontur-Halbierung statt Centroid — Centroid liegt ~28px daneben, minAreaRect + Breitenvergleich findet Spitze zuverlaessig (→ decisions.json#2026-03-17-tip-detection-narrowing)
- **2026-03-18**: 3-Stufen-Morphologie (Opening→Closing→Elongated) — Board-Draehte filtern + groessere Shaft-Luecken schliessen (→ decisions.json#2026-03-18-three-stage-morphology)
- **2026-03-18**: Sub-Pixel Tip Refinement via cornerSubPix — 0.1-0.5px Genauigkeit an Ring/Sektor-Grenzen (→ decisions.json#2026-03-18-subpixel-tip-refinement)
- **2026-03-18**: Konsolidierter Detection-Optimierungsplan mit 33 Ideen in 5 Tiers in priorities.md
- **2026-03-18**: Configurable ArUco marker_size_mm + marker_spacing_mm — Testvideos nutzen andere Marker (100mm/365mm vs. 75mm/430mm) (→ decisions.json#2026-03-18-configurable-marker-params)
- **2026-03-18**: P39-P43 aus pipeline_patterns.md in Priorities aufgenommen (Video-Testinfra, Adaptive Thresholds, Edge Cache, Cooldown, Modulare Components)
- **2026-03-18**: Webcam-Empfehlung: 2x Logitech C270 fuer Multi-Cam-Setup
- **2026-03-18**: 9-Phasen Multi-Cam-Integrationsplan — Heterogenitaet, Detection Quality, Multi-Pair Triangulation, FPS Governors, Stereo Wizard (→ decisions.json#2026-03-18-multi-cam-9-phase-plan)
- **2026-03-18**: Homography-Fallback bei Marker-Occlusion — gecachte Homography mit Age-Counter statt Kalibrierungsverlust (P60)
- **2026-03-18**: Multi-Cam Error Recovery — Auto-Reconnect mit exp. Backoff + graceful Degradation statt dauerhafter Kamera-Markierung (P56)
- **2026-03-18**: Homography-Fallback in Pipeline integriert — aruco_calibration_with_fallback() aktiv, homography_age in Telemetrie (P61)
- **2026-03-18**: Telemetrie-Cleanup-Scheduler — asyncio Background-Task + Status/Rotate API statt manueller Cleanup-Aufrufe (P51)

## Known Limitations / Tech Debt

- `DartDetection.frame_count` wird im FrameDiffDetector als "settle_frames" (Konfiguration) verwendet, nicht als echte Frame-Zaehlung — wird bei P20 bereinigt
- `DartImpactDetector.detect()` ist im Single-Cam-Pfad seit P19 nicht mehr aktiv (nur noch Multi-Cam und Tests)
- ~~Tip-Detection noch nicht gegen Board-Scoring validiert~~ → P25 erledigt, Tip ist zuverlaessiger

## Open Questions

- ~~Wie verhalten sich diff_threshold=50 und settle_frames=5 am echten Board?~~ → Realtest 17.03: Erkennung funktioniert, aber Latenz zu hoch. motion_threshold ist Flaschenhals.
- Multi-Cam: P29-P32 implementiert, Integration noch nicht live getestet
- Kamera-Qualitaet: ID 0 (schlechte Cam) zeigt Latenz-Probleme — 2x Logitech C270 bestellt/geplant
- Ground-Truth-Annotation der 8 Testvideos noch ausstehend (User annotiert manuell in testvids/ground_truth.yaml)
- Testvideos: Marker-Spacing 365mm muss am Board verifiziert werden (Berechnung: 480mm - 100mm - ~15mm Rand)
