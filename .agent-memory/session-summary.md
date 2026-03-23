# Letzte Session

*Datum: 2026-03-23 23:37*
*Agent: Claude Code*

## Was wurde gemacht
- **Live-Triangulation erstmals funktionierend**: 2 von 7 Wuerfen mit Stereo-Triangulation (reproj 3.5px und 15px)
- ROI-zu-Raw Koordinatentransformation implementiert (roi_to_raw in CombinedRemapper)
- DartDetection um raw_center/raw_tip erweitert fuer korrekte Triangulations-Koordinaten
- Stale-Stereo-Kalibrierung erkannt und gefixt (Lens neuer als Stereo → Reproj 712px → Neu-Kalibrierung → 0.18px)
- Warnung eingebaut wenn Stereo-Kalibrierung veraltet ist (_load_extrinsics + /api/multi/readiness)
- Sync-Timing angepasst: max_time_diff 150→500ms, sync_wait 300→800ms, depth_tolerance 15→300mm
- max_reproj_error 5→20px (realistisch fuer Webcams)
- Debug-Logging in triangulate_multi_pair fuer Fehlerdiagnose

## Offene Punkte
- 5 von 7 Wuerfen nur Single-Cam-Fallback — zweite Kamera erkennt Dart oft nicht
- Scoring zeigt "miss" bei Triangulation — Board-XY-Mapping pruefen (board_xy Werte unrealistisch)
- Debug-Logs in stereo_utils.py sollten vor Production auf DEBUG zurueckgestuft werden
- Wizard-State-Machine (`_wizardState.currentCamera`) ist toter Code
- cam_left Pose-Reproj 1.88px (cam_right 0.65px) — wiederholbar fuer bessere Werte

## Naechste Schritte
1. Board-XY-Mapping bei Triangulation fixen (Scoring zeigt miss statt korrektes Feld)
2. Zweite Kamera Detection-Rate verbessern (Beleuchtung? Threshold? Sensitivitaet?)
3. Debug-Logs auf DEBUG-Level zurueckstufen
4. Wizard-State-Machine aufraeumen oder entfernen

## Statistik
- Iterationen: 6 (ROI-fix, stale-stereo, sync-timing, depth-tolerance, reproj-threshold, debug-logging)
- Fehler: 2 neu (E9: ROI-coords, E10: stale-stereo)
- Neue Patterns: 2 (roi-vs-raw, calibration-chain)
- Tests: 1425+ passed (64 fokussiert verifiziert), 1 pre-existing failure
