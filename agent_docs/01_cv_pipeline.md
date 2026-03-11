# CV-Pipeline: Implementierungs-Spezifikation

> Lies dieses Dokument, wenn du an `src/cv/` arbeitest.

---

## Übersicht

Die CV-Pipeline verarbeitet Kamera-Frames in Echtzeit und erkennt Dart-Einschläge auf einem Standard-Dartboard. Die Pipeline folgt dem **ROI-First + Motion-Gated** Prinzip: Erst Board isolieren, dann nur bei Bewegung detektieren.

### Pipeline-Flow

```
Frame (720p) → Grayscale → CLAHE → ROI Warp → Motion Check
                                                    │
                                         ┌──────────┤
                                         │ NO       │ YES
                                         ▼          ▼
                                     Skip Frame   Shape Analysis
                                                    │
                                                    ▼
                                              Temporal Confirmation
                                              (≥3 Frames stabil)
                                                    │
                                                    ▼
                                              Sector/Ring Mapping
                                                    │
                                                    ▼
                                              Score Event → WebSocket
```

---

## Modul 1: ThreadedCamera (`src/cv/capture.py`)

### Zweck
Entkoppelte Bilderfassung in separatem Thread. Verhindert I/O-Blocking und liefert 52% Speedup gegenüber synchronem Capture.

### Interface
```python
class ThreadedCamera:
    """Thread-safe video capture with bounded queue and graceful frame dropping."""

    def __init__(self, src: int | str = 0, max_queue_size: int = 5) -> None:
        """
        Args:
            src: Camera index (int) or video file path (str).
            max_queue_size: Maximum frames in queue before dropping oldest.
        """
        ...

    def start(self) -> None:
        """Start the capture thread."""
        ...

    def read(self) -> tuple[bool, np.ndarray | None]:
        """Read the latest frame. Returns (success, frame)."""
        ...

    def stop(self) -> None:
        """Stop capture thread and release camera."""
        ...

    def is_running(self) -> bool:
        """Check if capture thread is active."""
        ...

    @property
    def frame_size(self) -> tuple[int, int]:
        """Return (width, height) of captured frames."""
        ...
```

### Implementierungs-Details

```python
import cv2
import threading
import queue
import time
import logging

logger = logging.getLogger(__name__)


class ThreadedCamera:
    def __init__(self, src: int | str = 0, max_queue_size: int = 5) -> None:
        self.src = src
        self.capture = cv2.VideoCapture(src)
        if not self.capture.isOpened():
            raise RuntimeError(f"Cannot open camera source: {src}")

        # Reduce internal OpenCV buffer to minimize latency
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self.frame_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_queue_size)
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info("Camera capture started (src=%s)", self.src)

    def _capture_loop(self) -> None:
        reconnect_delay = 1.0
        max_reconnect_delay = 30.0

        while self._running:
            ret, frame = self.capture.read()
            if not ret:
                # Auto-reconnect with exponential backoff
                logger.warning("Frame read failed, reconnecting in %.1fs...", reconnect_delay)
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                self.capture.release()
                self.capture = cv2.VideoCapture(self.src)
                continue

            reconnect_delay = 1.0  # Reset on success

            # Graceful frame dropping: drop oldest if queue full
            if self.frame_queue.full():
                try:
                    self.frame_queue.get_nowait()
                except queue.Empty:
                    pass
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                pass

    def read(self) -> tuple[bool, np.ndarray | None]:
        try:
            frame = self.frame_queue.get(timeout=0.1)
            return True, frame
        except queue.Empty:
            return False, None

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self.capture.release()
        logger.info("Camera capture stopped")

    def is_running(self) -> bool:
        return self._running

    @property
    def frame_size(self) -> tuple[int, int]:
        w = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)
```

### Failure Recovery
1. **Frame Dropping:** Bei voller Queue wird ältester Frame verworfen (Graceful Degradation)
2. **Auto-Reconnect:** Bei Kamera-Trennung automatischer Reconnect mit Exponential Backoff (1s → 30s)

---

## Modul 2: ROIProcessor (`src/cv/roi.py`)

### Zweck
Perspektivische Entzerrung des Dartboards und Extraktion der Region of Interest. Reduziert die zu verarbeitende Datenmenge drastisch.

