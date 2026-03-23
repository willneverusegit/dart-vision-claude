# 2026-03-23 Multi-Cam Kalibrierung End-to-End

## Erledigt
- ChArUco Auto-Capture Bug gefixt (Progress-Endpoint sammelte keine Frames)
- Config-Merge-Fix: `_atomic_save()` merged jetzt statt zu ueberschreiben
- Board-Pose Endpoint gefixt (`get_calibration` → `get_config`, try/except)
- Vollstaendige Multi-Cam-Kalibrierung auf Hardware: Lens, Board, Pose, Stereo
- Beide Kameras `ready=true`, `triangulation_possible=true`

## Probleme
- Lens-Intrinsics gingen bei Board-ArUco-Save verloren (Config-Overwrite-Bug)
- Board-Pose 500-Error war schwer zu debuggen (uvicorn zeigte keine Tracebacks)
- cam_right Lens schlug einmal fehl (OpenCV assertion bei zu wenigen guten Frames)

## Gelernt
- Separate CalibrationManager-Instanzen mit eigenen `_config` Dicts ueberschreiben sich gegenseitig beim Speichern — merge statt replace noetig
- Status/Progress-Endpoints brauchen bei Auto-Modi Seiteneffekte (Frame-Sammlung)

## Tests
- 1425 passed, 15 failed (pre-existing), 0 neue Fehler

## CLAUDE.md
- Keine Aenderungen noetig
