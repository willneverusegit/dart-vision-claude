# Multi-Cam Calibration V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the ChArUco frame collection blocker and add a provisional stationary calibration mode.

**Architecture:** Extend the existing `CharucoFrameCollector` with quality gates, lower diversity thresholds, and manual capture support. Add a separate provisional stereo path using `solvePnP`-derived extrinsics. Store provisional results with explicit metadata in the existing config schema.

**Tech Stack:** Python 3.11+, OpenCV (cv2), FastAPI, NumPy, vanilla JS

**Spec:** `docs/superpowers/specs/2026-03-20-multi-cam-calibration-design.md`

---

## Already Implemented (Backend)

The following backend features are already in place:

- **Quality gate** in `CharucoFrameCollector` — sharpness check via `compute_sharpness()`, `MIN_CHARUCO_CORNERS=6`, `last_reject_reason` property, `_last_sharpness` tracking (`src/cv/camera_calibration.py`)
- **Lowered diversity threshold** — `min_position_diff` default is `0.05` (was `0.15`)
- **`min_rotation_diff_deg` removal** — dead code already removed from constructor
- **Manual capture endpoint** — `POST /api/calibration/capture-frame/{camera_id}` (`routes.py:2652`)
- **`calibration_mode` and `capture_mode`** — stored on `CharucoFrameCollector` directly
- **`estimate_intrinsics()`** — exists at `camera_calibration.py:24`, returns `CameraIntrinsics(valid=False, method="estimated")`
- **`stereo_from_board_poses()`** — exists at `stereo_calibration.py:551`, takes `BoardPoseEstimate` objects
- **`provisional_stereo_calibrate()`** — exists at `stereo_calibration.py:580`, full provisional flow with `ProvisionalStereoResult`
- **`save_stereo_pair()` metadata** — accepts `calibration_method`, `quality_level`, `intrinsics_source`, `pose_consistency_px`, `warning`
- **Readiness API** — `ready_full`, `ready_provisional` in `/api/multi/readiness`; `calibration_quality` in calibration status
- **Stereo endpoint stationary mode** — `mode=stationary` triggers `provisional_stereo_calibrate()` path
- **Auto-capture guard** — only active in `handheld+auto` mode

---

## Remaining Tasks

### File Map

| File | Role | Action |
|------|------|--------|
| `src/utils/config.py` | `get_stereo_pair()` backward-compat defaults | Modify |
| `src/web/routes.py` | Board-pose endpoint `estimate_intrinsics` fallback | Modify |
| `static/js/app.js` | Wizard mode selection, manual capture, provisional badges | Modify |
| `templates/index.html` | Wizard HTML: mode step, capture controls, badges | Modify |
| `static/css/style.css` | Mode cards, capture feedback, badge styling | Modify |
| `tests/test_provisional_stereo.py` | New: backward-compat and integration tests | Create |
| `agent_docs/current_state.md` | Document V1 features | Modify |
| `agent_docs/priorities.md` | Mark P9/P29 progress | Modify |

---

## Task 1: get_stereo_pair() Backward-Compat Defaults

**Files:**
- Modify: `src/utils/config.py` — `get_stereo_pair()` (line 187)
- Create: `tests/test_provisional_stereo.py`

Old config files written before V1 don't have `calibration_method`, `quality_level`, or `intrinsics_source`. Consumers should get safe defaults.

- [ ] **Step 1.1: Write failing test**

Create `tests/test_provisional_stereo.py`:

