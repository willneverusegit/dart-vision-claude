# Session 2026-03-18: Depth Auto-Adapt + Wizard UI

## Erledigt
- Depth auto-adapt nach Multi-Pair Rewrite re-integriert (stereo_utils + multi_camera)
- triangulate_multi_pair gibt jetzt Z-Rejection-Info zurueck statt None
- Frontend: Calibration-Details (Blickwinkel-Qualitaet, Intrinsics-Warnungen) in Setup-Checklist
- Monkeypatch-Target in test_multi_robustness.py korrigiert (stereo_utils statt multi_camera)

## Probleme
- Keine neuen Probleme. 6 pre-existing e2e Failures (cv2.aruco compat)

## Gelernt
- triangulate_multi_pair muss Fehlergrund zurueckgeben, nicht nur None — Caller braucht Z-Rejection-Info

## CLAUDE.md-Anpassungen
- Keine noetig
