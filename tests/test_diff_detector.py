import json
import os

import numpy as np
import pytest
from src.cv.diff_detector import FrameDiffDetector


def _gray(val: int, size: int = 100) -> np.ndarray:
    return np.full((size, size), val, dtype=np.uint8)


def test_idle_no_motion_returns_none():
    d = FrameDiffDetector()
    result = d.update(_gray(128), has_motion=False)
    assert result is None


def test_idle_updates_baseline():
    d = FrameDiffDetector()
    d.update(_gray(50), has_motion=False)
    d.update(_gray(200), has_motion=False)
    assert np.array_equal(d._baseline, _gray(200))


def test_motion_triggers_in_motion_state():
    d = FrameDiffDetector()
    d.update(_gray(128), has_motion=False)
    d.update(_gray(128), has_motion=True)
    assert d.state == "in_motion"


def test_no_motion_after_in_motion_starts_settling():
    d = FrameDiffDetector()
    d.update(_gray(128), has_motion=False)
    d.update(_gray(128), has_motion=True)
    d.update(_gray(128), has_motion=False)
    assert d.state == "settling"


def test_motion_during_settling_reverts_to_in_motion():
    d = FrameDiffDetector(settle_frames=5)
    d.update(_gray(128), has_motion=False)
    d.update(_gray(128), has_motion=True)
    d.update(_gray(128), has_motion=False)  # → settling
    d.update(_gray(128), has_motion=True)   # Dart wackelt
    assert d.state == "in_motion"


def test_settling_returns_detection_and_back_to_idle():
    """settle_frames=2: 1 Frame in SETTLING zählt auf 1, zweiter löst Diff aus."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, min_elongation=1.0)
    baseline = _gray(50)
    dart_frame = _gray(50)
    dart_frame[40:60, 40:60] = 200  # Dart-Blob einfügen (20x20=400px²)

    d.update(baseline, has_motion=False)   # IDLE, Baseline = 50
    d.update(dart_frame, has_motion=True)  # → IN_MOTION
    d.update(dart_frame, has_motion=False) # → SETTLING, count=1
    result = d.update(dart_frame, has_motion=False)  # count=2 → Diff
    assert result is not None
    assert d.state == "idle"


def test_reset_clears_all_state():
    d = FrameDiffDetector()
    d.update(_gray(128), has_motion=False)
    d.update(_gray(128), has_motion=True)
    d.reset()
    assert d.state == "idle"
    assert d._baseline is None
    assert d._settle_count == 0


def test_diff_detects_new_blob():
    """Klarer Dart-Blob wird korrekt erkannt und Centroid stimmt."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=30, min_diff_area=50, min_elongation=1.0)
    baseline = _gray(100)
    post = _gray(100)
    post[45:65, 45:65] = 200  # 20x20 px = 400 px²
    d.update(baseline, has_motion=False)
    d.update(post, has_motion=True)
    d.update(post, has_motion=False)
    result = d.update(post, has_motion=False)
    assert result is not None
    assert abs(result.center[0] - 55) < 5
    assert abs(result.center[1] - 55) < 5


def test_diff_ignores_tiny_blobs():
    """Rauschartefakt unter min_diff_area wird ignoriert."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=30, min_diff_area=200)
    baseline = _gray(100)
    post = _gray(100)
    post[50, 50] = 200  # 1px — zu klein
    d.update(baseline, has_motion=False)
    d.update(post, has_motion=True)
    d.update(post, has_motion=False)
    result = d.update(post, has_motion=False)
    assert result is None


def test_diff_ignores_global_brightness_change():
    """Globale Beleuchtungsänderung überschreitet max_diff_area → kein Treffer."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=30, max_diff_area=5000)
    baseline = _gray(100, size=200)
    post = _gray(160, size=200)  # ganzes 200x200 = 40000 px² → zu groß
    d.update(baseline, has_motion=False)
    d.update(post, has_motion=True)
    d.update(post, has_motion=False)
    result = d.update(post, has_motion=False)
    assert result is None


