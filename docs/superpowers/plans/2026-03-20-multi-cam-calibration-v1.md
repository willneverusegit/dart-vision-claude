# Multi-Cam Calibration V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the ChArUco frame collection blocker and add a provisional stationary calibration mode.

**Architecture:** Extend the existing `CharucoFrameCollector` with quality gates, lower diversity thresholds, and manual capture support. Add a separate provisional stereo path using `solvePnP`-derived extrinsics. Store provisional results with explicit metadata in the existing config schema.

**Tech Stack:** Python 3.11+, OpenCV (cv2), FastAPI, NumPy, vanilla JS

**Spec:** `docs/superpowers/specs/2026-03-20-multi-cam-calibration-design.md`

---

## Already Implemented

The following features are already in place, verified against the current codebase:

### Backend (src/cv/)
- **Quality gate** in `CharucoFrameCollector` — sharpness check via `compute_sharpness()`, `MIN_CHARUCO_CORNERS=6`, `last_reject_reason` property, `_last_sharpness` tracking (`camera_calibration.py:311+`)
- **Lowered diversity threshold** — `min_position_diff` default is `0.05` (was `0.15`)
- **`min_rotation_diff_deg`** — dead code already removed from constructor
- **`estimate_intrinsics()`** — exists at `camera_calibration.py:24`, returns `CameraIntrinsics(valid=False)`
- **`stereo_from_board_poses()`** — exists at `stereo_calibration.py:551`, takes `BoardPoseEstimate` objects
- **`provisional_stereo_calibrate()`** — exists at `stereo_calibration.py:580`, full provisional flow with `ProvisionalStereoResult`
- **`save_stereo_pair()` metadata** — accepts `calibration_method`, `quality_level`, `intrinsics_source`, `pose_consistency_px`, `warning` (`config.py:197+`)

### Backend (src/web/routes.py)
- **Manual capture endpoint** — `POST /api/calibration/capture-frame/{camera_id}` (line 2652)
- **`calibration_mode` and `capture_mode`** — stored on `CharucoFrameCollector` directly, used in charuco-start/progress
- **Auto-capture guard** — only active in `handheld+auto` mode
- **Stereo endpoint stationary mode** — `mode=stationary` triggers `provisional_stereo_calibrate()` (line 1289)
- **Readiness API** — `ready_full`, `ready_provisional` in `/api/multi/readiness` (line 1734+); `calibration_quality` in calibration status (line 2602+)

### Frontend (static/js/app.js, templates/index.html, static/css/style.css)
- **Mode selection** — radio buttons "Bewegen" / "Fest" (`index.html:626-631`)
- **Capture mode toggle** — "Auto" / "Manuell" radio buttons (`index.html:638-645`)
- **Manual capture button** — `btn-cal-capture-frame` with event handler (`app.js:134-149`)
- **Capture feedback** — `_setCalibrationAutoFeedback()` method (`app.js:713`)
- **Sharpness display** — `charuco-sharpness` pill in UI (`index.html:663`, `app.js:4028-4040`)
- **Provisional badges** — "Provisorisch" / "Kalibriert" badges (`app.js:747-748, 786-789`)
- **Stepper mode handling** — `_updateStepperVisuals()` skips lens for stationary (`app.js:3840-3842`)
- **Status badge** — "Stationaer / Provisorisch" vs "Handheld / Voll" (`app.js:449`)

---

## Remaining Tasks

Only 2 small backend gaps plus tests and docs remain.

### File Map

