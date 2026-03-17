# Session Summary

*Date: 2026-03-17*
*Agent: Claude Sonnet 4.6 (Claude Code)*

## Completed

- P19 implementiert: FrameDiffDetector mit Before/After-Frame-Diff-Ansatz
  - IDLE/IN_MOTION/SETTLING-State-Machine in src/cv/diff_detector.py
  - register_confirmed() public method in DartImpactDetector
  - Integration in DartPipeline (update() vor Motion-Gate, reset_turn() fuer alle Detektoren)
  - 18 neue Tests (512 gesamt)
- Priorities P22/P23 aus Haupt-Repo-Stash aufgeloest und eingetragen
- PROJEKTSTAND_2026-03-17.md erstellt

## Open Items

- P20: Tip-Detection via Convex Hull (Centroid noch als Platzhalter)
- P21: Kontur-Robustheit gegen Schatten/Luecken
- P11: E2E-Tests mit echten Videoclips
- frame_count-Semantik in DartDetection klaeren (wird bei P20 bereinigt)

## Recommended Next Steps

1. P20 — Dart-Tip-Detection: minAreaRect, Extrempunkt entlang Hauptachse
2. P21 — Morphologisches Closing + Elongierungsfilter
3. Realen Testbetrieb mit P19 beobachten, Threshold ggf. anpassen
