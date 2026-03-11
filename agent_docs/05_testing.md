# Testing: Protokoll, Akzeptanzkriterien, Mock-Strategien

> Lies dieses Dokument, wenn du an `tests/` arbeitest.

---

## Test-Strategie

### Test-Pyramide
```
           ┌────────┐
           │  E2E   │  ← Integration: Pipeline + Game + Web
          ┌┴────────┴┐
          │  Integr.  │  ← Pipeline Tests mit Mock-Frames
         ┌┴──────────┴┐
         │   Unit      │  ← Jedes Modul einzeln
         └─────────────┘
```

### Frameworks
- **pytest** — Test-Runner
- **pytest-cov** — Coverage (Ziel: ≥ 80%)
- **pytest-asyncio** — Für FastAPI WebSocket Tests (optional)
- **unittest.mock** — Für Mock-Kamera, Mock-Frames

---

## Unit Tests

### `tests/test_field_mapper.py`

Kritischster Test: Die Scoring-Logik muss mathematisch korrekt sein.

```python
import pytest
from src.cv.field_mapper import FieldMapper


@pytest.fixture
def mapper():
    return FieldMapper()


class TestFieldMapper:
    """Test dartboard sector and ring mapping."""

    def test_inner_bull(self, mapper):
        """Point at exact center should be Inner Bull (50)."""
        result = mapper.point_to_score(200, 200, 200, 200, 200)
        assert result["score"] == 50
        assert result["ring"] == "inner_bull"

    def test_outer_bull(self, mapper):
        """Point just outside inner bull should be Outer Bull (25)."""
        # At 1.5% of radius from center (between 0.05 inner and 0.095 outer)
        x = 200 + 200 * 0.07  # 7% of radius
        result = mapper.point_to_score(x, 200, 200, 200, 200)
        assert result["score"] == 25
        assert result["ring"] == "outer_bull"

    def test_single_20_top(self, mapper):
        """Point at 12 o'clock in single area should be 20."""
        # Single zone: 0.095 < r < 0.53
        y = 200 - 200 * 0.3  # 30% radius, straight up
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["sector"] == 20
        assert result["multiplier"] == 1
        assert result["score"] == 20

    def test_triple_20(self, mapper):
        """Point in triple ring at 12 o'clock should be T20 (60)."""
        y = 200 - 200 * 0.55  # 55% radius (triple zone: 0.53–0.58)
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["sector"] == 20
        assert result["multiplier"] == 3
        assert result["score"] == 60

    def test_double_20(self, mapper):
        """Point in double ring at 12 o'clock should be D20 (40)."""
        y = 200 - 200 * 0.97  # 97% radius (double zone: 0.94–1.00)
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["sector"] == 20
        assert result["multiplier"] == 2
        assert result["score"] == 40

    def test_miss_outside_board(self, mapper):
        """Point outside board should be miss (0)."""
        y = 200 - 200 * 1.05  # 105% radius
        result = mapper.point_to_score(200, y, 200, 200, 200)
        assert result["score"] == 0
        assert result["ring"] == "miss"

    def test_all_20_sectors_accessible(self, mapper):
        """Each of the 20 sectors should be reachable by angle."""
        found_sectors = set()
        for angle_deg in range(0, 360, 18):
            import math
            rad = math.radians(angle_deg)
            r = 0.3  # Single area
            x = 200 + 200 * r * math.cos(rad)
            y = 200 + 200 * r * math.sin(rad)
            result = mapper.point_to_score(x, y, 200, 200, 200)
            found_sectors.add(result["sector"])
        assert len(found_sectors) == 20

    def test_sector_order(self, mapper):
        """Verify sector order matches standard dartboard layout."""
        expected = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                    3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
        assert mapper.SECTOR_ORDER == expected

    def test_zero_radius_no_crash(self, mapper):
        """Passing zero radius should not crash."""
        result = mapper.point_to_score(100, 100, 100, 100, 0)
        assert result["ring"] == "miss"
```