| File | Role | Action |
|------|------|--------|
| `src/utils/config.py` | `get_stereo_pair()` backward-compat defaults | Modify |
| `src/web/routes.py` | Board-pose endpoint `estimate_intrinsics` fallback | Modify |
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

    def test_existing_callers_still_work(self):
        """Code that only reads R, T, reprojection_error should not break."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
            yaml.dump({"pairs": {"x--y": {
                "R": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                "T": [0.2, 0, 0],
                "reprojection_error": 0.3,
            }}}, f)
            path = f.name
        try:
            from src.utils.config import get_stereo_pair
            pair = get_stereo_pair("x", "y", path=path)
            assert pair["R"] == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            assert pair["T"] == [0.2, 0, 0]
            assert pair["reprojection_error"] == pytest.approx(0.3)
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
- Modify: `tests/test_provisional_stereo.py` — add unit test

The board-pose endpoint currently returns an error if `intr is None` (line 1466-1467). In stationary mode, there may be no lens calibration. The fallback uses `estimate_intrinsics()` as a transient seed for `solvePnP`.

- [ ] **Step 2.1: Write test for estimate_intrinsics usability**

Add to `tests/test_provisional_stereo.py`:

```python
class TestEstimateIntrinsicsForBoardPose:
    def test_produces_usable_intrinsics(self):
        """estimate_intrinsics must produce a CameraIntrinsics usable by solvePnP."""
        from src.cv.camera_calibration import estimate_intrinsics
        intr = estimate_intrinsics(640, 480)
        assert intr is not None
        assert intr.valid is False
        assert intr.method == "estimated"
        assert intr.camera_matrix.shape == (3, 3)
        assert intr.camera_matrix[0, 0] > 0  # fx > 0
        assert intr.dist_coeffs.shape[0] >= 4  # solvePnP needs at least 4

    def test_1280x720(self):
        from src.cv.camera_calibration import estimate_intrinsics
        intr = estimate_intrinsics(1280, 720)
        assert intr.camera_matrix[0, 2] == pytest.approx(640.0)  # cx = width/2
        assert intr.camera_matrix[1, 2] == pytest.approx(360.0)  # cy = height/2
```

- [ ] **Step 2.2: Run test to verify it passes**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_provisional_stereo.py::TestEstimateIntrinsicsForBoardPose -v`

Expected: PASS (estimate_intrinsics already exists and works)

- [ ] **Step 2.3: Implement fallback in board-pose endpoint**

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

## Task 3: Missing UI Features — Verfeinern, Modus-Wechsel, Flash-Overlay

**Files:**
- Modify: `static/js/app.js` — add Verfeinern flow, Modus-Wechsel link, flash overlay
- Modify: `templates/index.html` — add Verfeinern button, Modus-Wechsel link
- Modify: `static/css/style.css` — flash overlay animation

These 3 spec UI features (Paket 5) are not yet implemented.

- [ ] **Step 3.1: Add "Verfeinern" button after provisional stereo result**

In the stereo result display area of `templates/index.html`, add:

```html
<button id="btn-cal-refine" class="btn btn-secondary" style="display:none"
        onclick="window.dartApp._refineCalibration()">
  Verfeinern (Handheld-Modus starten)
</button>
```

In `static/js/app.js`, add to the DartApp class:

```javascript
_refineCalibration() {
    // Reset collector and restart in handheld mode for full calibration
    this._wizardState.mode = 'handheld';
    this._wizardState.captureMode = 'auto';
    this._syncWizardModeControls();
    // Re-enter the wizard from lens step
    var cameraId = this._wizardState.currentCamera;
    if (cameraId) {
        this._startGuidedCapture(cameraId);
    }
}
```

Show the button when `data.quality_level === 'provisional'` in `_showWizardResult()` or `_renderWizardResultQuality()`.

- [ ] **Step 3.2: Add "Modus aendern" link in stepper**

In `templates/index.html`, add a link near the stepper:

```html
<a id="wizard-change-mode" href="#" style="display:none; font-size:0.85rem;"
   onclick="event.preventDefault(); window.dartApp._changeCalibrationMode()">Modus aendern</a>
```

In `static/js/app.js`:

```javascript
_changeCalibrationMode() {
    // Reset collector and go back to mode selection
    this._resetCalibration('all');
    this._showCalStep('cal-step-mode');
}
```

Show the link when wizard step is not 'idle' and not already on mode step.

- [ ] **Step 3.3: Add flash overlay for accept/reject**

In `static/css/style.css`:

```css
/* Frame capture flash overlay */
.capture-flash {
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  pointer-events: none; opacity: 0;
  transition: opacity 0.15s ease-out;
}
.capture-flash--accept { background: rgba(76, 175, 80, 0.3); }
.capture-flash--reject { background: rgba(244, 67, 54, 0.3); }
.capture-flash.active { opacity: 1; }
```

In `templates/index.html`, add inside the video feed container:

```html
<div id="capture-flash" class="capture-flash"></div>
```

In `static/js/app.js`, add flash trigger to the capture feedback path:

```javascript
_flashCapture(accepted) {
    var el = document.getElementById('capture-flash');
    if (!el) return;
    el.className = 'capture-flash ' + (accepted ? 'capture-flash--accept' : 'capture-flash--reject') + ' active';
    setTimeout(function() { el.classList.remove('active'); }, 300);
}
```

Call `this._flashCapture(data.accepted)` in the capture-frame response handler and auto-capture callback.

- [ ] **Step 3.4: Syntax check**

Run: `node -c static/js/app.js`

Expected: No syntax errors

- [ ] **Step 3.5: Commit**

```bash
git add static/js/app.js templates/index.html static/css/style.css
git commit -m "feat: add Verfeinern button, Modus-Wechsel link, and capture flash overlay"
```

---

## Task 4: Integration Tests and Real-Video Validation

**Files:**
- Modify: `tests/test_provisional_stereo.py` — add integration tests

- [ ] **Step 3.1: Write integration tests**

Add to `tests/test_provisional_stereo.py`:

```python
class TestProvisionalRoundTrip:
    def test_provisional_then_full_overwrites(self):
        """Full calibration should overwrite provisional data."""
        from src.utils.config import save_stereo_pair, get_stereo_pair
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            save_stereo_pair("a", "b", R=[[1,0,0],[0,1,0],[0,0,1]], T=[0.1,0,0],
                           reprojection_error=0.0, path=path,
                           calibration_method="board_pose_provisional",
                           quality_level="provisional",
                           pose_consistency_px=2.0)
            pair = get_stereo_pair("a", "b", path=path)
            assert pair["quality_level"] == "provisional"

            save_stereo_pair("a", "b", R=[[1,0,0],[0,1,0],[0,0,1]], T=[0.1,0,0],
                           reprojection_error=0.5, path=path,
                           calibration_method="stereoCalibrate",
                           quality_level="full")
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
            cx = 250 + i * 15
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

- [ ] **Step 3.2: Run all new tests**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_provisional_stereo.py -v`

Expected: All PASS

- [ ] **Step 3.3: Run full focused test suite**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -m pytest tests/test_calibration.py tests/test_stereo_calibration.py tests/test_charuco_progress.py tests/test_wizard_flow.py tests/test_routes_coverage4.py tests/test_web.py tests/test_multi_cam_config.py -v -x`

Expected: All PASS

- [ ] **Step 3.4: Validate with real videos (manual, not CI)**

Run: `cd C:/Users/domes/OneDrive/Desktop/dart-vision-claude && .venv/Scripts/python.exe -c "
from src.cv.camera_calibration import CharucoFrameCollector
from src.cv.stereo_calibration import detect_charuco_board, resolve_charuco_board_candidates
import cv2

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
"`

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
