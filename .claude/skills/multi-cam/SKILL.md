---
name: multi-cam
description: Stereo-Triangulation, Multi-Cam-Fusion, Stereo-Kalibrierung — aktivieren wenn an src/cv/multi_camera.py oder stereo_* gearbeitet wird
type: domain
---

## Wann nutzen

- Änderungen an multi_camera.py (Fusion, Triangulation, Fallback-Logik)
- Stereo-Kalibrierung (stereo_calibration.py, stereo_utils.py)
- Multi-Cam-Threading und Buffer-Management
- Kamera-Switching Single↔Multi
- Multi-Cam-Readiness-Diagnose
- Error Recovery und Reconnect (P56)
- Stereo-Kalibrierung Fortschritt und UX (P54)

## Pflichtlektüre vor Arbeit

1. `agent_docs/current_state.md` → Abschnitt "fortgeschritten, aber noch sensibel"
2. `MULTI_CAM_INSTRUCTIONS.md` — Deep-Dive Multi-Cam
3. `MULTI_CAM_WORKFLOW.md` — Entwicklungsworkflow
4. `agent_docs/pitfalls.md` → Abschnitt "Threading & Lifecycle"
5. `agent_docs/priorities.md` → P29-P36, P44-P45, P50, P54, P56 (Multi-Cam-Prioritäten)

## Schlüsselregeln

1. **Single-Cam-Pfad nie verschlechtern** (ADR-002): Änderungen an Multi-Cam dürfen Single-Cam-Performance/-Stabilität nie berühren.
2. **HIGH-RISK**: multi_camera.py hat mehrere Threads, Timing-Fenster, externe Kalibrierungsdaten und verschiedene Fallback-Pfade.
3. **Single↔Multi-Wechsel**: Alten Pipeline-Thread sauber stoppen (Signal + Join) bevor neuer gestartet wird.
4. **multi_cam.yaml speichert last_cameras** — beim Testen nicht mit Dummy-Werten überschreiben.
5. **Multi-Cam-Tests sind fragiler**: Immer separat laufen lassen (`python -m pytest tests/test_multi_camera.py`).
6. **Stereo-Kalibrierung ist Betriebsdaten** — `config/multi_cam.yaml` nie ohne Backup ändern.
7. **Triangulations-Toleranz**: Z-Depth-Plausibilität 15mm (konfigurierbar über P35), Reprojektionsfehler-Schwelle <1px.
8. **Voting-Fallback**: Wenn Triangulation fehlschlägt → Voting-Fallback aktivieren, kein Silent-Fail.
9. **P29-P36 vor neuen Features**: Grundlegende Multi-Cam-Probleme (Wizard, Error-Reporting, Intrinsics-Validation) vor weiteren Features angehen.

## Erledigte Multi-Cam P-Items

P30 (Error Reporting), P31 (Intrinsics Validation), P32 (Triangulation Telemetrie), P35 (Sync-Window), P44-P45 (Camera Profiles, Multi-Pair Triangulation), P54 (Stereo Progress Feedback), P56 (Error Recovery + Auto-Reconnect)

## Offene Todos (aktive P-Items)

| P-Nr | Titel | Kritikalität |
|------|-------|-------------|
| P29 | Stereo Calibration UI Wizard | KRITISCH |
| P33 | Multi-Cam FPS/Buffer Governors (i5-Laptop CPU-Schutz) | HOCH |
| P34 | 3+ Camera Fusion | HOCH |
| P36 | Multi-Cam Hardware E2E Test | MITTEL |
| P50 | Auto-Exposure-Kompensation pro Kamera | MITTEL |
| P9 | Multi-Cam UX Verbesserungen | NIEDRIG |

## Neue Features seit letztem Update

- **Error Recovery (P56)**: Auto-Reconnect nach 50 Frame-Fehlern, exp. Backoff (2-30s), graceful Degradation, API: `POST /api/multi/camera/{id}/reconnect`, `GET /api/multi/degraded`
- **Stereo Progress (P54)**: `frame_progress()` liefert `both_detected`, `valid_pairs`, deutsche Fehlermeldungen, Frontend-Fehleranzeige

## Risiko-Einschätzung

**SEHR HOCH** — Threading, externe Kalibrierungsdaten, Timing-Fenster und Fallback-Pfade zusammen.
Immer: `python -m pytest tests/test_multi_camera.py tests/test_multi_cam_config.py` laufen lassen.
Defensive Changes only — jeden neuen Code mit Tests absichern.