def test_compute_diff_without_baseline_returns_none():
    """_compute_diff ohne Baseline darf nicht crashen."""
    d = FrameDiffDetector()
    # _baseline ist None nach Initialisierung
    result = d._compute_diff(_gray(128))
    assert result is None


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        FrameDiffDetector(settle_frames=0)
    with pytest.raises(ValueError):
        FrameDiffDetector(diff_threshold=0)
    with pytest.raises(ValueError):
        FrameDiffDetector(diff_threshold=256)
    with pytest.raises(ValueError):
        FrameDiffDetector(min_diff_area=100, max_diff_area=100)


def test_second_dart_uses_updated_baseline():
    """Nach erstem Treffer wird Baseline neu gesetzt — zweiter Dart korrekt erkannt."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, min_elongation=1.0)
    empty = _gray(50)
    dart1 = _gray(50)
    dart1[20:30, 20:30] = 200

    # Erster Dart
    d.update(empty, has_motion=False)
    d.update(dart1, has_motion=True)
    d.update(dart1, has_motion=False)
    r1 = d.update(dart1, has_motion=False)
    assert r1 is not None
    assert d.state == "idle"

    # Zweiter Dart (anderer Ort, Baseline enthält jetzt dart1)
    dart2 = dart1.copy()
    dart2[70:80, 70:80] = 200
    d.update(dart1, has_motion=False)  # Baseline = dart1 (erster Dart steckt noch)
    d.update(dart2, has_motion=True)
    d.update(dart2, has_motion=False)
    r2 = d.update(dart2, has_motion=False)
    assert r2 is not None
    # Centroid sollte beim zweiten Blob liegen (~75, 75)
    assert abs(r2.center[0] - 75) < 8
    assert abs(r2.center[1] - 75) < 8


def test_color_frame_raises():
    """Color frame must raise ValueError, not silently fail."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10)
    color = np.full((100, 100, 3), 128, dtype=np.uint8)
    d.update(np.full((100, 100), 100, dtype=np.uint8), has_motion=False)  # grayscale baseline
    with pytest.raises(ValueError, match="grayscale"):
        d._compute_diff(color)


# ------------------------------------------------------------------
# Diagnostics tests (P20)
# ------------------------------------------------------------------


def test_diagnostics_saves_files_on_detection(tmp_path):
    """When diagnostics_dir is set, detection saves PNG + JSON files."""
    diag_dir = str(tmp_path / "diag")
    d = FrameDiffDetector(
        settle_frames=2, diff_threshold=10, min_diff_area=10,
        diagnostics_dir=diag_dir, min_elongation=1.0,
    )
    baseline = _gray(50)
    post = _gray(50)
    post[40:60, 40:60] = 200

    d.update(baseline, has_motion=False)
    d.update(post, has_motion=True)
    d.update(post, has_motion=False)
    result = d.update(post, has_motion=False)

    assert result is not None
    files = os.listdir(diag_dir)
    suffixes = {f.rsplit("_", 1)[-1] for f in files}
    assert "diff.png" in suffixes
    assert "thresh.png" in suffixes
    assert "contour.png" in suffixes
    assert "baseline.png" in suffixes
    assert "meta.json" in suffixes

    # Verify metadata content
    meta_file = [f for f in files if f.endswith("meta.json")][0]
    with open(os.path.join(diag_dir, meta_file)) as f:
        meta = json.load(f)
    assert "centroid" in meta
    assert "area" in meta
    assert "min_area_rect" in meta
    assert meta["settings"]["settle_frames"] == 2


def test_diagnostics_disabled_by_default():
    """Without diagnostics_dir, no files are written."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10)
    assert d._diagnostics_dir is None


def test_diagnostics_does_not_block_detection(tmp_path):
    """Even with diagnostics, detection result is still returned correctly."""
    diag_dir = str(tmp_path / "diag")
    d = FrameDiffDetector(
        settle_frames=2, diff_threshold=30, min_diff_area=50,
        diagnostics_dir=diag_dir, min_elongation=1.0,
    )
    baseline = _gray(100)
    post = _gray(100)
    post[45:65, 45:65] = 200

    d.update(baseline, has_motion=False)
    d.update(post, has_motion=True)
    d.update(post, has_motion=False)
    result = d.update(post, has_motion=False)

    assert result is not None
    assert abs(result.center[0] - 55) < 5
    assert abs(result.center[1] - 55) < 5


# ------------------------------------------------------------------
# Elongation filter & contour robustness tests (P21)
# ------------------------------------------------------------------


def _run_detection(detector, baseline, post):
    """Helper: run full IDLE->IN_MOTION->SETTLING->detect cycle."""
    detector.update(baseline, has_motion=False)
    detector.update(post, has_motion=True)
    detector.update(post, has_motion=False)
    return detector.update(post, has_motion=False)


def test_elongation_filter_rejects_circular_blob():
    """A square-ish diff blob (aspect ~1.0) is rejected by the elongation filter."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, min_elongation=1.5)
    baseline = _gray(50)
    post = _gray(50)
    post[40:60, 40:60] = 200  # 20x20 square blob
    result = _run_detection(d, baseline, post)
    assert result is None


