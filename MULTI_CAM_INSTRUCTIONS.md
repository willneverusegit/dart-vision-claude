# Multi-Kamera Implementierung — Claude Code Arbeitsanweisungen

> **Kontext:** Diese Datei enthält 5 sequenzielle Arbeitsaufträge (Steps 2–6) für die
> Multi-Kamera-Erweiterung des dart-vision-Projekts. Jeder Step ist in sich
> abgeschlossen und baut auf dem vorigen auf. Führe sie **einzeln und in Reihenfolge** aus.
>
> **Sprach-Konvention:** Erklärungen auf Deutsch, Code/Kommentare/Variablennamen auf Englisch.
>
> **Qualitätskriterien:** Jeder Step muss `pytest` mit 0 Failures durchlaufen.
> Bestehende Tests dürfen nicht brechen. Neue Module brauchen eigene Tests.

---

## Vorab-Annahmen (gilt für alle Steps)

```
Assumptions:
- Python 3.11+, OpenCV 4.8+ (opencv-contrib-python), NumPy, PyYAML vorhanden
- Einzelkamera-Betrieb muss nach jedem Step weiterhin funktionieren (Abwärtskompatibilität)
- Kein Deep Learning, nur klassische CV (projektweite Constraint)
- CPU-only, kein GPU
- ArUco-Dictionary: DICT_4X4_50 für Board-Marker, DICT_6X6_250 für ChArUco-Boards (Stereo)
- camera_id="default" ist der implizite Schlüssel für Einzelkamera-Setups
```

---

## Step 2: Konfigurations-Refactoring

### Ziel
Kalibrierungsdaten pro Kamera speicherbar machen. Neue YAML-Datei für extrinsische
Parameter (Stereo-Paare). Bestehende Single-Camera-Config bleibt funktionsfähig.

### 2.1 — `CalibrationManager` um `camera_id` erweitern

**Datei:** `src/cv/calibration.py`

Ändere den Konstruktor von `CalibrationManager`:

```python
def __init__(self, config_path: str = "config/calibration_config.yaml",
             camera_id: str = "default") -> None:
```

**Interne Logik:**
- Beim Laden (`_load_config`): Prüfe ob Top-Level-Key `cameras` existiert.
  - Ja → lade `config["cameras"][camera_id]` als Working-Config.
  - Nein → Legacy-Format, lade flach (Abwärtskompatibilität). Beim nächsten Speichern
    migriere automatisch unter `cameras.default`.
- Beim Speichern (`_atomic_save`): Schreibe immer im neuen Format:
  ```yaml
  schema_version: 3
  cameras:
    default:
      center_px: [275.5, 245.35]
      homography: [...]
      # ... alle bisherigen Felder
    cam_left:
      center_px: [...]
      # ...
  ```
- Die öffentlichen Getter (`get_homography()`, `get_config()`, etc.) arbeiten
  weiterhin auf der Working-Config der aktuellen `camera_id`.

**Migration-Logik (Pseudocode):**
```python
def _load_config(self) -> dict:
    raw = yaml.safe_load(file) or {}
    if "cameras" in raw and self.camera_id in raw["cameras"]:
        return raw["cameras"][self.camera_id]
    elif "cameras" not in raw and raw.get("valid"):
        # Legacy flat format → treat as "default"
        return raw
    else:
        return DEFAULT_CONFIG

def _atomic_save(self) -> None:
    # Load full file, update our camera_id section, write back
    full = yaml.safe_load(file) or {}
    if "cameras" not in full:
        # Migrate: move existing flat config into cameras.default
        full = {"schema_version": 3, "cameras": {"default": full}}
    full["cameras"][self.camera_id] = self._config
    full["schema_version"] = 3
    # atomic write full dict
```

**Kritisch:** `_atomic_save` muss die **gesamte** Datei lesen, den eigenen Abschnitt
updaten und dann die gesamte Datei zurückschreiben. Race Conditions bei gleichzeitigem
Zugriff mehrerer Kameras → File-Lock (z.B. `threading.Lock` auf Modulebene) einbauen.

### 2.2 — `BoardCalibrationManager` und `CameraCalibrationManager` anpassen

**Dateien:** `src/cv/board_calibration.py`, `src/cv/camera_calibration.py`

Beide Klassen reichen `camera_id` an ihren internen `CalibrationManager` durch:

```python
class BoardCalibrationManager:
    def __init__(self, config_path: str = "config/calibration_config.yaml",
                 roi_size: tuple[int, int] = (400, 400),
                 camera_id: str = "default") -> None:
        self._legacy = CalibrationManager(config_path=config_path, camera_id=camera_id)
        # ... rest unchanged
```

Analog für `CameraCalibrationManager`.

### 2.3 — `config/multi_cam.yaml` und Hilfsmodul

**Neue Datei:** `config/multi_cam.yaml` (initial leer oder mit Beispielstruktur):

```yaml
# Extrinsic stereo calibration parameters per camera pair
schema_version: 1
pairs: {}
#   cam_left--cam_right:
#     R: [[...], [...], [...]]
#     T: [...]
#     reprojection_error: 0.0
#     calibrated_utc: "2026-01-01T00:00:00+00:00"
```

**Datei erweitern:** `src/utils/config.py`

Füge hinzu:

```python
MULTI_CAM_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "multi_cam.yaml"
)

def load_multi_cam_config(path: str = MULTI_CAM_CONFIG_PATH) -> dict:
    """Load multi-camera extrinsic parameters."""
    return load_config(path)

def save_multi_cam_config(data: dict, path: str = MULTI_CAM_CONFIG_PATH) -> None:
    """Atomically save multi-camera extrinsic parameters."""
    save_config(data, path)

def get_stereo_pair(cam_a: str, cam_b: str,
                    path: str = MULTI_CAM_CONFIG_PATH) -> dict | None:
    """Load extrinsics for a specific camera pair. Order-independent key lookup."""
    cfg = load_multi_cam_config(path)
    pairs = cfg.get("pairs", {})
    key_ab = f"{cam_a}--{cam_b}"
    key_ba = f"{cam_b}--{cam_a}"
    return pairs.get(key_ab) or pairs.get(key_ba)

def save_stereo_pair(cam_a: str, cam_b: str, R: list, T: list,
                     reprojection_error: float,
                     path: str = MULTI_CAM_CONFIG_PATH) -> None:
    """Save extrinsics for a camera pair."""
    from datetime import datetime, timezone
    cfg = load_multi_cam_config(path)
    if "pairs" not in cfg:
        cfg["pairs"] = {}
    key = f"{cam_a}--{cam_b}"
    cfg["pairs"][key] = {
        "R": R,
        "T": T,
        "reprojection_error": reprojection_error,
        "calibrated_utc": datetime.now(timezone.utc).isoformat(),
    }
    cfg["schema_version"] = 1
    save_multi_cam_config(cfg, path)
```

### 2.4 — `__init__.py` Exporte aktualisieren

`src/utils/__init__.py`: Ergänze die neuen Funktionen.

### 2.5 — Tests

**Neue Datei:** `tests/test_multi_cam_config.py`

Teste:
- `save_stereo_pair` + `get_stereo_pair` Roundtrip
- Order-independent Key-Lookup (`cam_a--cam_b` == `cam_b--cam_a`)
- `CalibrationManager` mit verschiedenen `camera_id` Werten in einer Datei
- Legacy-Migration: Lade eine flache YAML, speichere, prüfe dass `cameras.default` existiert
- File-Lock: Zwei Manager mit verschiedenen `camera_id` schreiben nacheinander in dieselbe Datei

**Bestehende Tests:** `tests/test_calibration.py` muss weiterhin grün sein (dort wird
`CalibrationManager` ohne `camera_id` instanziiert → Fallback auf `"default"`).

### Checkliste Step 2
- [ ] `CalibrationManager.__init__` akzeptiert `camera_id`
- [ ] Legacy-Config wird transparent migriert
- [ ] File-Level Lock für gleichzeitigen Zugriff
- [ ] `BoardCalibrationManager` / `CameraCalibrationManager` reichen `camera_id` durch
- [ ] `config/multi_cam.yaml` Skelett existiert
- [ ] `src/utils/config.py` erweitert um Stereo-Paar-Funktionen
- [ ] Neue Tests grün, bestehende Tests grün
- [ ] `schema_version: 3` in calibration_config.yaml nach Migration

---

## Step 3: Stereo-Kalibrierung implementieren

### Ziel
Extrinsische Parameter (R, T) zwischen zwei Kameras berechnen und in `multi_cam.yaml` speichern.

### 3.1 — `src/cv/stereo_calibration.py` (neues Modul)