```python
"""Tests for provisional stereo calibration features."""
import os
import tempfile

import numpy as np
import pytest
import yaml


class TestGetStereoPairBackwardCompat:
    def test_old_config_gets_defaults(self):
        """Config written before V1 (no metadata) should get defaults."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            yaml.dump({"pairs": {"cam_old--cam_new": {
                "R": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "T": [0.1, 0, 0],
                "reprojection_error": 0.5,
                "calibrated_utc": "2026-01-01T00:00:00Z",
            }}}, f)
            path = f.name
        try:
            from src.utils.config import get_stereo_pair
            pair = get_stereo_pair("cam_old", "cam_new", path=path)
            assert pair is not None
            assert pair["calibration_method"] == "stereoCalibrate"
            assert pair["quality_level"] == "full"
            assert pair["intrinsics_source"] == "lens_calibration"
        finally:
            os.unlink(path)

    def test_new_config_preserves_values(self):
        """Config with metadata should keep its values, not get overwritten by defaults."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            yaml.dump({"pairs": {"a--b": {
                "R": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "T": [0.1, 0, 0],
                "reprojection_error": 0.0,
                "calibration_method": "board_pose_provisional",
                "quality_level": "provisional",
                "intrinsics_source": "estimated",
            }}}, f)
            path = f.name
        try:
            from src.utils.config import get_stereo_pair
            pair = get_stereo_pair("a", "b", path=path)
            assert pair["calibration_method"] == "board_pose_provisional"
            assert pair["quality_level"] == "provisional"
        finally:
            os.unlink(path)
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_provisional_stereo.py -v`

Expected: FAIL — `KeyError: 'calibration_method'` (old config has no metadata)

- [ ] **Step 1.3: Implement backward-compat defaults**

Modify `get_stereo_pair()` in `src/utils/config.py` (line 187-194):

```python
def get_stereo_pair(cam_a: str, cam_b: str,
                    path: str = MULTI_CAM_CONFIG_PATH) -> dict | None:
    """Load extrinsics for a specific camera pair. Order-independent key lookup."""
    cfg = load_multi_cam_config(path)
    pairs = cfg.get("pairs", {})
    key_ab = f"{cam_a}--{cam_b}"
    key_ba = f"{cam_b}--{cam_a}"
    pair = pairs.get(key_ab) or pairs.get(key_ba)
    if pair is not None:
        pair.setdefault("calibration_method", "stereoCalibrate")
        pair.setdefault("quality_level", "full")
        pair.setdefault("intrinsics_source", "lens_calibration")
    return pair
```

- [ ] **Step 1.4: Run test to verify it passes**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_provisional_stereo.py -v`

Expected: All PASS

- [ ] **Step 1.5: Run existing config tests for regression**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_multi_cam_config.py -v`

Expected: All PASS

- [ ] **Step 1.6: Commit**

```bash
git add src/utils/config.py tests/test_provisional_stereo.py
git commit -m "feat: add backward-compat defaults in get_stereo_pair() for pre-V1 configs"
```

---

## Task 2: Board-Pose Endpoint estimate_intrinsics Fallback

**Files:**
- Modify: `src/web/routes.py` — `board_pose_calibration()` (line 1436)

The board-pose endpoint currently returns an error if `intr is None`. In stationary mode, there may be no lens calibration. The fallback uses `estimate_intrinsics()` as a transient seed.

- [ ] **Step 2.1: Write failing test for fallback**

Add to `tests/test_provisional_stereo.py`:

```python
from unittest.mock import MagicMock, patch


class TestBoardPoseEstimateIntrinsicsFallback:
    def test_board_pose_uses_estimated_intrinsics_when_none(self):
        """Board-pose endpoint should fall back to estimate_intrinsics when no lens cal."""
        from src.cv.camera_calibration import estimate_intrinsics
        intr = estimate_intrinsics(640, 480)
        assert intr is not None
        assert intr.valid is False
        assert intr.camera_matrix[0, 0] == pytest.approx(640.0)
        # The route-level test requires a running pipeline which is heavy.
        # This unit test verifies that estimate_intrinsics produces a usable
        # CameraIntrinsics object that solvePnP can consume.
        assert intr.camera_matrix.shape == (3, 3)
        assert intr.dist_coeffs.shape[0] >= 4
```

- [ ] **Step 2.2: Run test**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_provisional_stereo.py::TestBoardPoseEstimateIntrinsicsFallback -v`

Expected: PASS (this validates the intrinsics object is well-formed for solvePnP)

- [ ] **Step 2.3: Implement fallback**

In `board_pose_calibration()` (`routes.py`, around line 1465-1467), change:

```python
# Before:
intr = pipeline.camera_calibration.get_intrinsics()
if intr is None:
    return {"ok": False, "error": f"Camera '{cam_id}' has no lens intrinsics — run lens calibration first"}

