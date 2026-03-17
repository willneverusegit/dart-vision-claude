# Projektstand Dart-Vision

## Zweck und Grundlage

Dieses Dokument beschreibt den aktuellen Stand des Projekts `dart-vision-claude` zum Stand **2026-03-17**. Die Bewertung basiert auf dem Repository-Inhalt nach Abschluss der Priorisierungsrunde P1–P19.

## Kurzfazit

Der Single-Camera-Betrieb ist stabil, gut getestet und fuer einen CPU-only Laptop der Klasse Intel i5-1035G1 geeignet. Die Treffererkennung wurde in dieser Session grundlegend verbessert: statt MOG2-Centroid (der fast immer aufs Flight zeigt) nutzt die Pipeline jetzt einen Before/After-Frame-Diff — robuster gegen Flight-Artefakte und Schatten-False-Positives.

Multi-Camera ist weiterhin funktional aber sensibel und wird defensiv behandelt.

## Was heute als stabil gilt

- Single-Camera-Startpfad (ThreadedCamera, Pipeline-Lifecycle)
- Game-Engine (X01, Cricket, Free Play) mit Validierung
- WebSocket-Eventfluss und REST-API
- Board-Geometrie und Scoring
- Kalibrierung (ArUco 4-stufig, Qualitaetsmetrik, Intensity-Fallback)
- Kamera-Reconnect mit exponentiellem Backoff
- **Frame-Diff-basierte Treffererkennung** (P19): Before/After-Diff statt MOG2-Centroid
- Hit-Candidate-Review mit Auto-Timeout (30s)
- Telemetrie (FPS, Dropped Frames, Queue-Druck, RAM) — Echtzeit + Chart
- Performance-Alerting (FPS < 15, Queue > 80%)
- Checkout-Vorschlaege (X01, Scores 2–170)
- UI-Responsiveness und Tastaturkuerzel
- Audio-Feedback, Wurf-Badges, Spieler-Glow-Effekt
- Diagnose-CLI (`python -m src.diagnose`) und Windows-Startskript (`start.bat`)
- Idempotentes Logging mit Session-ID und optionalem File-Rotation-Log

## Kenndaten (Stand 2026-03-17)

- **512 Tests bestanden**
- Gesamt-Coverage ~73%
- Wichtige Module: main.py 78%, routes.py 66%, pipeline.py 68%, multi_camera.py 62%, capture.py 72%

## Architektur-Kern

```
ThreadedCamera → DartPipeline → FrameDiffDetector → DartImpactDetector (Registry)
                                     ↓
                              BoardGeometry → Score → WebSocket → Frontend
```

Neu seit 2026-03-17:
- `FrameDiffDetector` (src/cv/diff_detector.py): IDLE/IN_MOTION/SETTLING-State-Machine
- `DartImpactDetector.register_confirmed()`: oeffentliche Schnittstelle fuer externe Detektionen
- `reset_turn()` setzt jetzt alle drei Detektoren zurueck (dart_detector, frame_diff_detector, motion_detector)

## Offene Prioritaeten (Auswahl)

| Prio | Thema | Status |
|------|-------|--------|
| P11 | E2E-Tests mit echten Videoclips | offen |
| P12 | DartImpactDetector Area-Range erweitern | offen |
| P18 | Checkout-Tabelle erweitern + Spielvarianten | offen |
| P20 | Dart-Tip-Detection via Convex Hull | offen — Folge aus P19 |
| P21 | Kontur-Robustheit gegen Schatten und Luecken | offen — Folge aus P19 |
| P22 | Telemetrie-Export und Post-Mortem-Analyse | offen |
| P23 | Dark/Light-Theme und Accessibility | offen |

## Arbeitsannahmen fuer Agents

1. Single-Cam ist der reale Hauptpfad.
2. Multi-Cam ist funktional, braucht defensive Behandlung.
3. Hardware ist begrenzt — CPU-only, konservative Ressourcennutzung.
4. Kalibrierung ist Kernfunktion, nicht Nebenthema.
5. Windows ist die Zielplattform.
6. FrameDiffDetector ersetzt den alten detect()-Pfad im Single-Cam-Betrieb. detect() bleibt fuer Multi-Cam und Tests erhalten.

## Naechste sinnvolle Schritte

1. **P20** — Dart-Tip-Detection: Convex Hull + minAreaRect statt Centroid
2. **P21** — Kontur-Robustheit: Schatten/Luecken-Filterung
3. **P11** — Echte Videoclips aufnehmen und E2E-Tests damit validieren
