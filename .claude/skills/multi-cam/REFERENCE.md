# Multi-Cam Domain Reference

## Datei-Map

| Datei | Zweck | Coverage | Status |
|-------|-------|----------|--------|
| `src/cv/multi_camera.py` | Multi-Cam-Orchestrierung, Fusion, Triangulation, Fallback | 62% | Sensibel, gehärtet |
| `src/cv/stereo_calibration.py` | Stereo-Paar-Kalibrierung | - | P3 ✅ |
| `src/cv/stereo_utils.py` | Triangulation + Voting-Fallback | - | P3 ✅ validiert |
| `src/web/stereo_progress.py` | Kalibrier-Fortschritt via WebSocket | - | Task-spezifisch |
| `src/utils/triangulation_telemetry.py` | Multi-Cam Metriken | - | Instrumentation |

## Multi-Cam Hauptdatenfluss

```
[Kamera 1] → DartPipeline1 → lokale Detections →┐
[Kamera 2] → DartPipeline2 → lokale Detections →┤→ MultiCameraPipeline
                                                  ├→ Temporal Buffer
                                                  ├→ Triangulation (wenn Stereo-Daten vorhanden)
                                                  └→ Voting-Fallback (wenn Triangulation fehlschlägt)
                                                  ↓
                                           gemeinsamer Treffer-Kandidat
```

## Stereo-Kalibrierung Workflow

1. Intrinsics pro Kamera prüfen (P31 — Pre-Flight-Check)
2. Stereo-Pair Frames aufnehmen
3. `stereo_calibration.py` → `cv2.stereoCalibrate()`
4. Reprojektionsfehler-Quality-Gate: RMS < 1.0px
5. Ergebnis in `config/multi_cam.yaml` speichern

## Konfiguration: multi_cam.yaml

- `last_cameras`: letzte verwendete Kamera-Indizes (schneller Re-Start)
- `stereo_pairs`: Stereo-Kalibrierungsdaten pro Kamera-Paar
- `board_transform`: Board-Pose im World-Koordinatensystem
- `MAX_DETECTION_TIME_DIFF_S`: Sync-Window (default 150ms) — P35: konfigurierbar machen

## Validierte Metriken (P3)

- Triangulations-Genauigkeit: <5mm auf 8 Board-Positionen (synthetisch)
- Z-Depth-Toleranz: 15mm Plausibilitätsfenster
- Reprojektionsfehler-Schwelle: <1px für Quality-Gate

## Wichtige Testdateien

| Datei | Testet |
|-------|--------|
| `tests/test_multi_camera.py` | Multi-Cam-Pipeline-Logik |
| `tests/test_multi_cam_config.py` | Config-Laden, Schema |
| `tests/test_stereo_validation.py` | 27 Triangulations-Tests (P3) |

## Architektur-Entscheidungen

- **ADR-002**: Single-Cam primär, Multi-Cam sekundär — Single-Cam nie für Multi-Cam opfern
- **ADR-003**: Threads mit Stop-Events, kein Process-Pool
- Multi-Cam noch nicht produktionsreif — defensive Changes only