```python
"""Stereo calibration: compute extrinsic parameters between two cameras."""

from __future__ import annotations

import logging
from typing import NamedTuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ChArUco board parameters for stereo calibration
# (distinct from board ArUco markers which use DICT_4X4_50)
STEREO_CHARUCO_DICT = cv2.aruco.DICT_6X6_250
STEREO_SQUARES_X = 7
STEREO_SQUARES_Y = 5
STEREO_SQUARE_LENGTH = 0.04   # meters
STEREO_MARKER_LENGTH = 0.02   # meters


class StereoResult(NamedTuple):
    ok: bool
    R: np.ndarray | None           # 3x3 rotation matrix
    T: np.ndarray | None           # 3x1 translation vector
    reprojection_error: float
    error_message: str | None


def detect_charuco_corners(
    frame: np.ndarray,
    dictionary=None,
    board=None,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Detect ChArUco corners in a single frame.

    Returns (charuco_corners, charuco_ids) or (None, None) if detection fails.
    """
    if dictionary is None:
        dictionary = cv2.aruco.getPredefinedDictionary(STEREO_CHARUCO_DICT)
    if board is None:
        board = cv2.aruco.CharucoBoard(
            (STEREO_SQUARES_X, STEREO_SQUARES_Y),
            STEREO_SQUARE_LENGTH, STEREO_MARKER_LENGTH, dictionary,
        )

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    detector = cv2.aruco.ArucoDetector(dictionary)
    corners, ids, _ = detector.detectMarkers(gray)

    if ids is None or len(ids) < 4:
        return None, None

    ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
        corners, ids, gray, board,
    )
    if ret < 4:
        return None, None

    return charuco_corners, charuco_ids


def stereo_calibrate(
    frames_cam1: list[np.ndarray],
    frames_cam2: list[np.ndarray],
    camera_matrix_1: np.ndarray,
    dist_coeffs_1: np.ndarray,
    camera_matrix_2: np.ndarray,
    dist_coeffs_2: np.ndarray,
    image_size: tuple[int, int] | None = None,
) -> StereoResult:
    """Compute extrinsic parameters between two cameras from synchronous ChArUco frames.

    Args:
        frames_cam1: List of frames from camera 1 (must be same length as frames_cam2).
        frames_cam2: List of frames from camera 2.
        camera_matrix_1: 3x3 intrinsic matrix of camera 1.
        dist_coeffs_1: Distortion coefficients of camera 1.
        camera_matrix_2: 3x3 intrinsic matrix of camera 2.
        dist_coeffs_2: Distortion coefficients of camera 2.
        image_size: (width, height) of the frames. Auto-detected if None.

    Returns:
        StereoResult with R, T, reprojection_error, or error message.
    """
    if len(frames_cam1) != len(frames_cam2):
        return StereoResult(False, None, None, 0.0,
                            f"Frame count mismatch: {len(frames_cam1)} vs {len(frames_cam2)}")
    if len(frames_cam1) < 5:
        return StereoResult(False, None, None, 0.0,
                            f"Need at least 5 frame pairs, got {len(frames_cam1)}")

    dictionary = cv2.aruco.getPredefinedDictionary(STEREO_CHARUCO_DICT)
    board = cv2.aruco.CharucoBoard(
        (STEREO_SQUARES_X, STEREO_SQUARES_Y),
        STEREO_SQUARE_LENGTH, STEREO_MARKER_LENGTH, dictionary,
    )

    obj_points_all: list[np.ndarray] = []
    img_points_1_all: list[np.ndarray] = []
    img_points_2_all: list[np.ndarray] = []

    for i, (f1, f2) in enumerate(zip(frames_cam1, frames_cam2)):
        if image_size is None:
            h, w = f1.shape[:2]
            image_size = (w, h)

        cc1, ci1 = detect_charuco_corners(f1, dictionary, board)
        cc2, ci2 = detect_charuco_corners(f2, dictionary, board)

        if cc1 is None or cc2 is None:
            logger.debug("Frame pair %d: detection failed in one camera, skipping", i)
            continue

        # Find common corner IDs
        ids1_flat = ci1.flatten()
        ids2_flat = ci2.flatten()
        common_ids = np.intersect1d(ids1_flat, ids2_flat)

        if len(common_ids) < 6:
            logger.debug("Frame pair %d: only %d common corners, skipping", i, len(common_ids))
            continue

        # Extract matching corners in consistent order
        mask1 = np.isin(ids1_flat, common_ids)
        mask2 = np.isin(ids2_flat, common_ids)

        pts1 = cc1[mask1].reshape(-1, 2)
        pts2 = cc2[mask2].reshape(-1, 2)

        # Sort by ID to ensure correspondence
        sorted_idx1 = np.argsort(ids1_flat[mask1])
        sorted_idx2 = np.argsort(ids2_flat[mask2])
        pts1 = pts1[sorted_idx1]
        pts2 = pts2[sorted_idx2]

        # Get object points for the common corner IDs
        obj_pts = board.getChessboardCorners()[common_ids].reshape(-1, 3).astype(np.float32)

        obj_points_all.append(obj_pts)
        img_points_1_all.append(pts1.astype(np.float32))
        img_points_2_all.append(pts2.astype(np.float32))

    if len(obj_points_all) < 3:
        return StereoResult(False, None, None, 0.0,
                            f"Only {len(obj_points_all)} usable frame pairs (need 3+)")

    try:
        flags = cv2.CALIB_FIX_INTRINSIC  # Intrinsics already calibrated per camera
        rms, _, _, _, _, R, T, E, F = cv2.stereoCalibrate(
            obj_points_all,
            img_points_1_all,
            img_points_2_all,
            camera_matrix_1, dist_coeffs_1,
            camera_matrix_2, dist_coeffs_2,
            image_size,
            flags=flags,
        )
    except cv2.error as e:
        return StereoResult(False, None, None, 0.0, f"stereoCalibrate failed: {e}")

    if not np.isfinite(rms):
        return StereoResult(False, None, None, 0.0, "Non-finite reprojection error")

    logger.info("Stereo calibration complete (RMS=%.4f)", rms)
    return StereoResult(True, R, T, float(rms), None)
```

### 3.2 — Tests

**Neue Datei:** `tests/test_stereo_calibration.py`

```python
"""Tests for stereo calibration with synthetic data."""

import numpy as np
import cv2
import pytest

from src.cv.stereo_calibration import (
    stereo_calibrate, detect_charuco_corners, StereoResult,
    STEREO_CHARUCO_DICT, STEREO_SQUARES_X, STEREO_SQUARES_Y,
    STEREO_SQUARE_LENGTH, STEREO_MARKER_LENGTH,
)


def _make_synthetic_stereo_pair(
    n_frames: int = 8,
    image_size: tuple[int, int] = (640, 480),
) -> tuple[list, list, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate synthetic ChArUco stereo image pairs with known extrinsics.

    Returns (frames1, frames2, K1, D1, K2, D2, R_true, T_true).
    """
    # Intrinsics (identical cameras for simplicity)
    fx, fy = 500.0, 500.0
    cx, cy = image_size[0] / 2, image_size[1] / 2
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float64)
    D = np.zeros((5, 1), dtype=np.float64)

    # Known extrinsic: camera 2 is 0.1m to the right of camera 1
    R_true = np.eye(3, dtype=np.float64)
    T_true = np.array([[0.1], [0.0], [0.0]], dtype=np.float64)

    dictionary = cv2.aruco.getPredefinedDictionary(STEREO_CHARUCO_DICT)
    board = cv2.aruco.CharucoBoard(
        (STEREO_SQUARES_X, STEREO_SQUARES_Y),
        STEREO_SQUARE_LENGTH, STEREO_MARKER_LENGTH, dictionary,
    )

    frames1, frames2 = [], []
    rng = np.random.RandomState(42)

    for _ in range(n_frames):
        # Random board pose in front of camera 1
        rvec = rng.uniform(-0.3, 0.3, 3).astype(np.float64)
        tvec = np.array([rng.uniform(-0.05, 0.05),
                         rng.uniform(-0.05, 0.05),
                         rng.uniform(0.3, 0.5)], dtype=np.float64)

        img1 = board.generateImage((image_size[0], image_size[1]))
        img2 = board.generateImage((image_size[0], image_size[1]))
        frames1.append(cv2.cvtColor(img1, cv2.COLOR_GRAY2BGR))
        frames2.append(cv2.cvtColor(img2, cv2.COLOR_GRAY2BGR))

    return frames1, frames2, K, D, K, D, R_true, T_true


class TestStereoCalibration:
    def test_frame_count_mismatch(self):
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        result = stereo_calibrate([np.zeros((10, 10, 3), dtype=np.uint8)], [], K, D, K, D)
        assert not result.ok
        assert "mismatch" in result.error_message.lower()

    def test_too_few_frames(self):
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        frames = [np.zeros((100, 100, 3), dtype=np.uint8)] * 3
        result = stereo_calibrate(frames, frames, K, D, K, D)
        assert not result.ok

    def test_result_type(self):
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        result = stereo_calibrate([], [], K, D, K, D)
        assert isinstance(result, StereoResult)

    def test_detect_charuco_corners_empty_frame(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        cc, ci = detect_charuco_corners(frame)
        assert cc is None and ci is None
```