### `tests/test_detector.py`

```python
import pytest
import numpy as np
from src.cv.detector import DartImpactDetector, DartDetection


@pytest.fixture
def detector():
    return DartImpactDetector(confirmation_frames=3, position_tolerance_px=20)


class TestDartImpactDetector:
    def _make_mask_with_blob(self, center: tuple[int, int], radius: int = 15,
                              size: tuple[int, int] = (400, 400)) -> np.ndarray:
        """Create a motion mask with a white blob (simulated dart)."""
        import cv2
        mask = np.zeros(size, dtype=np.uint8)
        cv2.circle(mask, center, radius, 255, -1)
        return mask

    def test_no_detection_without_motion(self, detector):
        """Empty motion mask should return None."""
        empty_mask = np.zeros((400, 400), dtype=np.uint8)
        roi = np.zeros((400, 400), dtype=np.uint8)
        result = detector.detect(roi, empty_mask)
        assert result is None

    def test_single_frame_no_confirmation(self, detector):
        """Single frame with dart should not confirm (need 3 frames)."""
        mask = self._make_mask_with_blob((200, 200))
        roi = np.zeros((400, 400), dtype=np.uint8)
        result = detector.detect(roi, mask)
        assert result is None  # Only 1 frame, need 3

    def test_confirmation_after_3_frames(self, detector):
        """Dart at same position for 3 frames should be confirmed."""
        mask = self._make_mask_with_blob((200, 200))
        roi = np.zeros((400, 400), dtype=np.uint8)

        # Frame 1 and 2: no confirmation yet
        detector.detect(roi, mask)
        detector.detect(roi, mask)

        # Frame 3: should confirm
        result = detector.detect(roi, mask)
        assert result is not None
        assert isinstance(result, DartDetection)
        assert result.frame_count >= 3

    def test_moving_object_no_confirmation(self, detector):
        """Object moving between frames should not confirm."""
        roi = np.zeros((400, 400), dtype=np.uint8)

        # Different positions each frame
        for pos in [(100, 100), (200, 200), (300, 300)]:
            mask = self._make_mask_with_blob(pos)
            result = detector.detect(roi, mask)

        assert result is None  # Positions differ too much

    def test_reset_clears_state(self, detector):
        """Reset should clear all candidates and confirmations."""
        mask = self._make_mask_with_blob((200, 200))
        roi = np.zeros((400, 400), dtype=np.uint8)

        detector.detect(roi, mask)
        detector.detect(roi, mask)
        detector.reset()

        # After reset, should need 3 new frames
        result = detector.detect(roi, mask)
        assert result is None
```

### `tests/test_game_engine.py`

