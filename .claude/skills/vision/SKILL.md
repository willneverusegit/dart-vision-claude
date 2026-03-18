---
name: vision
description: Dart-Erkennung, Frame-Diff-Pipeline, Tip-Detection, Kalibrierung, Geometrie — aktivieren wenn an src/cv/ gearbeitet wird
type: domain
---

## Wann nutzen

- Arbeit an Dart-Erkennung, Frame-Diff-Detektor, Tip-Detection
- Kalibrierung (ArUco, Board-Geometrie, Lens-Intrinsics, Homography-Fallback)
- Pipeline-Performance, Threshold-Tuning, Morphologie-Parameter
- ROI-Handling, Remapping, Motion-Detection
- Replay-basierte CV-Tests

## Pflichtlektüre vor Arbeit

1. `agent_docs/current_state.md` — verifizierter Stand (stable vs. sensibel)
2. `agent_docs/pitfalls.md` → Abschnitt "CV / Frame-Diff-Detektor"
3. `agent_docs/priorities.md` → offene CV-Priorities
4. Betroffene Quelldatei lesen **bevor** du änderst

## Schlüsselregeln

1. **update() VOR motion-gate-Early-Return**: `frame_diff_detector.update()` muss aufgerufen werden bevor Motion-Gate rausspringt — SETTLING braucht bewegungsfreie Frames.
2. **settle_frames ≥ 5 bei 30fps**: Zu wenig = Dart wackelt noch → falsche Tip-Position (~167ms Wartezeit).
3. **diff_threshold Startwert 50**: Wert <30 = Beleuchtungsrauschen erzeugt False Positives. Nur bei dunkler Umgebung senken.
4. **Nur Grayscale-Frames** in FrameDiffDetector: Farb-Frame löst `ValueError` aus. Pipeline übergibt bereits CLAHE-enhanced Grayscale.
5. **Baseline nach Homographie-Wechsel zurücksetzen**: `frame_diff_detector.reset()` nach Kalibrierungswechsel. `reset_turn()` deckt das ab wenn `pipeline.refresh_remapper()` danach `reset_turn()` triggert.
6. **Kalibrierungsdateien nie ohne Backup überschreiben** — echte Betriebsdaten.
7. **ADR-001 CPU-only**: Kein CUDA/OpenCL, kein YOLO ohne explizite User-Anfrage.
8. **min_diff_area = 30** (nicht 50): Outer-Bull-Blobs ~40px² werden sonst verworfen.
9. **E2E-Tests**: Pipeline lädt automatisch echte Kalibrierung — für synthetische Tests Remapper und Geometry explizit auf Identity überschreiben nach `pipeline.start()`.
10. **ROI-Zielgröße beibehalten**: Bounded-Queue-Strategie erhalten, keine unkontrollierte Mehrarbeit pro Frame.
11. **Homography-Fallback aktiv (P61)**: Pipeline nutzt `aruco_calibration_with_fallback()` — gecachte Homography bei Marker-Occlusion mit Age-Counter. `homography_age` in Telemetrie-Stats verfügbar.
12. **Ring-Naming inkonsistent (P69)**: `ground_truth.yaml` nutzt `bull_inner`/`bull_outer`, `routes.py` nutzt `inner_bull`/`outer_bull`. Bei E2E-Vergleichen Mapping beachten bis P69 gelöst ist.
13. **Ground-Truth-Validierung**: `scripts/validate_ground_truth.py` prüft YAML-Einträge auf Konsistenz. Vor neuen GT-Annotationen ausführen.

## Architektur-Überblick

```
ThreadedCamera → DartPipeline
  → MotionDetector (MOG2, Trigger)
  → FrameDiffDetector (Before/After-Diff, State-Machine: IDLE/IN_MOTION/SETTLING)
  → DartImpactDetector (Confirmed-Registry, CooldownManager)
  → aruco_calibration_with_fallback() → Homography (gecacht bei Occlusion)
  → BoardGeometry → point_to_score() (mm-basiert, nicht px!)
```

Key Components:
- **CooldownManager**: 50px Spatial Exclusion + 30-Frame Lockout
- **SharpnessTracker**: Laplacian-Varianz + Brightness (EMA) pro Kamera, Wire-Artefakt-Filter, adaptive CLAHE clipLimit
- **LightStabilityMonitor**: automatische Threshold-Erhöhung bei instabilem Licht
- **Adaptive Thresholds**: Otsu-Bias + Search Mode nach 90 Frames Stille

## Offene Todos (aktive P-Items)

| P-Nr | Titel | Status |
|------|-------|--------|
| P37 | Live-Realtest am Board — Parameter tunen | OFFEN — ohne echte Board-Validierung sind Algo-Änderungen blind |
| P11 | E2E Tests mit echten Videoclips | TEILWEISE — GT-Validierung + 32 Tests, Ring-Naming inkonsistent (P69) |
| P24 | Kamera-Vergleich und Kontur-Referenzdaten | OFFEN |
| P27 | Marker-Kalibrierung auf neue Masse | OFFEN |
| P68 | Timestamp-basiertes Detection Matching | OFFEN — GT-Timestamps mit Pipeline-Frames korrelieren |
| P69 | Ring-Naming-Konsistenz (bull_inner vs inner_bull) | OFFEN — GT und Backend nutzen verschiedene Namen |

**Erledigte CV-Items (Kurzreferenz):**
P12 (Area-Range), P19 (Frame-Diff), P20 (Tip-Detection), P21 (Kontur-Robustheit), P25 (Tip vs Centroid), P26 (Schärfemetrik), P38 (3-Stufen-Morphologie), P39 (Video-Replay-Infra verbessert), P40-P43 (Adaptive/Cache/Cooldown/Modular), P47 (Kernel Cache), P49 (Component Tests), P50 (Auto-Exposure), P53 (FrameDiff Integration), P55 (Baseline-Warmup), P57 (Diff-Cache-Bug), P59 (MOG2 Sensitivity), P60 (Homography-Fallback), P61 (Pipeline-Integration), P62 (Homography-Warning UI), P63 (Quick-Wins)

## Risiko-Einschätzung

**MITTEL** für pipeline.py, diff_detector.py, tip_detection.py — Änderungen wirken sich direkt auf Erkennungsrate aus.
**HOCH** für calibration.py, board_calibration.py — Kalibrierungslogik ist Kernfunktion.
Immer: E2E-Replay-Tests laufen lassen nach CV-Änderungen.