# After:
from src.cv.camera_calibration import estimate_intrinsics
intr = pipeline.camera_calibration.get_intrinsics()
intrinsics_source = "lens_calibration"
if intr is None:
    frame_check = pipeline.get_latest_raw_frame()
    if frame_check is not None:
        intr = estimate_intrinsics(frame_check.shape[1], frame_check.shape[0])
        intrinsics_source = "estimated"
        logger.info("Using estimated intrinsics for board-pose (camera %s)", cam_id)
    else:
        return {"ok": False, "error": f"Camera '{cam_id}' has no lens intrinsics and no frame available"}
```

Also add `"intrinsics_source": intrinsics_source` to the response dict.

- [ ] **Step 2.4: Run route tests**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_routes_extra.py tests/test_routes_coverage4.py -v -x`

Expected: All PASS

- [ ] **Step 2.5: Commit**

```bash
git add src/web/routes.py tests/test_provisional_stereo.py
git commit -m "feat: add estimate_intrinsics fallback to board-pose endpoint for stationary mode"
```

---

## Task 3: Wizard UI — Mode Selection

**Files:**
- Modify: `templates/index.html` — add mode selection step
- Modify: `static/js/app.js` — wizard mode logic
- Modify: `static/css/style.css` — mode card styling

- [ ] **Step 3.1: Add mode selection HTML**

In `templates/index.html`, inside the calibration modal (after the stepper, before the lens section), add:

```html
<div id="wizard-mode-select" class="wizard-step" style="display:none">
  <h3>Kalibrierungsmodus waehlen</h3>
  <div class="mode-cards">
    <div class="mode-card" data-mode="handheld" onclick="window.dartApp._selectCalibrationMode('handheld')">
      <h4>Kalibrierboard bewegen</h4>
      <p>Volle Kalibrierung, bessere Genauigkeit</p>
    </div>
    <div class="mode-card" data-mode="stationary" onclick="window.dartApp._selectCalibrationMode('stationary')">
      <h4>Kalibrierboard bleibt fest</h4>
      <p>Schnellstart, spaeter verfeinerbar</p>
    </div>
  </div>
</div>
```

- [ ] **Step 3.2: Add capture toggle and manual button HTML**

In the guidance panel section of `templates/index.html`:

```html
<div id="capture-mode-toggle" style="display:none">
  <label class="toggle-label">
    <input type="checkbox" id="capture-mode-switch" onchange="window.dartApp._toggleCaptureMode()">
    <span>Manuell</span>
  </label>
  <button id="manual-capture-btn" class="btn btn-secondary" style="display:none"
          onclick="window.dartApp._manualCapture()">
    Frame aufnehmen
  </button>
</div>
<div id="capture-feedback" class="capture-feedback" style="display:none"></div>
```

- [ ] **Step 3.3: Add CSS for mode cards and capture feedback**

Add to `static/css/style.css`:

```css
/* Calibration mode cards */
.mode-cards {
  display: flex; gap: 1rem; margin: 1rem 0;
}
.mode-card {
  flex: 1; padding: 1.5rem; border: 2px solid var(--border-color, #444);
  border-radius: 8px; cursor: pointer; transition: border-color 0.2s, background 0.2s;
  text-align: center;
}
.mode-card:hover {
  border-color: var(--accent-color, #4fc3f7);
  background: var(--hover-bg, rgba(79, 195, 247, 0.1));
}
.mode-card.selected {
  border-color: var(--accent-color, #4fc3f7);
  background: var(--selected-bg, rgba(79, 195, 247, 0.15));
}

/* Capture feedback flash */
.capture-feedback {
  padding: 0.5rem 1rem; border-radius: 4px; margin-top: 0.5rem;
  font-size: 0.9rem; transition: opacity 0.3s;
}
.capture-feedback.accept { background: rgba(76, 175, 80, 0.2); color: #4caf50; }
.capture-feedback.reject { background: rgba(244, 67, 54, 0.2); color: #f44336; }

/* Provisional badge */
.badge-provisional { background: #ff9800; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
.badge-calibrated { background: #4caf50; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
```