```python
import pytest
from src.game.engine import GameEngine


@pytest.fixture
def engine():
    return GameEngine()


class TestX01:
    def test_new_game_501(self, engine):
        engine.new_game(mode="x01", players=["Alice", "Bob"], starting_score=501)
        state = engine.get_state()
        assert state["mode"] == "x01"
        assert state["scores"]["Alice"] == 501
        assert state["scores"]["Bob"] == 501

    def test_score_subtraction(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=501)
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        state = engine.get_state()
        assert state["scores"]["Alice"] == 441

    def test_bust_below_zero(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=50)
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        state = engine.get_state()
        # Should bust: score reset to 50
        assert state["scores"]["Alice"] == 50

    def test_double_out_win(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=40)
        engine.register_throw({"score": 40, "sector": 20, "multiplier": 2, "ring": "double"})
        state = engine.get_state()
        assert state["winner"] == "Alice"
        assert state["phase"] == "game_over"

    def test_non_double_finish_busts(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=20)
        engine.register_throw({"score": 20, "sector": 20, "multiplier": 1, "ring": "single"})
        state = engine.get_state()
        assert state["scores"]["Alice"] == 20  # Bust, not 0
        assert state["winner"] is None

    def test_undo(self, engine):
        engine.new_game(mode="x01", players=["Alice"], starting_score=501)
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        assert engine.get_state()["scores"]["Alice"] == 441
        engine.undo_last_throw()
        assert engine.get_state()["scores"]["Alice"] == 501

    def test_three_darts_completes_turn(self, engine):
        engine.new_game(mode="x01", players=["Alice", "Bob"], starting_score=501)
        for _ in range(3):
            engine.register_throw({"score": 20, "sector": 20, "multiplier": 1, "ring": "single"})
        # After 3 darts, turn should auto-complete
        state = engine.get_state()
        assert state["darts_thrown"] == 0  # New turn


class TestCricket:
    def test_mark_number(self, engine):
        engine.new_game(mode="cricket", players=["Alice"])
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        state = engine.get_state()
        assert state["players"][0]["cricket_marks"][20] == 3  # Closed

    def test_score_on_open_number(self, engine):
        engine.new_game(mode="cricket", players=["Alice", "Bob"])
        # Alice triples 20 (closes it)
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        # Alice scores another 20 (Bob hasn't closed it)
        engine.register_throw({"score": 20, "sector": 20, "multiplier": 1, "ring": "single"})
        state = engine.get_state()
        assert state["scores"]["Alice"] == 20  # Scored on open number


class TestFreePlay:
    def test_score_accumulates(self, engine):
        engine.new_game(mode="free", players=["Alice"])
        engine.register_throw({"score": 60, "sector": 20, "multiplier": 3, "ring": "triple"})
        engine.register_throw({"score": 25, "sector": 25, "multiplier": 1, "ring": "outer_bull"})
        state = engine.get_state()
        assert state["scores"]["Alice"] == 85
```

### `tests/test_calibration.py`

```python
import pytest
import os
import tempfile
import numpy as np
from src.cv.calibration import CalibrationManager


@pytest.fixture
def calib_manager(tmp_path):
    config_path = str(tmp_path / "test_calib.yaml")
    return CalibrationManager(config_path=config_path)


class TestCalibration:
    def test_initial_state_invalid(self, calib_manager):
        assert not calib_manager.is_valid()
        assert calib_manager.get_homography() is None

    def test_manual_calibration(self, calib_manager):
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        result = calib_manager.manual_calibration(points)
        assert result["ok"]
        assert calib_manager.is_valid()
        assert calib_manager.get_homography() is not None

    def test_config_persistence(self, calib_manager):
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        calib_manager.manual_calibration(points)

        # Load fresh manager from same config
        manager2 = CalibrationManager(config_path=calib_manager.config_path)
        assert manager2.is_valid()
        np.testing.assert_array_almost_equal(
            manager2.get_homography(),
            calib_manager.get_homography()
        )

    def test_atomic_write_creates_file(self, calib_manager):
        points = [[100, 100], [300, 100], [300, 300], [100, 300]]
        calib_manager.manual_calibration(points)
        assert os.path.exists(calib_manager.config_path)
```

---

## Akzeptanzkriterien (Vollständige Matrix)

| Kategorie | Metrik | Testbedingungen | Akzeptanz |
|-----------|--------|----------------|-----------|
| FPS | Median FPS | 60s kontinuierlich, 720p | ≥ 15 FPS |
| FPS | P95 FPS | 60s kontinuierlich, 720p | ≥ 10 FPS |
| Latenz | End-to-End | Frame → Score Result | ≤ 200ms |
| Latenz | Processing only | Ohne Capture | ≤ 100ms |
| Genauigkeit | Hit Error RMS | 20 Darts, Ground Truth | ≤ 10mm |
| Genauigkeit | Hit Error Max | 20 Darts, Ground Truth | ≤ 25mm |
| Qualität | False Positive Rate | 100 Frames ohne Darts | ≤ 5% |
| Qualität | False Negative Rate | 50 Frames mit Darts | ≤ 10% |
| Robustheit | Beleuchtung | Normal/Dim/Bright | < 20% Degradation |
| System | CPU Usage | Durchschnitt, 60s | ≤ 70% |
| System | Memory | Peak | ≤ 512 MB |

