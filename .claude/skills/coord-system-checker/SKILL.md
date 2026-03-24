---
name: coord-system-checker
description: Prueft Detection-Code auf korrekte Verwendung von Koordinatensystemen (ROI-Raum vs Raw-Kamera-Raum). Verhindert Verwechslungen bei center/tip vs raw_center/raw_tip. Aktivieren bei Arbeit an Detection, Triangulation oder Multi-Cam Code.
user-invocable: true
---

# Coordinate System Checker

Dart-Vision hat zwei Koordinatensysteme:

| Feld | Raum | Beschreibung |
|------|------|-------------|
| `center`, `tip` | ROI-Raum | Nach Combined Remap (Homography-Warp), 400x400 Board-Space |
| `raw_center`, `raw_tip` | Kamera-Frame-Raum | Original-Pixel-Koordinaten, passend zu Lens-Intrinsics |

## Regeln

1. **Triangulation** MUSS `raw_center`/`raw_tip` verwenden (Stereo-Kalibrierung nutzt Raw-Frame-Intrinsics)
2. **Board-Scoring** (wo hat der Dart getroffen) nutzt `center`/`tip` (ROI = Board-Space)
3. **Visualisierung im Raw-Frame** muss `raw_center`/`raw_tip` verwenden
4. **Visualisierung im ROI-Overlay** nutzt `center`/`tip`

## Pruef-Workflow

### 1. Dateien scannen

Suche in geaenderten Dateien nach:

```
grep -n "\.center\|\.tip\|\.raw_center\|\.raw_tip\|triangulat\|undistort\|project_points" <files>
```

### 2. Kontext-Analyse

Fuer jede Fundstelle pruefen:

- **In Triangulation-Code** (`triangulate_point`, `stereo_`, `multi_camera`):
  → Muss `raw_center`/`raw_tip` sein. Wenn `center`/`tip` → **FEHLER**

- **In Score/Board-Berechnung** (`score`, `segment`, `sector`, `board_position`):
  → Sollte `center`/`tip` sein (ROI-Raum = Board-Raum)

- **In Pipeline-Code** (`pipeline.py`, `detection`):
  → `raw_center`/`raw_tip` muessen NACH Detection gesetzt werden via `roi_to_raw()`

- **In `CombinedRemapper`**:
  → `roi_to_raw()` muss inverse Homography + Re-Distortion ausfuehren

### 3. Output

```
COORDINATE SYSTEM CHECK
=======================
src/cv/multi_camera.py:142  triangulate_point(det.raw_tip)  ✅ Raw-Raum
src/cv/pipeline.py:89       score = calc_score(det.center)  ✅ ROI-Raum
src/cv/pipeline.py:95       det.raw_center = roi_to_raw()   ✅ Konvertierung

KEINE Koordinaten-Verwechslungen gefunden.
```

Oder bei Fehler:
```
⚠️ src/cv/multi_camera.py:142  triangulate_point(det.center)
   FEHLER: Triangulation nutzt ROI-Koordinaten statt raw_center!
   Fix: det.center → det.raw_center
```
