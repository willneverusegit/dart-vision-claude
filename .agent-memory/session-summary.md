# Letzte Session

*Datum: 2026-03-23 22:00*
*Agent: Claude Code*

## Was wurde gemacht
- ChArUco Auto-Capture Bug gefixt (Progress-Endpoint sammelte keine Frames)
- Config-Merge-Bug gefixt (Lens-Intrinsics gingen bei Board-Save verloren)
- Board-Pose Endpoint repariert (get_calibration→get_config, try/except)
- Multi-Cam Kalibrierung end-to-end auf Hardware: Lens, Board, Pose, Stereo
- Beide Kameras ready=true, triangulation_possible=true
- Session-Log, current_state.md und Learnings aktualisiert

## Offene Punkte
- cam_left Pose-Reproj 1.88px (cam_right 0.65px) — wiederholbar fuer bessere Werte
- Wizard-State-Machine (`_wizardState.currentCamera`) ist toter Code

## Naechste Schritte
1. Live-Dart-Erkennung im Multi-Cam-Modus testen (Triangulation)
2. Wizard-State-Machine aufraeumen oder entfernen
3. Frontend: Board-Pose-Button im Kalibrierungsmodal einbauen

## Statistik
- Iterationen: 2 (bugfix + hardware-test) + 2 Fixes (config-merge, board-pose)
- Fehler: 1 neu (E8: auto-capture), 2 Fixes
- Neue Patterns: 0
- Tests: 1425 passed, 15 failed (pre-existing)