### Interface
```python
class ROIProcessor:
    """Extracts and warps the dartboard region using homography."""

    def __init__(self, roi_size: tuple[int, int] = (400, 400)) -> None:
        ...

    def set_homography(self, src_points: np.ndarray, dst_points: np.ndarray) -> None:
        """Set perspective transform from 4 source to 4 destination points."""
        ...

    def set_homography_matrix(self, matrix: np.ndarray) -> None:
        """Directly set the 3x3 homography matrix (from config)."""
        ...

    def warp_roi(self, frame: np.ndarray) -> np.ndarray:
        """Apply perspective transform. Falls back to identity if no homography set."""
        ...

    def polar_unwrap(self, roi_frame: np.ndarray, center: tuple[int, int] | None = None,
                     radius: int = 200) -> np.ndarray:
        """Convert circular dartboard to linear polar coordinates."""
        ...
```

### Implementierung
```python
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ROIProcessor:
    def __init__(self, roi_size: tuple[int, int] = (400, 400)) -> None:
        self.roi_size = roi_size
        self.homography: np.ndarray | None = None

    def set_homography(self, src_points: np.ndarray, dst_points: np.ndarray) -> None:
        src = np.float32(src_points)
        dst = np.float32(dst_points)
        self.homography = cv2.getPerspectiveTransform(src, dst)
        logger.info("Homography set from %d point pairs", len(src_points))

    def set_homography_matrix(self, matrix: np.ndarray) -> None:
        self.homography = np.array(matrix, dtype=np.float64).reshape(3, 3)

    def warp_roi(self, frame: np.ndarray) -> np.ndarray:
        if self.homography is None:
            logger.debug("No homography set, returning original frame")
            return frame
        try:
            warped = cv2.warpPerspective(frame, self.homography, self.roi_size)
            return warped
        except cv2.error as e:
            logger.error("Warp failed: %s — falling back to identity", e)
            return frame

    def polar_unwrap(self, roi_frame: np.ndarray, center: tuple[int, int] | None = None,
                     radius: int = 200) -> np.ndarray:
        if center is None:
            h, w = roi_frame.shape[:2]
            center = (w // 2, h // 2)
        polar = cv2.warpPolar(
            roi_frame,
            (2 * radius, 360),
            center,
            radius,
            cv2.WARP_POLAR_LINEAR
        )
        return polar
```

### Failure Recovery
1. **Identity Transform Fallback:** Wenn Homography `None` oder ungültig → Original-Frame zurückgeben
2. **Auto-Center-Estimation:** Wenn `polar_center` fehlt → ROI-Mittelpunkt verwenden

---

## Modul 3: MotionDetector (`src/cv/motion.py`)

### Zweck
Motion-Gating via MOG2 Background Subtraction. Aktiviert teure Detektionslogik nur bei signifikanter Bewegung.

### Interface
```python
class MotionDetector:
    """MOG2-based motion detection with configurable threshold."""

    def __init__(self, threshold: int = 500, detect_shadows: bool = True,
                 var_threshold: int = 50) -> None:
        ...

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, bool]:
        """Returns (cleaned_motion_mask, motion_detected_flag)."""
        ...

    def reset(self) -> None:
        """Reset background model (e.g., after calibration change)."""
        ...
```

### Implementierung
```python
import cv2
import numpy as np


class MotionDetector:
    def __init__(self, threshold: int = 500, detect_shadows: bool = True,
                 var_threshold: int = 50) -> None:
        self.threshold = threshold
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=detect_shadows,
            varThreshold=var_threshold
        )
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def detect(self, frame: np.ndarray) -> tuple[np.ndarray, bool]:
        fg_mask = self.bg_subtractor.apply(frame)
        # Remove shadow pixels (MOG2 marks shadows as 127)
        fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)[1]
        # Morphological cleanup
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self._kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self._kernel)

        motion_pixels = cv2.countNonZero(fg_mask)
        return fg_mask, motion_pixels > self.threshold

    def reset(self) -> None:
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True, varThreshold=50
        )
```

### Tuning-Parameter
| Parameter | Default | Bereich | Effekt |
|-----------|---------|---------|--------|
| `threshold` | 500 px | 100–2000 | Höher = weniger sensitiv, weniger False Positives |
| `var_threshold` | 50 | 16–100 | Höher = nur starke Bewegung erkannt |
| `detect_shadows` | True | — | Shadow-Erkennung reduziert False Positives |

---

## Modul 4: DartImpactDetector (`src/cv/detector.py`)

### Zweck
Erkennung von Dart-Einschlägen durch Konturanalyse + temporale Multi-Frame-Bestätigung (Land-and-Stick Logic).