**Hinweis für Claude Code:** Der synthetische Test mit `_make_synthetic_stereo_pair` ist
vorbereitet, aber `board.generateImage` erzeugt nur das Board-Bild — nicht ein projiziertes
Bild aus einer bestimmten Kamerapose. Ein vollständiger synthetischer Stereo-Test erfordert
`cv2.projectPoints` + `cv2.drawChessboardCorners`, was den Rahmen dieses Steps sprengt.
Der Test ist daher konservativ: Er prüft Fehlerhandling und Interfaces, nicht die
Triangulationsgenauigkeit. Genauigkeitstests kommen in Step 6 mit echten Daten.

### 3.3 — API-Routen (minimale Erweiterung)

**Datei:** `src/web/routes.py`

Füge nach den bestehenden Kalibrierungs-Routen hinzu:

```python
@router.post("/api/calibration/stereo")
async def stereo_calibration(request: Request) -> dict:
    """Run stereo calibration between two cameras."""
    body = await request.json()
    cam_a = body.get("camera_a", "default")
    cam_b = body.get("camera_b")
    if not cam_b:
        return {"ok": False, "error": "camera_b is required"}
    # ... Implementierung kommt in Step 5 vollständig,
    # hier nur Stub, der die Route registriert
    return {"ok": False, "error": "Not yet implemented — complete in Step 5"}
```

### 3.4 — `__init__.py` Exporte

`src/cv/__init__.py`: Ergänze `StereoResult` und `stereo_calibrate`.

### Checkliste Step 3
- [ ] `src/cv/stereo_calibration.py` existiert mit `stereo_calibrate()` und `detect_charuco_corners()`
- [ ] `StereoResult` NamedTuple definiert
- [ ] Tests in `tests/test_stereo_calibration.py` grün
- [ ] API-Stub `/api/calibration/stereo` registriert
- [ ] Bestehende Tests weiterhin grün

---

## Step 4: Multi-Kamera-Pipeline

### Ziel
Klasse `MultiCameraPipeline`, die mehrere `DartPipeline`-Instanzen koordiniert, Treffer
fusioniert (Triangulation oder Voting-Fallback) und eine einheitliche Callback-Schnittstelle bietet.

### 4.1 — `src/cv/stereo_utils.py` (Triangulations-Hilfsmodul)

