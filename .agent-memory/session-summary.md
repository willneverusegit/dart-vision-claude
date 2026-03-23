# Letzte Session

*Datum: 2026-03-23 21:30*
*Agent: Claude Code*

## Was wurde gemacht
- ChArUco Auto-Capture Bug gefixt: Progress-Endpoint sammelte keine Frames bei capture_mode=auto
- Multi-Cam Kalibrierung end-to-end auf Hardware durchgefuehrt (erstmals!)
- Lens: cam_left RMS 0.230px, cam_right RMS 0.223px (Preset 7x5_40x28)
- Board ArUco: beide Kameras 4/4 Marker, mm_per_px ~2.38
- Stereo-Paar: calibrated=true, quality_level=full
- Calibration Reset Feature gebaut (API + UI)
- Frontend-Design-Verbesserungen (Wizard-Stepper, Status-Dots, Progress-Bar)

## Offene Punkte
- Board-Pose Endpoint fehlt — wird fuer vollstaendige Triangulation benoetigt
- Wizard-State-Machine (`_wizardState.currentCamera`) wird nie aktiviert

## Naechste Schritte
1. Board-Pose Endpoint implementieren fuer Triangulation
2. Wizard-State-Machine reparieren oder entfernen
3. Live-Dart-Erkennung mit kalibriertem Multi-Cam testen

## Statistik
- Iterationen: 2 (bugfix + hardware-test)
- Fehler: 1 (E8: auto-capture)
- Neue Patterns: 0