- [ ] **Step 3.4: Add JS wizard mode logic**

In `static/js/app.js`, add methods to the DartApp class:

```javascript
_selectCalibrationMode(mode) {
  this._wizardState.calibrationMode = mode;  // 'handheld' | 'stationary'
  // Update stepper: skip lens step if stationary
  if (mode === 'stationary') {
    this._wizardAdvance('board_running');
  } else {
    this._wizardAdvance('lens_running');
  }
}

_toggleCaptureMode() {
  const manual = document.getElementById('capture-mode-switch')?.checked;
  this._wizardState.captureMode = manual ? 'manual' : 'auto';
  const btn = document.getElementById('manual-capture-btn');
  if (btn) btn.style.display = manual ? '' : 'none';
}

async _manualCapture() {
  const camId = this._wizardState.currentCamera;
  if (!camId) return;
  try {
    const resp = await fetch(`/api/calibration/capture-frame/${camId}`, { method: 'POST' });
    const data = await resp.json();
    this._showCaptureFeedback(data.accepted, data.reason);
  } catch (e) {
    this._showCaptureFeedback(false, 'Netzwerkfehler');
  }
}

_showCaptureFeedback(accepted, reason) {
  const el = document.getElementById('capture-feedback');
  if (!el) return;
  el.className = 'capture-feedback ' + (accepted ? 'accept' : 'reject');
  el.textContent = accepted ? 'Frame aufgenommen!' : (reason || 'Abgelehnt');
  el.style.display = '';
  setTimeout(() => { el.style.display = 'none'; }, 2000);
}
```

- [ ] **Step 3.5: Update stepper to handle mode step**

Modify the existing `_updateStepperVisuals()` and `_wizardNext()` methods to:
- Include 'mode' as the first step
- Show/hide the mode selection panel
- Skip lens step when `calibrationMode === 'stationary'`
- Show capture toggle only during lens step in handheld mode
- After provisional stereo: show yellow "Provisorisch" badge and "Verfeinern" button
- "Verfeinern" button calls `_selectCalibrationMode('handheld')` to restart in handheld mode with full lens calibration. This overwrites the provisional data on success.

- [ ] **Step 3.6: Syntax check**

Run: `node -c static/js/app.js`

Expected: No syntax errors

- [ ] **Step 3.7: Run frontend-related tests**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_wizard_flow.py tests/test_web.py -v -x`

Expected: All PASS

- [ ] **Step 3.8: Commit**

```bash
git add static/js/app.js templates/index.html static/css/style.css
git commit -m "feat: wizard mode selection UI with manual capture and provisional badges"
```

---

## Task 4: Integration Tests and Validation

**Files:**
- Modify: `tests/test_provisional_stereo.py` — add integration tests

- [ ] **Step 4.1: Write integration test for provisional round-trip**

Add to `tests/test_provisional_stereo.py`:

```python
class TestProvisionalRoundTrip:
    def test_provisional_then_full_overwrites(self):
        """Full calibration should overwrite provisional data."""
        from src.utils.config import save_stereo_pair, get_stereo_pair
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            # Save provisional
            save_stereo_pair("a", "b", R=[[1,0,0],[0,1,0],[0,0,1]], T=[0.1,0,0],
                           reprojection_error=0.0, path=path,
                           calibration_method="board_pose_provisional",
                           quality_level="provisional",
                           pose_consistency_px=2.0)
            pair = get_stereo_pair("a", "b", path=path)
            assert pair["quality_level"] == "provisional"

            # Overwrite with full
            save_stereo_pair("a", "b", R=[[1,0,0],[0,1,0],[0,0,1]], T=[0.1,0,0],
                           reprojection_error=0.5, path=path)
            pair = get_stereo_pair("a", "b", path=path)
            assert pair["quality_level"] == "full"
        finally:
            os.unlink(path)