```python
"""Stereo triangulation and camera parameter structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import cv2
import numpy as np


@dataclass
class CameraParams:
    """Complete camera model: intrinsics + extrinsics."""
    camera_id: str
    camera_matrix: np.ndarray      # 3x3
    dist_coeffs: np.ndarray        # Nx1
    R: np.ndarray                  # 3x3 rotation (world → camera)
    T: np.ndarray                  # 3x1 translation (world → camera)

    @property
    def projection_matrix(self) -> np.ndarray:
        """3x4 projection matrix P = K @ [R | T]."""
        RT = np.hstack([self.R, self.T.reshape(3, 1)])
        return self.camera_matrix @ RT


class TriangulationResult(NamedTuple):
    point_3d: np.ndarray    # (X, Y, Z) in world/board coordinate system
    reprojection_error: float
    valid: bool


def triangulate_point(
    pt1: tuple[float, float],
    pt2: tuple[float, float],
    cam1: CameraParams,
    cam2: CameraParams,
    max_reproj_error: float = 5.0,
) -> TriangulationResult:
    """Triangulate a 3D point from two 2D observations.

    Args:
        pt1: (x, y) pixel coordinate in camera 1.
        pt2: (x, y) pixel coordinate in camera 2.
        cam1: Camera parameters for camera 1.
        cam2: Camera parameters for camera 2.
        max_reproj_error: Maximum reprojection error (px) to consider valid.

    Returns:
        TriangulationResult with 3D point and quality metrics.
    """
    # Undistort points first
    pt1_undist = cv2.undistortPoints(
        np.array([[pt1]], dtype=np.float64),
        cam1.camera_matrix, cam1.dist_coeffs,
        P=cam1.camera_matrix,
    ).reshape(2)

    pt2_undist = cv2.undistortPoints(
        np.array([[pt2]], dtype=np.float64),
        cam2.camera_matrix, cam2.dist_coeffs,
        P=cam2.camera_matrix,
    ).reshape(2)

    P1 = cam1.projection_matrix
    P2 = cam2.projection_matrix

    # Triangulate
    pts_4d = cv2.triangulatePoints(
        P1, P2,
        pt1_undist.reshape(2, 1),
        pt2_undist.reshape(2, 1),
    )

    # Convert from homogeneous
    w = pts_4d[3, 0]
    if abs(w) < 1e-10:
        return TriangulationResult(np.zeros(3), float("inf"), False)
    point_3d = (pts_4d[:3, 0] / w).astype(np.float64)

    # Reprojection error check
    reproj_1 = _reproject(point_3d, cam1)
    reproj_2 = _reproject(point_3d, cam2)
    err_1 = np.linalg.norm(reproj_1 - np.array(pt1))
    err_2 = np.linalg.norm(reproj_2 - np.array(pt2))
    avg_error = float((err_1 + err_2) / 2.0)

    valid = avg_error <= max_reproj_error and point_3d[2] > 0  # Z > 0 = in front of cameras

    return TriangulationResult(point_3d, avg_error, valid)


def _reproject(point_3d: np.ndarray, cam: CameraParams) -> np.ndarray:
    """Reproject a 3D point to 2D pixel coordinates."""
    rvec, _ = cv2.Rodrigues(cam.R)
    pts_2d, _ = cv2.projectPoints(
        point_3d.reshape(1, 1, 3),
        rvec, cam.T,
        cam.camera_matrix, cam.dist_coeffs,
    )
    return pts_2d.reshape(2)


def point_3d_to_board_2d(
    point_3d: np.ndarray,
    board_normal: np.ndarray | None = None,
) -> tuple[float, float]:
    """Project a 3D point onto the board plane to get (x_mm, y_mm).

    Assumes the board lies in the Z=0 plane (if board_normal is None).
    """
    if board_normal is None:
        # Simple case: board at Z=0, X/Y are the board coordinates in meters
        return (float(point_3d[0] * 1000), float(point_3d[1] * 1000))  # m → mm
    # General case with board normal: project onto plane
    # (extend later if board is not at Z=0)
    return (float(point_3d[0] * 1000), float(point_3d[1] * 1000))
```

### 4.2 — `src/cv/multi_camera.py`

