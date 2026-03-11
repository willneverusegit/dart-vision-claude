# Kalibrierung: Workflow, Methoden, Config-Schema

> Lies dieses Dokument, wenn du an `src/cv/calibration.py` arbeitest.

---

## Übersicht

Die Kalibrierung verbindet die Pixelwelt des Kamerabildes mit der physikalischen Welt des Dartboards. Ohne korrekte Kalibrierung ist kein präzises Scoring möglich.

### Zwei Methoden

| Methode | Genauigkeit | Setup-Aufwand | Empfehlung |
|---------|------------|---------------|------------|
| **Manuelle 4-Punkt** | 2–5 mm | Niedrig (4 Klicks) | MVP, immer verfügbar |
| **ChArUco Board** | 0.5–2 mm | Hoch (Board drucken) | Optional, Phase 2+ |

---

## CalibrationManager (`src/cv/calibration.py`)

### Interface
```python
class CalibrationManager:
    """Manages board calibration: manual 4-point and optional ChArUco."""

    def __init__(self, config_path: str = "config/calibration_config.yaml") -> None:
        ...

    def manual_calibration(self, board_points: list[list[float]],
                           roi_size: tuple[int, int] = (400, 400)) -> dict:
        """
        Perform manual 4-point calibration.

        Args:
            board_points: 4 corner points [[x1,y1], ...] in clockwise order
                          (top-left, top-right, bottom-right, bottom-left)
            roi_size: Target ROI dimensions

        Returns:
            {"ok": True, "homography": list, "mm_per_px": float}
            or {"ok": False, "error": str}
        """
        ...

    def charuco_calibration(self, frames: list[np.ndarray]) -> dict:
        """
        ChArUco-based calibration from multiple frames.

        Args:
            frames: List of frames containing ChArUco board views

        Returns:
            {"ok": True, "homography": list, "mm_per_px": float, "reprojection_error": float}
            or {"ok": False, "error": str}
        """
        ...

    def get_homography(self) -> np.ndarray | None:
        """Get current homography matrix, or None if not calibrated."""
        ...

    def get_config(self) -> dict:
        """Get current calibration config."""
        ...

    def is_valid(self) -> bool:
        """Check if calibration is valid."""
        ...
```

### Implementierung — Manuelle Kalibrierung
```python
import cv2
import numpy as np
import yaml
import os
import tempfile
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

BOARD_DIAMETER_MM = 340  # Standard dartboard playing area


class CalibrationManager:
    def __init__(self, config_path: str = "config/calibration_config.yaml") -> None:
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> dict:
        default = {
            "center_px": [200, 200],
            "radii_px": [10, 19, 106, 116, 188, 200],
            "rotation_deg": 0.0,
            "mm_per_px": 1.0,
            "homography": np.eye(3).tolist(),
            "last_update_utc": None,
            "valid": False,
            "method": None,
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    loaded = yaml.safe_load(f)
                if loaded:
                    default.update(loaded)
            except Exception as e:
                logger.error("Config load error: %s", e)
        return default

    def manual_calibration(self, board_points: list[list[float]],
                           roi_size: tuple[int, int] = (400, 400)) -> dict:
        try:
            src = np.float32(board_points)
            dst = np.float32([
                [0, 0],
                [roi_size[0], 0],
                [roi_size[0], roi_size[1]],
                [0, roi_size[1]]
            ])

            homography = cv2.getPerspectiveTransform(src, dst)

            # Estimate scale
            board_width_px = np.linalg.norm(src[1] - src[0])
            mm_per_px = BOARD_DIAMETER_MM / board_width_px

            # Estimate center
            center_x = (src[0][0] + src[2][0]) / 2
            center_y = (src[0][1] + src[2][1]) / 2

            self._config.update({
                "center_px": [float(center_x), float(center_y)],
                "mm_per_px": float(mm_per_px),
                "homography": homography.tolist(),
                "last_update_utc": datetime.now(timezone.utc).isoformat(),
                "valid": True,
                "method": "manual",
            })

            self._atomic_save()
            logger.info("Manual calibration complete (mm/px=%.3f)", mm_per_px)
            return {"ok": True, "homography": homography.tolist(), "mm_per_px": mm_per_px}

        except Exception as e:
            logger.error("Manual calibration failed: %s", e)
            return {"ok": False, "error": str(e)}

    def _atomic_save(self) -> None:
        """Atomic config write: temp file → os.replace()."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        fd, temp_path = tempfile.mkstemp(suffix=".yaml", dir=os.path.dirname(self.config_path))
        try:
            with os.fdopen(fd, "w") as f:
                yaml.dump(self._config, f, default_flow_style=False)
            os.replace(temp_path, self.config_path)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def get_homography(self) -> np.ndarray | None:
        if self._config["valid"]:
            return np.array(self._config["homography"], dtype=np.float64)
        return None

    def get_config(self) -> dict:
        return dict(self._config)

    def is_valid(self) -> bool:
        return self._config.get("valid", False)
```