---

## Performance-Benchmark-Script

Erstelle `tests/benchmark_pipeline.py`:

```python
"""
Performance benchmark for the CV pipeline.
Run: python -m tests.benchmark_pipeline --source 0 --duration 60
"""

import time
import argparse
import statistics
import psutil
from src.cv.pipeline import DartPipeline
from src.utils.fps import FPSCounter


def run_benchmark(source: int = 0, duration: int = 60) -> dict:
    pipeline = DartPipeline(camera_src=source, debug=False)
    pipeline.start()

    fps_counter = FPSCounter(window_size=100)
    frame_times = []
    process = psutil.Process()
    cpu_samples = []

    start_time = time.time()

    while time.time() - start_time < duration:
        frame_start = time.perf_counter()
        pipeline.process_frame()
        frame_end = time.perf_counter()

        frame_times.append(frame_end - frame_start)
        fps_counter.update()
        cpu_samples.append(process.cpu_percent(interval=None))

    pipeline.stop()

    # Calculate metrics
    frame_times_sorted = sorted(frame_times)
    n = len(frame_times_sorted)

    results = {
        "duration_s": duration,
        "total_frames": n,
        "fps_median": 1.0 / statistics.median(frame_times) if frame_times else 0,
        "fps_p95": 1.0 / frame_times_sorted[int(n * 0.95)] if n > 0 else 0,
        "latency_median_ms": statistics.median(frame_times) * 1000,
        "latency_p95_ms": frame_times_sorted[int(n * 0.95)] * 1000 if n > 0 else 0,
        "cpu_avg_percent": statistics.mean(cpu_samples) if cpu_samples else 0,
        "cpu_max_percent": max(cpu_samples) if cpu_samples else 0,
    }

    # Print report
    print("\n=== Pipeline Benchmark Results ===")
    for key, value in results.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    # Check KPIs
    print("\n=== KPI Check ===")
    checks = [
        ("Median FPS ≥ 15", results["fps_median"] >= 15),
        ("P95 FPS ≥ 10", results["fps_p95"] >= 10),
        ("Latency ≤ 200ms", results["latency_p95_ms"] <= 200),
        ("CPU ≤ 70%", results["cpu_avg_percent"] <= 70),
    ]
    for name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=int, default=0)
    parser.add_argument("--duration", type=int, default=60)
    args = parser.parse_args()
    run_benchmark(args.source, args.duration)
```

---

## Mock-Strategien

### Mock-Kamera (`tests/conftest.py`)

```python
import pytest
import numpy as np


@pytest.fixture
def mock_frame():
    """Generate a 720p black frame."""
    return np.zeros((720, 1280, 3), dtype=np.uint8)


@pytest.fixture
def mock_frame_with_circle(mock_frame):
    """Generate a frame with a white circle (simulated dartboard)."""
    import cv2
    frame = mock_frame.copy()
    cv2.circle(frame, (640, 360), 300, (255, 255, 255), 2)
    return frame


@pytest.fixture
def mock_roi_frame():
    """Generate a 400x400 ROI frame."""
    return np.zeros((400, 400), dtype=np.uint8)


@pytest.fixture
def mock_calibration_config(tmp_path):
    """Generate a temporary calibration config."""
    import yaml
    config = {
        "center_px": [200, 200],
        "mm_per_px": 0.85,
        "homography": np.eye(3).tolist(),
        "valid": True,
        "method": "manual",
    }
    config_path = str(tmp_path / "test_config.yaml")
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path
```

---

## Reproduzierbarkeitsanforderungen

- **Feste Seeds:** `np.random.seed(42)` für alle stochastischen Operationen
- **Config Snapshots:** Jeder Testlauf speichert die verwendete Konfiguration
- **Structured Logging:** JSON-formatierte Logs mit Zeitstempeln
- **Deterministische Tests:** Keine Abhängigkeit von Kamera oder externen Ressourcen in Unit-Tests