### Interface
```python
from dataclasses import dataclass


@dataclass
class DartDetection:
    """Represents a confirmed dart detection."""
    center: tuple[int, int]     # (x, y) in ROI coordinates
    area: float                 # Contour area in pixels
    confidence: float           # 0.0–1.0
    frame_count: int            # Number of confirmation frames


class DartImpactDetector:
    """Detects dart impacts using shape analysis and temporal confirmation."""

    def __init__(self, confirmation_frames: int = 3,
                 position_tolerance_px: int = 20,
                 area_min: int = 10, area_max: int = 1000,
                 aspect_ratio_range: tuple[float, float] = (0.3, 3.0)) -> None:
        ...

    def detect(self, roi_frame: np.ndarray, motion_mask: np.ndarray) -> DartDetection | None:
        """Analyze motion mask for dart-shaped objects. Returns confirmed detection or None."""
        ...

    def reset(self) -> None:
        """Reset temporal state (e.g., after dart removal)."""
        ...

    def get_all_confirmed(self) -> list[DartDetection]:
        """Return all currently confirmed dart positions (up to 3 per turn)."""
        ...
```

### Implementierung
```python
import cv2
import numpy as np
import math
import logging

logger = logging.getLogger(__name__)


class DartImpactDetector:
    def __init__(self, confirmation_frames: int = 3,
                 position_tolerance_px: int = 20,
                 area_min: int = 10, area_max: int = 1000,
                 aspect_ratio_range: tuple[float, float] = (0.3, 3.0)) -> None:
        self.confirmation_frames = confirmation_frames
        self.position_tolerance_px = position_tolerance_px
        self.area_min = area_min
        self.area_max = area_max
        self.aspect_ratio_range = aspect_ratio_range

        # Temporal state
        self._candidates: list[dict] = []
        self._confirmed: list[DartDetection] = []

    def detect(self, roi_frame: np.ndarray, motion_mask: np.ndarray) -> DartDetection | None:
        shapes = self._find_dart_shapes(motion_mask)
        if not shapes:
            # Decay candidates that weren't seen
            self._decay_candidates()
            return None

        best = shapes[0]
        matched = self._match_candidate(best)

        if matched is not None:
            matched["count"] += 1
            matched["center"] = best["center"]
            matched["area"] = best["area"]

            if matched["count"] >= self.confirmation_frames:
                detection = DartDetection(
                    center=matched["center"],
                    area=matched["area"],
                    confidence=min(matched["area"] / 200.0, 1.0),
                    frame_count=matched["count"]
                )
                # Check if this is a new dart (not already confirmed)
                if not self._is_already_confirmed(detection):
                    self._confirmed.append(detection)
                    logger.info("Dart confirmed at %s (area=%.0f, frames=%d)",
                                detection.center, detection.area, detection.frame_count)
                    return detection
        else:
            self._candidates.append({
                "center": best["center"],
                "area": best["area"],
                "count": 1
            })

        return None

    def _find_dart_shapes(self, motion_mask: np.ndarray) -> list[dict]:
        contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []

        for contour in contours:
            area = cv2.contourArea(contour)
            if not (self.area_min < area < self.area_max):
                continue

            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                continue
            aspect_ratio = float(w) / h

            if not (self.aspect_ratio_range[0] < aspect_ratio < self.aspect_ratio_range[1]):
                continue

            M = cv2.moments(contour)
            if M["m00"] <= 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            candidates.append({"center": (cx, cy), "area": area})

        candidates.sort(key=lambda d: d["area"], reverse=True)
        return candidates

    def _match_candidate(self, shape: dict) -> dict | None:
        for candidate in self._candidates:
            dist = math.hypot(
                shape["center"][0] - candidate["center"][0],
                shape["center"][1] - candidate["center"][1]
            )
            if dist < self.position_tolerance_px:
                return candidate
        return None

    def _is_already_confirmed(self, detection: DartDetection) -> bool:
        for confirmed in self._confirmed:
            dist = math.hypot(
                detection.center[0] - confirmed.center[0],
                detection.center[1] - confirmed.center[1]
            )
            if dist < self.position_tolerance_px:
                return True
        return False

    def _decay_candidates(self) -> None:
        self._candidates = [c for c in self._candidates if c["count"] > 1]
        for c in self._candidates:
            c["count"] -= 1

    def reset(self) -> None:
        self._candidates.clear()
        self._confirmed.clear()

    def get_all_confirmed(self) -> list[DartDetection]:
        return list(self._confirmed)
```