---

## Config-Schema (`config/calibration_config.yaml`)

```yaml
# Auto-generated by CalibrationManager. Do not edit manually.
center_px: [320.5, 240.3]
radii_px: [10, 19, 106, 116, 188, 200]
rotation_deg: 0.0
mm_per_px: 0.85
homography:
  - [1.234, 0.012, -45.6]
  - [0.023, 1.198, -32.1]
  - [0.00001, 0.00002, 1.0]
last_update_utc: "2026-03-10T21:00:00+00:00"
valid: true
method: manual
```

### Felder

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `center_px` | [float, float] | Board-Zentrum in Pixeln |
| `radii_px` | [float, ...] | Ring-Radien in Pixeln (inner bull → double outer) |
| `rotation_deg` | float | Board-Rotation in Grad |
| `mm_per_px` | float | Skalierungsfaktor: mm pro Pixel |
| `homography` | [[float,...], ...] | 3×3 Perspektiv-Transformationsmatrix |
| `last_update_utc` | str (ISO 8601) | Zeitstempel der letzten Kalibrierung |
| `valid` | bool | Ob die Kalibrierung gültig ist |
| `method` | str | "manual" oder "charuco" |

---

## Kalibrierungs-Workflow (User-Perspektive)

### Manuelle 4-Punkt-Kalibrierung
1. User klickt "Kalibrieren" im Web-Frontend
2. Modal öffnet sich mit Live-Kamerabild (Einzelframe)
3. User klickt 4 Board-Ecken im Uhrzeigersinn:
   - Oben-Links (Outer Double Wire)
   - Oben-Rechts
   - Unten-Rechts
   - Unten-Links
4. System berechnet Homography und aktualisiert Pipeline
5. Config wird atomar gespeichert
6. Pipeline nutzt ab sofort die neue Kalibrierung

### CLI-Modus (Alternative)
```bash
python -m src.cv.calibration --mode manual --source 0
```
Öffnet OpenCV-Fenster, User klickt 4 Punkte, Enter bestätigt.

---

## Atomic Write Pattern

Um Datenkorruption bei Stromausfällen oder Crashes zu verhindern:

```
1. Neue Daten → temporäre Datei schreiben (tempfile.mkstemp)
2. os.replace(temp_path, config_path)  ← atomare Operation (POSIX)
3. Falls Fehler: temp-file löschen, alter Config bleibt intakt
```

Dies garantiert, dass die Config-Datei immer in einem konsistenten Zustand ist.

---

## ChArUco-Kalibrierung (Phase 2 — Optional)

Nur implementieren, wenn die manuelle Kalibrierung stabil funktioniert.

### Voraussetzungen
- Gedrucktes ChArUco-Board (7×5 Squares, 40mm/20mm)
- `cv2.aruco.DICT_6X6_250`

### Ablauf
1. Mehrere Frames mit ChArUco-Board im Sichtfeld sammeln
2. ArUco-Marker detektieren
3. ChArUco-Ecken interpolieren
4. Kamera-Kalibrierung durchführen
5. Homography für Board-Entzerrung ableiten

### Hinweis zur OpenCV-API
Die ArUco-API hat sich in OpenCV 4.7+ geändert:
```python
# Neu (4.7+):
dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
board = cv2.aruco.CharucoBoard((7, 5), 0.04, 0.02, dictionary)
detector = cv2.aruco.ArucoDetector(dictionary)

# Alt (4.6-):
dictionary = cv2.aruco.Dictionary_get(cv2.aruco.DICT_6X6_250)
board = cv2.aruco.CharucoBoard_create(7, 5, 0.04, 0.02, dictionary)
```

Verwende die neue API (4.7+). Prüfe die installierte OpenCV-Version.