def test_elongation_filter_accepts_dart_shaped_blob():
    """An elongated blob (tall and narrow) passes the elongation filter."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, min_elongation=1.5)
    baseline = _gray(50)
    post = _gray(50)
    post[20:80, 48:54] = 200  # 60x6 elongated blob
    result = _run_detection(d, baseline, post)
    assert result is not None


def test_closing_fills_gaps_in_contour():
    """A dart contour with a 5px gap in the middle still gets detected."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, min_elongation=1.5)
    baseline = _gray(50)
    post = _gray(50)
    post[20:45, 48:54] = 200  # top segment
    # gap at rows 45-50
    post[50:80, 48:54] = 200  # bottom segment
    result = _run_detection(d, baseline, post)
    assert result is not None


def test_shadow_artifact_rejected():
    """A large diffuse blob exceeding max_diff_area is rejected."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, max_diff_area=5000, min_elongation=1.5)
    baseline = _gray(50, size=200)
    post = _gray(50, size=200)
    post[60:140, 60:140] = 120  # 80x80 = 6400 px² > max_diff_area
    result = _run_detection(d, baseline, post)
    assert result is None


def test_configurable_elongation_threshold():
    """Setting min_elongation=1.0 accepts everything including square blobs."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, min_elongation=1.0)
    baseline = _gray(50)
    post = _gray(50)
    post[40:60, 40:60] = 200  # square blob
    result = _run_detection(d, baseline, post)
    assert result is not None


def test_invalid_min_elongation_raises():
    """min_elongation < 1.0 raises ValueError."""
    with pytest.raises(ValueError, match="min_elongation"):
        FrameDiffDetector(min_elongation=0.5)


# ------------------------------------------------------------------
# Board-wire filtering & morphology pipeline tests (Tier 1 Opt)
# ------------------------------------------------------------------


def test_board_wire_filtered_by_opening():
    """Thin 1px-wide wire artefacts in the diff should be removed by opening."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, min_elongation=1.0)
    baseline = _gray(50)
    post = _gray(50)
    # Simulate thin board wire: 1px wide horizontal line
    post[50, 10:90] = 200  # 1px tall, 80px wide — should be removed by opening
    result = _run_detection(d, baseline, post)
    assert result is None, "Thin wire artefact should be filtered by morphological opening"


def test_elongated_closing_connects_dart_fragments():
    """A dart shaft with a 8px gap should be connected by elongated closing kernel."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=10, min_elongation=1.5)
    baseline = _gray(50)
    post = _gray(50)
    # Two dart shaft segments with 8px gap (larger than 5x5 ellipse can close)
    post[15:40, 48:54] = 200   # top segment
    # gap at rows 40-48
    post[48:80, 48:54] = 200   # bottom segment
    result = _run_detection(d, baseline, post)
    assert result is not None, "Elongated closing should connect 8px gap in dart shaft"


def test_outer_bull_small_blob_detected():
    """A small ~56px² blob (outer bull area) should be detected with min_diff_area=30."""
    d = FrameDiffDetector(settle_frames=2, diff_threshold=10, min_diff_area=30, min_elongation=1.0)
    baseline = _gray(50)
    post = _gray(50)
    # Small blob: 8x7 = 56 px² — simulates outer bull dart tip (survives 2x2 opening)
    post[46:54, 47:54] = 200
    result = _run_detection(d, baseline, post)
    assert result is not None, "56px² blob should pass min_diff_area=30"


def test_default_min_diff_area_is_30():
    """Default min_diff_area should be 30 (lowered for outer bull detection)."""
    d = FrameDiffDetector()
    assert d.min_diff_area == 30
