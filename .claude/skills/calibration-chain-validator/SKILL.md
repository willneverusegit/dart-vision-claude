---
name: calibration-chain-validator
description: Validiert die Kalibrierungs-Kette (Lens → Board Pose → Stereo) auf Timestamp-Konsistenz. Warnt wenn nachgelagerte Kalibrierungen aelter sind als vorgelagerte. Aktivieren bei Arbeit an Kalibrierungscode oder vor Commits.
user-invocable: true
---

# Calibration Chain Validator

Pruefe die Kalibrierungs-Kette auf Konsistenz. Jeder Schritt invalidiert alle nachfolgenden:

**Lens-Kalibrierung → Board Pose → Stereo-Kalibrierung**

## Validierungs-Schritte

### 1. Timestamps extrahieren

Lies `config/calibration_config.yaml` und `config/multi_cam.yaml`:

- **Lens**: `cameras.<cam>.lens_last_update_utc` aus `calibration_config.yaml`
- **Board Pose**: `cameras.<cam>.last_update_utc` aus `calibration_config.yaml` (Homography-Update)
- **Stereo**: `pairs.<pair>.calibrated_utc` aus `multi_cam.yaml`

### 2. Ketten-Validierung pro Kamera

Fuer jede Kamera pruefen:

```
lens_timestamp <= board_pose_timestamp <= stereo_timestamp
```

**Violations:**
- Lens neuer als Board Pose → Board Pose ist STALE (neue Intrinsics, alte Homography)
- Lens neuer als Stereo → Stereo ist STALE (neue Intrinsics, alte Extrinsics)
- Board Pose neuer als Stereo → Stereo nutzt moeglicherweise veraltete Pose-Daten

### 3. Zusaetz-Checks

- `lens_valid: true` muss gesetzt sein
- `reprojection_error` sollte < 1.0 sein (Lens) und < 5.0 (Stereo)
- `quality_level: provisional` in Stereo warnen

### 4. Output-Format

```
CALIBRATION CHAIN STATUS
========================
cam_left:
  Lens:       2026-03-23T20:48  (reproj: 0.23) ✅
  Board Pose: 2026-03-23T21:35  ✅ (nach Lens)
  Stereo:     2026-03-23T22:12  ✅ (nach Lens)

cam_right:
  Lens:       2026-03-23T20:53  (reproj: 0.xx) ✅
  Board Pose: —                  ⚠️ nicht vorhanden
  Stereo:     2026-03-23T22:12  ✅ (nach Lens)

Chain: ✅ VALID / ⚠️ STALE (Stereo aelter als Lens fuer cam_left)
```

### 5. Bei STALE-Ergebnis

Empfehlung ausgeben welcher Schritt wiederholt werden muss:
- "Board Pose neu kalibrieren (Lens wurde am X aktualisiert)"
- "Stereo-Kalibrierung wiederholen (Lens/Board Pose wurde am X aktualisiert)"