### Tuning-Parameter
| Parameter | Default | Bereich | Effekt |
|-----------|---------|---------|--------|
| `confirmation_frames` | 3 | 2–7 | Höher = weniger False Positives, mehr Latenz |
| `position_tolerance_px` | 20 | 10–40 | Höher = toleranter bei Positionsschwankungen |
| `area_min` | 10 px² | 5–50 | Filter für zu kleine Konturen (Rauschen) |
| `area_max` | 1000 px² | 500–3000 | Filter für zu große Konturen (Hand/Arm) |

---

## Modul 5: FieldMapper (`src/cv/field_mapper.py`)

### Zweck
Übersetzt Pixelkoordinaten im entzerrten ROI-Bild in Dartboard-Sektoren und Punktwerte.

### Dartboard-Geometrie

Standard-Dartboard (WDF/BDO/PDC):
- **20 Sektoren** à 18° (im Uhrzeigersinn ab 12 Uhr: 20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)
- **Offset:** ±9° damit Sektor 20 zentriert bei 12 Uhr liegt
- **Ring-Radien** (normalisiert, Board-Radius = 1.0):

| Ring | Innerer Radius | Äußerer Radius | Multiplikator |
|------|---------------|----------------|---------------|
| Inner Bull | 0.00 | 0.05 | 50 Punkte (flat) |
| Outer Bull | 0.05 | 0.095 | 25 Punkte (flat) |
| Inner Single | 0.095 | 0.53 | ×1 |
| Triple | 0.53 | 0.58 | ×3 |
| Outer Single | 0.58 | 0.94 | ×1 |
| Double | 0.94 | 1.00 | ×2 |
| Miss | > 1.00 | — | 0 Punkte |

### Interface
```python
class FieldMapper:
    """Maps pixel coordinates to dartboard sector and score."""

    SECTOR_ORDER: list[int] = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                                3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

    def __init__(self, sector_offset_deg: float = 9.0) -> None:
        ...

    def point_to_score(self, x: float, y: float,
                       center_x: float, center_y: float,
                       radius_px: float) -> dict:
        """
        Convert pixel coords to score.

        Returns:
            {
                "score": int,           # Total points (e.g., 60 for T20)
                "sector": int,          # Base sector value (e.g., 20)
                "multiplier": int,      # 1, 2, or 3 (or 0 for miss)
                "ring": str,            # "inner_bull", "outer_bull", "single",
                                        # "triple", "double", "miss"
                "normalized_distance": float,  # 0.0–1.0+
                "angle_deg": float      # 0–360
            }
        """
        ...
```

### Implementierung
```python
import math


class FieldMapper:
    SECTOR_ORDER = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                    3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

    RING_RADII = {
        "bull_inner": 0.05,
        "bull_outer": 0.095,
        "triple_inner": 0.53,
        "triple_outer": 0.58,
        "double_inner": 0.94,
        "double_outer": 1.00,
    }

    def __init__(self, sector_offset_deg: float = 9.0) -> None:
        self.sector_offset_deg = sector_offset_deg
        self.sector_angle_deg = 18.0  # 360 / 20

    def point_to_score(self, x: float, y: float,
                       center_x: float, center_y: float,
                       radius_px: float) -> dict:
        dx = x - center_x
        dy = y - center_y
        distance = math.hypot(dx, dy)
        norm_dist = distance / radius_px if radius_px > 0 else 999.0

        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        # Adjust: 0° at top (12 o'clock), clockwise
        adjusted_angle = (angle_deg + 90 + self.sector_offset_deg) % 360

        sector_index = int(adjusted_angle / self.sector_angle_deg) % 20
        sector_value = self.SECTOR_ORDER[sector_index]

        # Determine ring
        r = self.RING_RADII
        if norm_dist <= r["bull_inner"]:
            return self._result(50, 50, 1, "inner_bull", norm_dist, adjusted_angle)
        elif norm_dist <= r["bull_outer"]:
            return self._result(25, 25, 1, "outer_bull", norm_dist, adjusted_angle)
        elif norm_dist <= r["triple_inner"]:
            return self._result(sector_value, sector_value, 1, "single", norm_dist, adjusted_angle)
        elif norm_dist <= r["triple_outer"]:
            return self._result(sector_value * 3, sector_value, 3, "triple", norm_dist, adjusted_angle)
        elif norm_dist <= r["double_inner"]:
            return self._result(sector_value, sector_value, 1, "single", norm_dist, adjusted_angle)
        elif norm_dist <= r["double_outer"]:
            return self._result(sector_value * 2, sector_value, 2, "double", norm_dist, adjusted_angle)
        else:
            return self._result(0, 0, 0, "miss", norm_dist, adjusted_angle)

    def _result(self, score: int, sector: int, multiplier: int, ring: str,
                norm_dist: float, angle: float) -> dict:
        return {
            "score": score,
            "sector": sector,
            "multiplier": multiplier,
            "ring": ring,
            "normalized_distance": round(norm_dist, 4),
            "angle_deg": round(angle, 2),
        }
```