```python
"""Multi-camera pipeline: coordinate multiple DartPipelines and fuse results."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import numpy as np

from src.cv.pipeline import DartPipeline
from src.cv.stereo_utils import CameraParams, triangulate_point, point_3d_to_board_2d
from src.cv.geometry import BoardGeometry
from src.utils.config import get_stereo_pair

logger = logging.getLogger(__name__)

# Maximum time difference (seconds) between detections from two cameras
# to be considered "simultaneous" (software sync).
MAX_DETECTION_TIME_DIFF_S = 0.15  # 150ms


class MultiCameraPipeline:
    """Orchestrate multiple DartPipeline instances and fuse detections."""

    def __init__(
        self,
        camera_configs: list[dict],
        on_multi_dart_detected: Callable[[dict], None] | None = None,
        debug: bool = False,
    ) -> None:
        """
        Args:
            camera_configs: List of dicts, each with keys:
                - camera_id (str): Unique name, e.g. "cam_left"
                - src (int | str): Camera source index or video path
                - camera_params (CameraParams | None): For triangulation
            on_multi_dart_detected: Callback with fused score dict.
            debug: Enable debug visualization.
        """
        self.camera_configs = camera_configs
        self.on_multi_dart_detected = on_multi_dart_detected
        self.debug = debug

        self._pipelines: dict[str, DartPipeline] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._detection_buffer: dict[str, dict] = {}  # camera_id -> latest detection
        self._buffer_lock = threading.Lock()
        self._running = False
        self._fusion_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start all camera pipelines in separate threads."""
        self._running = True

        for cfg in self.camera_configs:
            cam_id = cfg["camera_id"]
            src = cfg.get("src", 0)

            pipeline = DartPipeline(
                camera_src=src,
                on_dart_detected=lambda score, det, _id=cam_id: self._on_single_detection(_id, score, det),
                debug=self.debug,
            )

            # Configure pipeline with camera-specific calibration
            # (BoardCalibrationManager and CameraCalibrationManager
            # must use the camera_id from Step 2)
            pipeline.board_calibration = type(pipeline.board_calibration)(
                camera_id=cam_id,
            )
            pipeline.camera_calibration = type(pipeline.camera_calibration)(
                camera_id=cam_id,
            )

            self._pipelines[cam_id] = pipeline

            thread = threading.Thread(
                target=self._run_pipeline_loop,
                args=(cam_id, pipeline),
                daemon=True,
                name=f"cv-pipeline-{cam_id}",
            )
            self._threads[cam_id] = thread
            thread.start()
            logger.info("Pipeline started for camera '%s' (src=%s)", cam_id, src)

        # Start fusion thread
        self._fusion_thread = threading.Thread(
            target=self._fusion_loop,
            daemon=True,
            name="cv-fusion",
        )
        self._fusion_thread.start()

    def stop(self) -> None:
        """Stop all pipelines."""
        self._running = False
        for cam_id, pipeline in self._pipelines.items():
            pipeline.stop()
            logger.info("Pipeline stopped for camera '%s'", cam_id)
        for thread in self._threads.values():
            thread.join(timeout=5.0)
        if self._fusion_thread:
            self._fusion_thread.join(timeout=5.0)

    def _run_pipeline_loop(self, cam_id: str, pipeline: DartPipeline) -> None:
        """Frame processing loop for a single camera."""
        try:
            pipeline.start()
        except Exception as e:
            logger.warning("Camera '%s' failed to start: %s", cam_id, e)
            return

        while self._running:
            try:
                pipeline.process_frame()
            except Exception as e:
                logger.debug("Frame error on '%s': %s", cam_id, e)
            time.sleep(0.001)

    def _on_single_detection(self, camera_id: str, score_result: dict, detection) -> None:
        """Callback from a single pipeline. Buffer detection for fusion."""
        with self._buffer_lock:
            self._detection_buffer[camera_id] = {
                "camera_id": camera_id,
                "score_result": score_result,
                "detection": detection,
                "timestamp": time.time(),
            }

    def _fusion_loop(self) -> None:
        """Periodically check detection buffer and fuse multi-camera results."""
        while self._running:
            time.sleep(0.05)  # 20Hz check rate
            self._try_fuse()

    def _try_fuse(self) -> None:
        """Attempt to fuse detections from multiple cameras."""
        with self._buffer_lock:
            if len(self._detection_buffer) < 2:
                # Single camera fallback: emit the lone detection
                if len(self._detection_buffer) == 1:
                    entry = list(self._detection_buffer.values())[0]
                    age = time.time() - entry["timestamp"]
                    if age > MAX_DETECTION_TIME_DIFF_S:
                        # Detection is old enough that the other camera won't
                        # catch up → use single-camera result as fallback
                        result = entry["score_result"]
                        result["source"] = "single"
                        result["camera_id"] = entry["camera_id"]
                        self._emit(result)
                        self._detection_buffer.clear()
                return

            # Check if detections are temporally close enough
            entries = list(self._detection_buffer.values())
            timestamps = [e["timestamp"] for e in entries]
            if max(timestamps) - min(timestamps) > MAX_DETECTION_TIME_DIFF_S:
                # Too far apart — use the most recent single detection
                latest = max(entries, key=lambda e: e["timestamp"])
                result = latest["score_result"]
                result["source"] = "single_timeout"
                result["camera_id"] = latest["camera_id"]
                self._emit(result)
                self._detection_buffer.clear()
                return

            # Two+ cameras detected within time window → attempt triangulation
            cam_ids = [e["camera_id"] for e in entries]
            cam_params = {
                cfg["camera_id"]: cfg.get("camera_params")
                for cfg in self.camera_configs
            }

            # Try triangulation for first pair with valid CameraParams
            triangulated = False
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    p1 = cam_params.get(entries[i]["camera_id"])
                    p2 = cam_params.get(entries[j]["camera_id"])
                    if p1 is None or p2 is None:
                        continue

                    det1 = entries[i]["detection"]
                    det2 = entries[j]["detection"]
                    if det1 is None or det2 is None:
                        continue

                    tri = triangulate_point(
                        det1.center, det2.center, p1, p2,
                    )
                    if tri.valid:
                        board_x_mm, board_y_mm = point_3d_to_board_2d(tri.point_3d)
                        # Convert mm to board score via geometry of first camera
                        pipeline_1 = self._pipelines.get(entries[i]["camera_id"])
                        if pipeline_1 and pipeline_1.geometry:
                            geo = pipeline_1.geometry
                            # Convert mm back to ROI pixels for scoring
                            from src.cv.geometry import BOARD_RADIUS_MM
                            radius_px = geo.double_outer_radius_px
                            mm_per_px = BOARD_RADIUS_MM / radius_px if radius_px > 0 else 1.0
                            ox, oy = geo.optical_center_px
                            roi_x = ox + board_x_mm / mm_per_px
                            roi_y = oy + board_y_mm / mm_per_px
                            hit = geo.point_to_score(roi_x, roi_y)
                            result = geo.hit_to_dict(hit)
                            result["source"] = "triangulation"
                            result["reprojection_error"] = tri.reprojection_error
                            self._emit(result)
                            triangulated = True
                            break
                if triangulated:
                    break

            if not triangulated:
                # Voting fallback: average the 2D detections
                result = self._voting_fallback(entries)
                self._emit(result)

            self._detection_buffer.clear()

    def _voting_fallback(self, entries: list[dict]) -> dict:
        """When triangulation fails, use best single-camera result or average."""
        # Pick the detection with highest confidence
        best = max(entries, key=lambda e: getattr(e.get("detection"), "confidence", 0))
        result = best["score_result"]
        result["source"] = "voting_fallback"
        result["camera_id"] = best["camera_id"]
        return result

    def _emit(self, score_result: dict) -> None:
        """Emit fused detection via callback."""
        if self.on_multi_dart_detected:
            self.on_multi_dart_detected(score_result)

    def reset_all(self) -> None:
        """Reset detectors on all pipelines (darts removed)."""
        for pipeline in self._pipelines.values():
            pipeline.reset_turn()
        with self._buffer_lock:
            self._detection_buffer.clear()

    def get_pipelines(self) -> dict[str, DartPipeline]:
        """Expose individual pipelines for frame access, overlays, etc."""
        return dict(self._pipelines)
```

### 4.3 — Tests

**Neue Datei:** `tests/test_stereo_utils.py`

