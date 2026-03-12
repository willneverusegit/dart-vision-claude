# Refactoring: BoardGeometry als Single Source of Truth (Release 0.3)

> Anweisung fuer einen Coding-Agenten. Lies dieses Dokument vollstaendig,
> bevor du Code aenderst. Pruefe den IST-Zustand jeder Datei vor dem Editieren.

---

## Ziel

`FieldMapper` wird entfernt. Alles Scoring laeuft ueber `BoardGeometry.point_to_score()`.
Das Ergebnis ist ein typsicherer `BoardHit` (frozen dataclass) statt ein loses `dict`.

---

## Kontext: Was bereits existiert

| Datei | Status | Aktion |
|-------|--------|--------|
| `src/cv/geometry.py` | Existiert mit `CameraIntrinsics`, `BoardPose`, `BoardGeometry` (dataclass) | Erweitern |
| `src/cv/field_mapper.py` | Existiert, enthaelt Scoring-Logik | Nach Migration entfernen |
| `src/cv/remapping.py` | Existiert, funktioniert | Keine Aenderung |
| `src/cv/pipeline.py` | Nutzt `FieldMapper` + `BoardGeometry` parallel | Umstellen |
| `src/web/routes.py` | Nutzt Score-Dicts aus Pipeline | Anpassen |
| `tests/test_field_mapper.py` | Unit-Tests fuer FieldMapper | Migrieren zu test_geometry.py |

---

## Schritt 1: Neue Typen in `src/cv/geometry.py`

Fuege diese Typen am Anfang der Datei hinzu (nach den bestehenden Imports).
Die bestehenden Klassen (`CameraIntrinsics`, `BoardPose`, `BoardGeometry`) bleiben erhalten.

```python
from typing import NamedTuple

class PolarCoord(NamedTuple):
    """Normalized polar coordinate on the dartboard."""
    r_norm: float   # 0.0 = center, 1.0 = double-ring outer edge
    theta_deg: float  # 0-360, 0 deg = 12 o'clock, clockwise


@dataclass(frozen=True)
class BoardHit:
    """Complete result of mapping a point to a dartboard score."""
    score: int          # Total points (e.g. 60 for T20, 50 for Bull)
    sector: int         # Base sector value (1-20, or 25 for Bull)
    multiplier: int     # 1, 2, 3 (0 for miss)
    ring: str           # "inner_bull", "outer_bull", "single", "triple", "double", "miss"
    polar: PolarCoord   # Normalized polar position
    board_mm: tuple[float, float]  # (x_mm, y_mm) from board center
    roi_x: float        # Original ROI pixel x
    roi_y: float        # Original ROI pixel y
```

### Modul-Konstanten

Fuege diese Konstanten als Modul-Level hinzu (nicht in einer Klasse):

```python
# Physical dimensions in mm (from center) — WDF/BDO/PDC Standard
BULL_INNER_MM = 6.35
BULL_OUTER_MM = 15.9
TRIPLE_INNER_MM = 99.0
TRIPLE_OUTER_MM = 107.0
DOUBLE_INNER_MM = 162.0
DOUBLE_OUTER_MM = 170.0
BOARD_RADIUS_MM = DOUBLE_OUTER_MM  # 170mm

# Normalized ring boundaries (relative to BOARD_RADIUS_MM)
RING_BOUNDARIES: tuple[tuple[float, float, str, int, int | None], ...] = (
    # (inner_norm, outer_norm, name, multiplier, flat_score_or_None)
    (0.0, BULL_INNER_MM / BOARD_RADIUS_MM, "inner_bull", 1, 50),
    (BULL_INNER_MM / BOARD_RADIUS_MM, BULL_OUTER_MM / BOARD_RADIUS_MM, "outer_bull", 1, 25),
    (BULL_OUTER_MM / BOARD_RADIUS_MM, TRIPLE_INNER_MM / BOARD_RADIUS_MM, "single", 1, None),
    (TRIPLE_INNER_MM / BOARD_RADIUS_MM, TRIPLE_OUTER_MM / BOARD_RADIUS_MM, "triple", 3, None),
    (TRIPLE_OUTER_MM / BOARD_RADIUS_MM, DOUBLE_INNER_MM / BOARD_RADIUS_MM, "single", 1, None),
    (DOUBLE_INNER_MM / BOARD_RADIUS_MM, DOUBLE_OUTER_MM / BOARD_RADIUS_MM, "double", 2, None),
)

SECTOR_ORDER: tuple[int, ...] = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                                  3, 19, 7, 16, 8, 11, 14, 9, 12, 5)
SECTOR_COUNT = 20
SECTOR_ANGLE_DEG = 360.0 / SECTOR_COUNT  # 18 deg
SECTOR_HALF_WIDTH_DEG = SECTOR_ANGLE_DEG / 2.0  # 9 deg
```