---

## Modul 6: DartPipeline (`src/cv/pipeline.py`)

### Zweck
Orchestrator, der alle CV-Module verbindet und die Frame-by-Frame-Verarbeitung steuert.

### Interface
```python
from typing import Callable


class DartPipeline:
    """Orchestrates the full CV pipeline: capture → preprocess → detect → score."""

    def __init__(self, camera_src: int | str = 0,
                 on_dart_detected: Callable[[dict], None] | None = None,
                 on_dart_removed: Callable[[], None] | None = None,
                 debug: bool = False) -> None:
        """
        Args:
            camera_src: Camera source for ThreadedCamera.
            on_dart_detected: Callback when a dart is confirmed. Receives score dict.
            on_dart_removed: Callback when darts are removed (turn reset).
            debug: Show OpenCV debug windows with overlays.
        """
        ...

    def start(self) -> None:
        """Initialize all modules and start processing loop."""
        ...

    def stop(self) -> None:
        """Stop processing and release resources."""
        ...

    def process_frame(self) -> dict | None:
        """Process one frame. Returns score dict if dart detected, else None."""
        ...

    def set_calibration(self, src_points: np.ndarray, dst_points: np.ndarray) -> None:
        """Update calibration (from web frontend or CLI)."""
        ...

    def reset_turn(self) -> None:
        """Reset detector state for new turn (after darts removed)."""
        ...

    def get_annotated_frame(self) -> np.ndarray | None:
        """Get current frame with HUD overlay (for MJPEG stream)."""
        ...
```

### Hauptverarbeitungsschleife (Pseudocode)
```python
def process_frame(self) -> dict | None:
    ret, frame = self.camera.read()
    if not ret:
        return None

    self.fps_counter.update()

    # 1. Preprocessing
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    enhanced = self.clahe.apply(gray)

    # 2. ROI Extraction
    roi = self.roi_processor.warp_roi(enhanced)

    # 3. Motion Gating
    motion_mask, has_motion = self.motion_detector.detect(roi)

    if not has_motion:
        self._update_annotated_frame(frame, roi, None)
        return None

    # 4. Dart Detection (only when motion detected)
    detection = self.dart_detector.detect(roi, motion_mask)

    if detection is None:
        self._update_annotated_frame(frame, roi, motion_mask)
        return None

    # 5. Scoring
    center_x = self.roi_processor.roi_size[0] // 2
    center_y = self.roi_processor.roi_size[1] // 2
    radius_px = min(center_x, center_y)

    score_result = self.field_mapper.point_to_score(
        detection.center[0], detection.center[1],
        center_x, center_y, radius_px
    )

    # 6. Callback
    if self.on_dart_detected:
        self.on_dart_detected(score_result)

    self._update_annotated_frame(frame, roi, motion_mask, detection, score_result)
    return score_result
```

### CLAHE Preprocessing
```python
# Im __init__ der Pipeline:
self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
```

### Debug HUD Overlay
Im Debug-Modus (`--debug`) soll ein OpenCV-Fenster folgende Overlays zeigen:
- **FPS** (oben links, grün)
- **Motion Mask** (kleines Fenster, unten rechts)
- **Detection Marker** (Kreis an erkannter Position, rot)
- **Score** (Text neben Marker, weiß)
- **Kalibrierungsstatus** (oben rechts, grün/rot)

---

## Preprocessing: CLAHE

CLAHE (Contrast Limited Adaptive Histogram Equalization) wird als Standard-Preprocessing eingesetzt, um bei variablen Lichtverhältnissen robuster zu arbeiten.

| Parameter | Default | Effekt |
|-----------|---------|--------|
| `clipLimit` | 2.0 | Höher = mehr Kontrastverstärkung, aber auch mehr Rauschen |
| `tileGridSize` | (8, 8) | Kleinere Tiles = lokalere Anpassung |

---

## Performance-Optimierungen

1. **Frame Decimation:** Bei CPU-Überlast jeden 2. Frame überspringen
2. **Early Grayscale:** Farbe nur für Debug-Overlay behalten
3. **ROI-Size:** 400×400 px als Default — kleiner = schneller
4. **Kernel Caching:** Morphologische Kernel einmal erstellen, wiederverwenden
5. **Contour-Filter-Early-Out:** Fläche prüfen vor teurer Moment-Berechnung