```
Teste triangulate_point mit synthetischen Daten:
- Zwei Kameras mit bekannten intrinsics/extrinsics
- Bekannter 3D-Punkt → projiziere auf beide Kameras → trianguliere → vergleiche
- Prüfe dass reprojection_error < 1.0 px
- Prüfe dass ungültige Eingaben (degenerate Punkte) valid=False ergeben
- Prüfe point_3d_to_board_2d Konvertierung (mm-Skalierung)
```

**Neue Datei:** `tests/test_multi_camera.py`

```
Teste MultiCameraPipeline:
- Instanziierung mit leerer camera_configs-Liste → kein Crash
- start()/stop() Lifecycle (mit Mock-Kameras, z.B. ReplayCamera)
- _voting_fallback wählt höchste Confidence
- _on_single_detection puffert korrekt
- reset_all() leert den Buffer
```

### 4.4 — `__init__.py` Exporte

`src/cv/__init__.py`: Ergänze `MultiCameraPipeline`, `CameraParams`,
`triangulate_point`, `TriangulationResult`.

### Checkliste Step 4
- [ ] `src/cv/stereo_utils.py` mit `CameraParams`, `triangulate_point`, `point_3d_to_board_2d`
- [ ] `src/cv/multi_camera.py` mit `MultiCameraPipeline`
- [ ] Frame-Synchronisation via Zeitfenster (`MAX_DETECTION_TIME_DIFF_S = 0.15`)
- [ ] Single-Camera-Fallback wenn nur eine Kamera erkennt
- [ ] Voting-Fallback wenn Triangulation fehlschlägt
- [ ] Thread pro Kamera + Fusion-Thread
- [ ] Tests für `stereo_utils` und `multi_camera` grün
- [ ] Bestehende Tests weiterhin grün
- [ ] `DartPipeline` selbst unverändert (Einzelkamera-Betrieb bleibt)

---

## Step 5: API und Frontend anpassen

### Ziel
Backend-Routen für Multi-Kamera-Start, WebSocket-Anpassung, Frontend-Erweiterung.

### 5.1 — Backend: `src/main.py` erweitern

**Neue Felder in `app_state`:**
```python
app_state.update({
    "multi_pipeline": None,         # MultiCameraPipeline | None
    "multi_pipeline_running": False,
    "active_camera_ids": [],        # List of active camera IDs
})
```

**Neue Funktion `_run_multi_pipeline`:**
Analog zu `_run_pipeline`, aber instanziiert `MultiCameraPipeline` statt `DartPipeline`.
Der Callback `on_multi_dart_detected` erzeugt Hit-Candidates analog zum Single-Pipeline-Flow.

**Wichtig:** Wenn Multi-Pipeline läuft, muss der Einzel-Pipeline-Thread gestoppt sein
(und umgekehrt). Nicht beide gleichzeitig laufen lassen.

### 5.2 — Backend-Routen: `src/web/routes.py`

Neue Routen:

```python
@router.post("/api/multi/start")
async def multi_start(request: Request) -> dict:
    """Start multi-camera pipeline.

    Body: {"cameras": [{"camera_id": "cam_left", "src": 0},
                        {"camera_id": "cam_right", "src": 1}]}
    """
    # ... parse camera configs, stop existing pipeline, start multi pipeline
    pass

@router.post("/api/multi/stop")
async def multi_stop() -> dict:
    """Stop multi-camera pipeline and optionally restart single pipeline."""
    pass

@router.get("/api/multi/status")
async def multi_status() -> dict:
    """Get multi-camera pipeline status (per-camera FPS, calibration state)."""
    pass

@router.post("/api/calibration/stereo")
async def stereo_calibration_run(request: Request) -> dict:
    """Execute stereo calibration between two cameras.

    Body: {"camera_a": "cam_left", "camera_b": "cam_right"}

    Requires: Both cameras must have valid lens intrinsics (Step 2/3).
    Captures synchronized frame pairs, runs stereo_calibrate, saves to multi_cam.yaml.
    """
    pass
```

Passe den bestehenden WebSocket-Handler an:
- Score-Events kommen entweder aus Single- oder Multi-Pipeline (transparent für Frontend)
- Neuer Event-Typ `"multi_status"` mit Per-Camera-Stats

### 5.3 — Frontend: `templates/index.html` und JS

**Neues UI-Element:** Kamera-Auswahl (Dropdown oder Checkboxes für aktive Kameras).

**Neues UI-Element:** Multi-Camera Video-Grid (zeigt Streams aller aktiven Kameras).

**Kalibrierungs-Modal erweitern:**
- Neuer Tab "Stereo-Kalibrierung"
- Zeigt beide Videostreams nebeneinander
- Button "Bild aufnehmen" (synchron)
- Anzeige der Paar-Anzahl und Reprojektion-Fehler
- Button "Kalibrieren" wenn genug Paare (>= 5)

**Trefferanzeige:** Keine Änderung nötig — die Hit-Candidate-Logik bleibt identisch,
egal ob die Quelle Single- oder Multi-Pipeline ist. Das `source`-Feld im Score-Dict
kann im UI als Badge angezeigt werden ("TRI" für Triangulation, "1-CAM" für Fallback).

### 5.4 — README.md aktualisieren

Ergänze:
- Hardware-Anforderungen für Mehrkamera-Setup (2+ USB-Kameras, USB-Hub mit ausreichend Bandbreite)
- Empfohlene Kamera-Platzierung: 60–90° Winkel zueinander, 50–80 cm Abstand zum Board
- Kalibrier-Workflow: (1) Lens Setup pro Kamera, (2) Board Alignment pro Kamera, (3) Stereo-Kalibrierung pro Paar
- Neue API-Routen dokumentieren