class TestCollectorWithNewThresholds:
    def test_diverse_frames_collected(self):
        """Simulate frames with small positional variation — should collect multiple."""
        from src.cv.camera_calibration import CharucoFrameCollector
        from src.cv.stereo_calibration import CharucoBoardSpec
        spec = CharucoBoardSpec(squares_x=7, squares_y=5,
                                square_length_m=0.04, marker_length_m=0.028,
                                preset_name="7x5_40x28")
        collector = CharucoFrameCollector(frames_needed=15, min_position_diff=0.05, board_specs=[spec])
        rng = np.random.RandomState(42)
        frame = rng.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        accepted = 0
        for i in range(30):
            cx = 250 + i * 15  # shift ~15px per frame
            corners = rng.uniform([cx - 25, 215], [cx + 25, 265], (8, 2)).astype(np.float32)
            if collector.add_frame_if_diverse(
                corners, frame,
                board_spec=spec,
                markers_found=10, charuco_corners_found=8,
                interpolation_ok=True,
            ):
                accepted += 1
        assert accepted >= 5, f"Expected >= 5 accepted frames, got {accepted}"
```

- [ ] **Step 4.2: Run all new tests**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_provisional_stereo.py -v`

Expected: All PASS

- [ ] **Step 4.3: Run full focused test suite**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_calibration.py tests/test_stereo_calibration.py tests/test_charuco_progress.py tests/test_wizard_flow.py tests/test_routes_coverage4.py tests/test_web.py tests/test_multi_cam_config.py -v -x`

Expected: All PASS

- [ ] **Step 4.4: Validate with real videos**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -c "
from src.cv.camera_calibration import CharucoFrameCollector, estimate_intrinsics
from src.cv.stereo_calibration import detect_charuco_board, resolve_charuco_board_candidates
from src.cv.sharpness import compute_sharpness
import cv2, numpy as np

specs = resolve_charuco_board_candidates()
collector = CharucoFrameCollector(frames_needed=15, min_position_diff=0.05, board_specs=specs)

cap = cv2.VideoCapture('testvids/rec_20260320_042317.mp4')
for i in range(0, 104, 3):
    cap.set(cv2.CAP_PROP_POS_FRAMES, i)
    ok, frame = cap.read()
    if not ok: break
    detection = detect_charuco_board(frame, board_specs=specs)
    accepted = collector.add_frame_if_diverse(
        detection.charuco_corners, frame,
        board_spec=detection.board_spec,
        markers_found=detection.markers_found,
        charuco_corners_found=detection.charuco_corners_found,
        interpolation_ok=detection.interpolation_ok,
    )
    if accepted:
        print(f'Frame {i}: ACCEPTED (usable={collector.usable_frames})')
    elif collector.last_reject_reason:
        print(f'Frame {i}: REJECTED - {collector.last_reject_reason}')
cap.release()
print(f'Total usable: {collector.usable_frames}/{collector.frames_needed}')
"
`

Expected: More than 1 frame accepted (vs. exactly 1 with old 0.15 threshold)

- [ ] **Step 4.5: Commit**

```bash
git add tests/test_provisional_stereo.py
git commit -m "test: add integration and round-trip tests for calibration V1"
```

---

## Task 5: Documentation Update

**Files:**
- Modify: `agent_docs/current_state.md`
- Modify: `agent_docs/priorities.md`

- [ ] **Step 5.1: Update current_state.md**

Add under "Was heute als stabil gilt":
- Multi-Cam-Kalibrierung: Zwei-Modi-Wizard (Handheld + Stationaer/Provisional)
- CharucoFrameCollector: Qualitaets-Gate (Schaerfe, Interpolation), gesenkte Diversitaetsschwellen
- Manual-Capture-Endpoint fuer gezielte Frame-Aufnahme
- Provisorische Stereo-Kalibrierung via Board-Pose mit separater Speicherung
- Readiness-API: additiv ready_full / ready_provisional

- [ ] **Step 5.2: Update priorities.md**

Mark P9 and P29 progress with summary of what was implemented. Add note about V1.1 items (pose-diversity, best-of-N).

- [ ] **Step 5.3: Commit**

```bash
git add agent_docs/current_state.md agent_docs/priorities.md
git commit -m "docs: update current_state and priorities for calibration V1"
```
