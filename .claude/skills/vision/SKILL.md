---
name: vision
description: Dart-Erkennung, Frame-Diff-Pipeline, Tip-Detection, Kalibrierung, Geometrie — aktivieren wenn an src/cv/ gearbeitet wird
type: domain
---

## Wann nutzen

- Arbeit an Dart-Erkennung, Frame-Diff-Detektor, Tip-Detection
- Kalibrierung (ArUco, Board-Geometrie, Lens-Intrinsics)
- Pipeline-Performance, Threshold-Tuning, Morphologie-Parameter
- ROI-Handling, Remapping, Motion-Detection
- Replay-basierte CV-Tests

## Pflichtlektüre vor Arbeit

1. `agent_docs/current_state.md` — verifizierter Stand (stable vs. sensibel)
2. `agent_docs/pitfalls.md` → Abschnitt "CV / Frame-Diff-Detektor"
3. `agent_docs/priorities.md` → offene CV-Priorities (P37, P40-P43, Tier 2)
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

## Offene Todos (aktive P-Items)

| P-Nr | Titel | Status |
|------|-------|--------|
| P37 | Live-Realtest am Board — Parameter tunen | OFFEN — ohne echte Board-Validierung sind weitere Algo-Änderungen blind |
| P40 | Adaptive Thresholds (Otsu-Bias + Search Mode) | OFFEN |
| P41 | Edge Cache (Canny-Reuse pro Frame, ~15-25% CPU-Ersparnis) | OFFEN |
| P42 | Cooldown Management (50px Zone + 30-Frame Lockout) | OFFEN |
| P43 | Modulare Detection Components | OFFEN (Architektur, niedrig prio) |
| P11 | E2E Tests mit echten Videoclips | OFFEN (Ground-Truth-Annotation fehlt) |
| P12 | DartImpactDetector Area-Range erweitern (area_max konfigurierbar) | OFFEN |

**Tier-2 Nächste CV-Optimierungen:**
- HoughLinesP Shaft-Detection (#5) — Autodarts-Ansatz, hoher Impact
- fitLine für Tip-Richtung (#6) — robuster bei unregelmäßigen Konturen
- Temporal Stability Gating (#7) — 3-Frame Positionsbestätigung
- Bounce-Out Detection (#10) — temporal signature
- Contour Shape Confidence Score (#11)

## Risiko-Einschätzung

**MITTEL** für pipeline.py, diff_detector.py, tip_detection.py — Änderungen hier wirken sich direkt auf Erkennungsrate aus.
**HOCH** für calibration.py, board_calibration.py — Kalibrierungslogik ist Kernfunktion.
Immer: E2E-Replay-Tests laufen lassen nach CV-Änderungen.
