# Session 2026-03-18: Multi-Cam Integration Plan

## Erledigt
- Umfassenden 9-Phasen-Plan fuer Multi-Cam-Integration erstellt
- Codebase-Recherche: multi_camera.py, stereo_utils.py, pipeline.py, calibration.py, hardware_constraints
- Plan deckt ab: Kamera-Heterogenitaet, Detection Quality, Multi-Pair Triangulation, FPS Governors, Stereo Wizard
- Mapping auf existierende Prioritaeten P29-P36

## Probleme
- Keine Code-Aenderungen in dieser Session (reine Planungs-Session)
- E2E-Replay-Tests weiterhin failing (cv2.aruco Kompatibilitaet)

## Gelernt
- Homography absorbiert Aufloesungsunterschiede automatisch — kein Normalisierungs-Layer noetig
- 2-Tier Sync-Logik (sync_wait vs max_time_diff) verhindert unnoetige Single-Fallbacks
- Viewing-Angle-Quality aus Homography-Determinante ableitbar

## CLAUDE.md-Anpassungen
- Keine Aenderungen noetig