---

## Schritt 2: `point_to_score()` Methode in `BoardGeometry`

Fuege diese Methode zur bestehenden `BoardGeometry` dataclass hinzu.
Sie ersetzt `FieldMapper.point_to_score()` komplett.

Die Methode nutzt die bereits vorhandenen Properties `optical_center_px`,
`double_outer_radius_px` und `rotation_deg` der bestehenden Klasse.

```python
def point_to_score(self, x_px: float, y_px: float) -> BoardHit:
    """Convert ROI pixel coordinates to a BoardHit.

    This is the ONLY function external modules should call for scoring.
    """
    radius = self.double_outer_radius_px
    if radius <= 0:
        return BoardHit(
            score=0, sector=0, multiplier=0, ring="miss",
            polar=PolarCoord(0.0, 0.0), board_mm=(0.0, 0.0),
            roi_x=x_px, roi_y=y_px,
        )

    ox, oy = self.optical_center_px
    dx = x_px - ox
    dy = y_px - oy
    distance_px = math.hypot(dx, dy)
    r_norm = distance_px / radius

    # Angle: 0 deg at 12 o'clock, clockwise
    angle_deg = (math.degrees(math.atan2(dy, dx)) + 90.0 + self.rotation_deg) % 360.0
    polar = PolarCoord(r_norm=r_norm, theta_deg=angle_deg)

    # mm calculation (use physical proportions)
    mm_per_px = BOARD_RADIUS_MM / radius
    board_mm = (dx * mm_per_px, dy * mm_per_px)

    # Ring classification
    ring_name = "miss"
    multiplier = 0
    flat_score: int | None = None
    for inner, outer, name, mult, flat in RING_BOUNDARIES:
        if inner <= r_norm < outer:
            ring_name = name
            multiplier = mult
            flat_score = flat
            break

    if multiplier == 0:
        return BoardHit(
            score=0, sector=0, multiplier=0, ring="miss",
            polar=polar, board_mm=board_mm, roi_x=x_px, roi_y=y_px,
        )

    if flat_score is not None:
        return BoardHit(
            score=flat_score, sector=25, multiplier=1, ring=ring_name,
            polar=polar, board_mm=board_mm, roi_x=x_px, roi_y=y_px,
        )

    # Sector classification
    adjusted = (angle_deg + SECTOR_HALF_WIDTH_DEG) % 360.0
    sector_index = int(adjusted / SECTOR_ANGLE_DEG) % SECTOR_COUNT
    sector_value = SECTOR_ORDER[sector_index]

    return BoardHit(
        score=sector_value * multiplier,
        sector=sector_value,
        multiplier=multiplier,
        ring=ring_name,
        polar=polar,
        board_mm=board_mm,
        roi_x=x_px,
        roi_y=y_px,
    )
```

### Kompatibilitaets-Helper

Fuege auch diese Methode hinzu, damit bestehender Code, der Dicts erwartet,
schrittweise migriert werden kann:

```python
def hit_to_dict(self, hit: BoardHit) -> dict:
    """Convert BoardHit to legacy dict format for API/WebSocket compatibility."""
    return {
        "score": hit.score,
        "sector": hit.sector,
        "multiplier": hit.multiplier,
        "ring": hit.ring,
        "normalized_distance": round(hit.polar.r_norm, 4),
        "angle_deg": round(hit.polar.theta_deg, 2),
        "roi_x": hit.roi_x,
        "roi_y": hit.roi_y,
        "board_x_norm": round(hit.board_mm[0] / BOARD_RADIUS_MM, 4) if BOARD_RADIUS_MM > 0 else 0.0,
        "board_y_norm": round(hit.board_mm[1] / BOARD_RADIUS_MM, 4) if BOARD_RADIUS_MM > 0 else 0.0,
        "polar_radius_norm": round(hit.polar.r_norm, 4),
        "polar_angle_deg": round(hit.polar.theta_deg, 2),
    }
```

---

## Schritt 3: Pipeline umstellen (`src/cv/pipeline.py`)

### 3a: Import aendern

```python
# ENTFERNEN:
from src.cv.field_mapper import FieldMapper

# HINZUFUEGEN (falls nicht schon importiert):
from src.cv.geometry import BoardGeometry, BoardHit
```

### 3b: `__init__` bereinigen

- Entferne: `self.field_mapper = FieldMapper()`
- Entferne: Alle Backward-Compat-Aliases die auf field_mapper verweisen

### 3c: `process_frame()` anpassen

Ersetze den Scoring-Block (aktuell Zeilen ~158-178) durch:

```python
# 5) Scoring via BoardGeometry
geometry = self.geometry or self.board_calibration.get_geometry()
hit = geometry.point_to_score(detection.center[0], detection.center[1])
score_result = geometry.hit_to_dict(hit)

if self.on_dart_detected:
    self.on_dart_detected(score_result, detection)

self._last_score = score_result
```

Das `score_result` dict hat das gleiche Format wie vorher — das Frontend
und die WebSocket-Events brauchen keine Aenderung.

### 3d: `start()` bereinigen

Entferne die `field_mapper.set_ring_radii_px()` Zeilen. Das Scoring
nutzt jetzt die physikalischen Konstanten aus `geometry.py`, nicht
kalibrierte Pixel-Radien.

### 3e: `_draw_field_overlay()` anpassen

Ersetze `self.field_mapper.ring_radii.values()` durch die Modul-Konstanten:

```python
ring_fractions = [b[1] for b in RING_BOUNDARIES]  # outer boundaries
```

Importiere `RING_BOUNDARIES` aus `src.cv.geometry`.

---

## Schritt 4: Tests migrieren

### 4a: `tests/test_geometry.py` erstellen (oder erweitern falls vorhanden)

Migriere die Testfaelle aus `tests/test_field_mapper.py`:

```python
import math
import pytest
from src.cv.geometry import BoardGeometry, BoardHit, BoardPose, PolarCoord

@pytest.fixture
def geometry() -> BoardGeometry:
    """Standard 400x400 ROI with center at (200, 200)."""
    pose = BoardPose(
        homography=None,
        center_px=(200.0, 200.0),
        radii_px=(10.0, 19.0, 106.0, 116.0, 188.0, 200.0),
        rotation_deg=0.0,
        valid=True,
    )
    return BoardGeometry.from_pose(pose, roi_size=(400, 400))


class TestPointToScore:
    def test_bullseye(self, geometry: BoardGeometry) -> None:
        hit = geometry.point_to_score(200.0, 200.0)
        assert hit.score == 50
        assert hit.ring == "inner_bull"
        assert hit.multiplier == 1

    def test_outer_bull(self, geometry: BoardGeometry) -> None:
        # Punkt knapp ausserhalb inner bull, aber innerhalb outer bull
        hit = geometry.point_to_score(200.0, 200.0 - 12.0)
        assert hit.score == 25
        assert hit.ring == "outer_bull"

    def test_triple_20(self, geometry: BoardGeometry) -> None:
        # 20 ist oben (12 Uhr), Triple-Ring bei ~110px vom Center
        hit = geometry.point_to_score(200.0, 200.0 - 110.0)
        assert hit.sector == 20
        assert hit.multiplier == 3
        assert hit.score == 60
        assert hit.ring == "triple"

    def test_double_20(self, geometry: BoardGeometry) -> None:
        # Double-Ring bei ~195px vom Center
        hit = geometry.point_to_score(200.0, 200.0 - 195.0)
        assert hit.sector == 20
        assert hit.multiplier == 2
        assert hit.score == 40

    def test_miss(self, geometry: BoardGeometry) -> None:
        # Weit ausserhalb
        hit = geometry.point_to_score(200.0, 200.0 - 250.0)
        assert hit.score == 0
        assert hit.ring == "miss"

    def test_single_sector(self, geometry: BusinessGeometry) -> None:
        # Rechts vom Center = Sektor 6 (3-Uhr-Position)
        hit = geometry.point_to_score(200.0 + 150.0, 200.0)
        assert hit.sector == 6
        assert hit.multiplier == 1
        assert hit.ring == "single"

    def test_returns_board_hit_type(self, geometry: BoardGeometry) -> None:
        hit = geometry.point_to_score(200.0, 200.0)
        assert isinstance(hit, BoardHit)
        assert isinstance(hit.polar, PolarCoord)

    def test_board_mm_populated(self, geometry: BoardGeometry) -> None:
        hit = geometry.point_to_score(200.0, 100.0)
        assert hit.board_mm[1] < 0  # above center = negative y in mm

    def test_hit_to_dict_keys(self, geometry: BoardGeometry) -> None:
        hit = geometry.point_to_score(200.0, 200.0)
        d = geometry.hit_to_dict(hit)
        required_keys = {"score", "sector", "multiplier", "ring",
                         "normalized_distance", "angle_deg", "roi_x", "roi_y"}
        assert required_keys.issubset(d.keys())
```

ACHTUNG: Der Test `test_single_sector` hat einen Tippfehler (`BusinessGeometry`).
Korrigiere zu `BoardGeometry`.

### 4b: `tests/test_field_mapper.py` entfernen

Erst entfernen wenn alle Tests in `test_geometry.py` gruen sind.

---

## Schritt 5: Aufraeum-Arbeiten

### 5a: `src/cv/field_mapper.py` loeschen

### 5b: Alle Imports bereinigen

Suche im gesamten Projekt nach:
```
from src.cv.field_mapper import
```
und entferne/ersetze sie.

### 5c: `src/cv/__init__.py` anpassen

Exportiere `BoardHit` und `PolarCoord` aus dem Paket falls noetig.

---

## Validierung

Nach Abschluss muessen diese Checks bestehen:

```bash
# Alle Tests gruen
python -m pytest tests/ -v

# Kein Import von field_mapper mehr vorhanden
grep -r "field_mapper" src/ tests/

# Pipeline startet ohne Fehler
python -m src.cv.pipeline --source 0 --debug

# Linting
ruff check src/ tests/
```

---

## Was NICHT geaendert wird

- `CombinedRemapper` (`remapping.py`) — funktioniert bereits
- `CameraIntrinsics` / `BoardPose` — bleiben wie sie sind
- `calibration.py`, `board_calibration.py`, `camera_calibration.py` — keine Aenderung
- Frontend (HTML/JS/CSS) — keine Aenderung (Dict-Format bleibt kompatibel)
- `src/web/routes.py` — keine Aenderung noetig (nutzt Score-Dicts)
- Frame-Speicherung (`_last_raw_frame`) — bleibt fuer Video-Stream noetig