### Checkliste Step 5
- [ ] `/api/multi/start`, `/api/multi/stop`, `/api/multi/status` Routen
- [ ] `/api/calibration/stereo` vollständig implementiert
- [ ] WebSocket sendet Score-Events unabhängig von Pipeline-Typ
- [ ] Frontend zeigt Kamera-Auswahl
- [ ] Frontend zeigt Multi-Video-Grid
- [ ] Stereo-Kalibrierung im Modal
- [ ] README mit Multi-Kamera-Doku
- [ ] Bestehende Tests grün

---

## Step 6: Tests, Benchmarks und Feinschliff

### Ziel
Performance-Validierung, Robustheitstests, strukturiertes Logging.

### 6.1 — Benchmark erweitern: `tests/benchmark_pipeline.py`

Ergänze optionalen `--cameras N` Parameter:
- Simuliert N parallele Pipelines mit Mock-Frames
- Misst FPS pro Kamera, Gesamt-FPS, Latenz, CPU, Memory
- Neue KPIs für Mehrkamera:
  - Per-Camera FPS >= 10 (statt 15 bei Single)
  - Gesamtlatenz (Detection → Fusion → Score) <= 300ms
  - CPU <= 90% bei 2 Kameras
  - Memory <= 768 MB bei 2 Kameras

### 6.2 — Robustheitstests

**Neue Datei:** `tests/test_multi_robustness.py`

Szenarien:
- Eine Kamera fällt aus während Betrieb → Fallback auf Single ohne Crash
- Triangulation ergibt Z < 0 (hinter Board) → Voting-Fallback
- Detektionen sind zeitlich zu weit auseinander → Single-Camera-Fallback
- Beide Kameras erkennen verschiedene Sektoren → Voting wählt höhere Confidence
- Kamera-Auflösungen unterschiedlich → kein Crash

### 6.3 — Strukturiertes Logging

Erweitere `src/utils/logger.py`:

```python
def setup_logging(level: int = logging.INFO, json_format: bool = False) -> None:
    if json_format:
        # JSON-Formatter für Produktionsbetrieb
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"module":"%(name)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        formatter = logging.Formatter(...)  # existing format
```

In `MultiCameraPipeline` und `stereo_utils`: Alle Log-Meldungen enthalten `camera_id`
und ggf. `calibration_version` (= `schema_version` + `last_update_utc`).

### 6.4 — Voting-Ansatz verfeinern

In `MultiCameraPipeline._voting_fallback`:
- Wenn Triangulation Z-Wert unplausibel (|Z| > 50mm = zu weit vom Board), nutze 2D-Mittelwert
- Gewichte nach Confidence: `weighted_avg = sum(score_i * conf_i) / sum(conf_i)`
- Optional: Median statt Mean bei >= 3 Kameras

### Checkliste Step 6
- [ ] Benchmark mit `--cameras` Parameter
- [ ] Neue KPI-Grenzwerte für Mehrkamera dokumentiert
- [ ] Robustheitstests grün
- [ ] JSON-Logging-Option
- [ ] Alle Log-Meldungen in Multi-Modulen enthalten `camera_id`
- [ ] Voting-Fallback gewichtet nach Confidence
- [ ] Gesamte Test-Suite grün (`pytest` mit 0 Failures)

---

## Zusammenfassung der neuen Dateien

| Datei | Step | Beschreibung |
|-------|------|--------------|
| `config/multi_cam.yaml` | 2 | Extrinsische Stereo-Parameter |
| `src/cv/stereo_calibration.py` | 3 | ChArUco-basierte Stereo-Kalibrierung |
| `src/cv/stereo_utils.py` | 4 | `CameraParams`, `triangulate_point` |
| `src/cv/multi_camera.py` | 4 | `MultiCameraPipeline` |
| `tests/test_multi_cam_config.py` | 2 | Config-Migration, Stereo-Paar-Speicherung |
| `tests/test_stereo_calibration.py` | 3 | Stereo-Kalibrierung |
| `tests/test_stereo_utils.py` | 4 | Triangulation |
| `tests/test_multi_camera.py` | 4 | Multi-Pipeline Lifecycle |
| `tests/test_multi_robustness.py` | 6 | Ausfallszenarien |

## Geänderte Dateien (kumulativ)

| Datei | Steps | Art der Änderung |
|-------|-------|------------------|
| `src/cv/calibration.py` | 2 | `camera_id` Parameter, Migration, File-Lock |
| `src/cv/board_calibration.py` | 2 | `camera_id` durchreichen |
| `src/cv/camera_calibration.py` | 2 | `camera_id` durchreichen |
| `src/utils/config.py` | 2 | Stereo-Paar-Funktionen |
| `src/utils/__init__.py` | 2 | Neue Exporte |
| `src/cv/__init__.py` | 3, 4 | Neue Exporte |
| `src/main.py` | 5 | Multi-Pipeline Lifecycle, `app_state` |
| `src/web/routes.py` | 3, 5 | Neue Routen |
| `templates/index.html` | 5 | Kamera-Auswahl, Multi-Video, Stereo-Kalibrierung |
| `static/js/app.js` | 5 | Multi-Kamera UI-Logik |
| `static/css/style.css` | 5 | Multi-Video-Grid Styles |
| `README.md` | 5 | Multi-Kamera-Dokumentation |
| `tests/benchmark_pipeline.py` | 6 | `--cameras` Parameter |
| `src/utils/logger.py` | 6 | JSON-Logging-Option |
