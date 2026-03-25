# Iteration Log

---

## [2026-03-24] Stereo Calibration Coverage: 59 neue Tests, alle Kernfunktionen abgedeckt

**Category:** testing | **Severity:** minor | **Attempts:** 1

**Type:** enhancement
**Summary:** 59 neue Tests in `tests/test_stereo_calibration_coverage.py` fuer bisher ungetestete Bereiche in `src/cv/stereo_calibration.py`. Abgedeckt: CharucoBoardSpec Validierung (__post_init__ alle 3 Fehlertypen, to_config_fragment, to_api_payload, create_dictionary, create_board), _canonical_preset_name (bekannte Presets, custom, Portrait-Varianten), resolve_charuco_board_spec Edge Cases (board_spec Parameter, unknown preset, config overrides, mm overrides), resolve_charuco_board_candidates (board_spec, non-auto, dedup, auto+mm), detect_charuco_board Edge Cases (empty candidates, grayscale, no markers, few markers warning, no interpolation multi-candidate, few corners warning, single candidate no markers), estimate_charuco_board_pose (None intrinsics, no board_spec, interpolation not ok, too few ids, synthetic success, cv2.error, solvePnP failure), stereo_from_board_poses (identity, translation-only, output types), _average_stereo_extrinsics (single pair, multi averaging, negative det correction, output types), provisional_stereo_calibrate (mismatch, too few pairs, synthetic success, result fields), validate_stereo_prerequisites (invalid cameras, dict keys), stereo_calibrate Exception-Pfade (cv2.error, non-finite rms, success path), ProvisionalStereoResult/BoardPoseEstimate fields.
**Files changed:** tests/test_stereo_calibration_coverage.py (neu)
**Tests:** 1686 passed (+59), 0 failed, 1 warning
**Confidence:** 5/5
**Tags:** python, testing, stereo-calibration, coverage, board-pose, provisional-stereo, charuco

### Details
- estimate_charuco_board_pose war komplett ungetestet — jetzt 7 Tests (None-Pfade, synthetic success mit projectPoints, cv2.error, solvePnP failure)
- stereo_from_board_poses war komplett ungetestet — jetzt 3 Tests (identity, translation, types)
- _average_stereo_extrinsics war komplett ungetestet — jetzt 4 Tests inkl. negative-det SVD-Korrektur
- provisional_stereo_calibrate war komplett ungetestet — jetzt 4 Tests (mismatch, few pairs, synthetic success mit 4 variierenden Posen, result fields)
- validate_stereo_prerequisites war komplett ungetestet — jetzt 2 Tests (ungueltige Kameras, dict structure)
- stereo_calibrate Exception-Pfade (cv2.error, non-finite rms, success) waren komplett ungetestet — jetzt 3 Tests via monkeypatch
- CharucoBoardSpec.__post_init__ Validierung (3 Fehlertypen), to_config_fragment, to_api_payload waren ungetestet — jetzt 11 Tests

### Learnings
- estimate_charuco_board_pose laesst sich gut mit synthetischen Daten testen: Board-Corners via getChessboardCorners holen, projectPoints fuer Image-Points, dann Detection-Objekt bauen
- _average_stereo_extrinsics hat einen SVD-basierten Rotations-Averaging mit negative-det-Korrektur — subtiler Branch der ohne Test leicht brechen koennte

---

## [2026-03-24] Remapping + Main Coverage: 51 neue Tests

**Category:** testing | **Severity:** minor | **Attempts:** 1

**Type:** enhancement
**Summary:** 51 neue Tests in zwei Dateien fuer bisher ungetestete Branches in `src/cv/remapping.py` und `src/main.py`. Remapping (25 Tests): roi_to_raw() alle 3 Pfade (no homography, with intrinsics, without intrinsics, zero-fx skip), configure() Edge Cases (None homography reset, invalid intrinsics, flat array reshape, exception in _build_combined_maps), _build_combined_maps ValueError bei fx=0/fy=0, remap() Fallback-Pfade (undistort+warp, combined map), Properties. Main (26 Tests): _full_state_reset() mit/ohne Lock, _wait_for_camera_release() (skip non-USB, retry, timeout, string digit), stop_pipeline_thread force-release (camera stop, pipeline stop, camera None, exception), _run_pipeline Callbacks (on_dart_detected mit detection, ohne engine/em, recorder write, general exception, stop_event=None), _run_multi_pipeline (start failure, on_multi_dart_detected, on_camera_errors_changed, frame update loop), _compute_quality_score Edge Cases.
**Files changed:** tests/test_remapping_coverage.py (neu), tests/test_main_coverage2.py (neu)
**Tests:** 1627 passed (+51), 0 failed, 1 warning
**Confidence:** 5/5
**Tags:** python, testing, remapping, main, coverage, roi-to-raw, state-reset, callbacks

### Details
- remapping.py hatte nur 3 Tests — roi_to_raw() war komplett ungetestet, configure() Edge Cases fehlten
- main.py: _full_state_reset(), _wait_for_camera_release(), force-release Pfade in stop_pipeline_thread, Recorder-Write-Pfad, Multi-Pipeline-Callbacks waren ungetestet
- _full_state_reset in finally-Block von _run_multi_pipeline loescht multi_latest_frames — Test muss get_annotated_frame-Aufruf verifizieren statt State nach Cleanup
- roi_to_raw mit fx=0 nimmt den Early-Return-Pfad ohne Re-Distortion (Zeile 74: if fx != 0 and fy != 0)

### Learnings
- remapping.py war trotz geringer Zeilenanzahl (146 Zeilen) ein Coverage-Blindspot weil es nur 3 triviale Tests hatte — roi_to_raw() als Kernfunktion war komplett ungetestet
- Bei Tests fuer Funktionen mit finally-Cleanup-Bloecken: State-Assertions muessen den Cleanup beruecksichtigen, nicht den Zustand waehrend der Ausfuehrung

---

## [2026-03-24] CalibrationManager Coverage: 46 neue Tests, 52% → 78%

**Category:** testing | **Severity:** minor | **Attempts:** 1

**Type:** enhancement
**Summary:** 46 neue Tests in `tests/test_calibration_coverage.py` fuer bisher ungetestete Bereiche in `src/cv/calibration.py`. Abgedeckt: ArUco Calibration Success Path (Grayscale/BGR/Config-Persistenz/Custom Params/Detection Method/Missing Marker/State Updates/Radii), ChArUco Calibration (Too-few-frames/No-usable/Synthetic Success/BGR/Exception), reset_calibration (Full/Lens-Only/Board-Only/State Verification), _atomic_save (Directory Creation/Legacy Migration/Multi-Camera Preservation/Corrupt File), find_optical_center (Grayscale/Empty Patch/Edge Cases), _load_config (Exception/Missing Camera/Raw Data), manual_calibration Edge Cases (Degenerate/Too Small/Exception/Close Points/Wrong Count/mm_per_px), Config Accessors.
**Files changed:** tests/test_calibration_coverage.py (neu)
**Tests:** 1576 passed (+46), 0 failed, 1 warning
**Confidence:** 5/5
**Tags:** python, testing, calibration, aruco, charuco, coverage

### Details
- CalibrationManager hatte NULL direkte Unit-Tests — 52% Coverage kam ausschliesslich indirekt ueber Route-Tests
- ArUco Success Path (Zeilen 272-412, ~140 Zeilen) war der groesste einzelne uncovered Block
- charuco_calibration (Zeilen 573-635) und reset_calibration (684-713) waren komplett ungetestet
- Synthetische ArUco-Frames via cv2.aruco.generateImageMarker() funktionieren zuverlaessig
- _atomic_save Merge-Semantik entdeckt: reset loescht Keys in-memory, aber File-Merge fuegt keine Deletions durch — potentieller Tech-Debt

### Learnings
- CalibrationManager war der groesste Coverage-Blindspot (52%) im gesamten Projekt — ohne direkte Unit-Tests hing die Coverage rein an Integration via Routes
- Synthetische ArUco-Marker-Generierung ist trivial und liefert zuverlaessige Detection auch in Unit-Tests

---

## [2026-03-24] Multi-Camera Coverage: 63 neue Tests, FPSGovernor + Kernmethoden abgedeckt

**Category:** testing | **Severity:** minor | **Attempts:** 1

**Type:** enhancement
**Summary:** 63 neue Tests in `tests/test_multi_camera_coverage.py` fuer bisher ungetestete Bereiche in `src/cv/multi_camera.py`. Abgedeckt: FPSGovernor komplett (Init, should_skip_frame, record_frame_time mit Overload/Recovery/Min-FPS/Primary-Protection, Properties, get_stats), MultiCameraPipeline.stop() (running-Flag, Pipeline-Stop, Thread-Join, Fusion-Thread), _apply_camera_profile(), _apply_exposure_gain() (alle Branches), _load_extrinsics() (Board-Transforms, Stereo-Pairs, fehlende Intrinsics, ungueltige Daten, Stale-Stereo-Warning), reload_stereo_params(), _notify_camera_errors() (Callback, Exception-Handling), reset_all(), alle get_*-Accessoren, _try_fuse Triangulation-Erfolg/-Fehlschlag + Depth-Auto-Adapt, _voting_fallback (2-Cam weighted, 3-Cam median, no-total-score, VAQ-Gewichtung), __init__ Config-Branches, _degrade_camera(), _emit().
**Files changed:** tests/test_multi_camera_coverage.py (neu)
**Tests:** 1530 passed (+63), 0 failed, 1 warning
**Confidence:** 5/5
**Tags:** python, testing, multi-camera, fps-governor, coverage, triangulation

### Details
- FPSGovernor war komplett ungetestet — jetzt 20 Tests fuer alle Methoden und Branches
- stop() war ungetestet — jetzt 5 Tests (running-Flag, Pipeline-Stops, Thread-Joins, Fusion-Thread, None-Fusion)
- _load_extrinsics() war ungetestet — jetzt 6 Tests (Board-Transform laden/fehlen/ungueltig, Stereo-Pair laden, fehlende Intrinsics, Stale-Warning)
- _apply_exposure_gain() war ungetestet — jetzt 4 Tests (Exposure+Gain, kein Config, kein set_exposure, unbekannte Camera)
- _try_fuse Triangulation-Erfolg war ungetestet — jetzt 3 Tests (Erfolg mit Scoring, Fehlschlag→Voting, Depth-Auto-Adapt)

### Learnings
- FPSGovernor hat eine subtile Asymmetrie: Primary-Kameras werden NIE gedrosselt, nur Secondary. Das ist eine bewusste Design-Entscheidung die ohne Tests leicht verloren gehen koennte.
- Depth-Auto-Adapt braucht >20 Gesamtversuche UND >50% Z-Rejection-Rate bevor die Toleranz geweitet wird — konservatives Design.

---

## [2026-03-24] Pipeline.py Coverage: 39 neue Tests, kritische Branches abgedeckt

**Category:** testing | **Severity:** minor | **Attempts:** 1

**Type:** enhancement
**Summary:** 39 neue Tests in `tests/test_pipeline_coverage2.py` fuer bisher ungetestete Branches in `src/cv/pipeline.py`. Abgedeckt: start() Lifecycle (Homography-Restore, Optical-Center-Restore), _check_camera_focus() (low/ok/grayscale), process_frame() Branches (stale frame drop, idle skip, bounce-out, exclusion zone rejection, full detection→scoring→callback, tip/no-tip raw coords), detect_optical_center() (camera read, grayscale ROI), MotionFilter-Property-Proxies, _draw_marker_overlay(), _composite_overlay() Edge Cases, _draw_field_overlay() Radii-Fallback.
**Files changed:** tests/test_pipeline_coverage2.py (neu)
**Tests:** 1491 passed (+39), 14 failed (alle E2E-Video-Replay, VM-bedingt), 2 skipped
**Confidence:** 5/5
**Tags:** python, testing, pipeline, coverage, process-frame, detection

### Details
- Test-Ordering-Pollution in diff_detector-Tests: nicht reproduzierbar in dieser Umgebung (alle 45 diff_detector-Tests bestehen auch im Gesamtlauf)
- Groesste Coverage-Luecke war process_frame(): 8 von ~15 Branches waren ungetestet (bounce-out, exclusion zone, scoring, stale drop, idle skip, tip-handling)
- start() war komplett ungetestet — jetzt 4 Tests (init, homography, optical center, no-homography)
- _check_camera_focus() war komplett ungetestet — jetzt 5 Tests (no cam, read fail, low/good quality, grayscale)

### Learnings
- Coverage-Tooling (pytest-cov) interferiert mit cv2-Import unter Python 3.10 in bestimmten Umgebungen — Code-Analyse als Alternative funktioniert gut.
- Die frueher dokumentierte Test-Ordering-Pollution ist moeglicherweise umgebungsspezifisch (Windows vs. Linux) oder wurde durch fruehere Test-Hygiene-Fixes (sync_wait_s, Preset-Werte) indirekt behoben.

---

## [2026-03-24] Test-Suite Hygiene: 16 Failures gefixt

**Category:** testing | **Severity:** minor | **Attempts:** 1

**Type:** bugfix
**Summary:** 26 pre-existing Test-Failures auf 10 reduziert. Drei Root Causes identifiziert und behoben: (1) sync_depth_presets-Tests referenzierten veraltete Preset-Werte nach Live-Tuning, (2) asyncio.timeout fehlt in Python <3.11, (3) Multi-Cam sync_wait_s Default von 0.3s auf 0.8s geaendert aber Tests nicht angepasst. Verbleibende 10 Failures sind umgebungsbedingt (fehlende Video-Codecs in Linux-VM, Test-Ordering-Pollution).
**Files changed:** tests/test_sync_depth_presets.py, tests/test_multi_camera.py, tests/test_multi_robustness.py, src/web/routes.py
**Tests:** 1450 passed, 10 failed (8 env, 2 ordering), 2 skipped
**Confidence:** 5/5
**Tags:** python, testing, asyncio, compatibility, sync-depth-presets, multi-cam

### Details
- `SYNC_DEPTH_PRESETS` in config.py: tight=200ms/50mm, standard=500ms/300mm, loose=1000ms/500mm — Tests erwarteten die alten engeren Werte
- `asyncio.timeout` (Python 3.11+): Compat-Shim als asynccontextmanager mit call_later/cancel in routes.py eingefuegt
- `sync_wait_s` Default 0.8s: Test-Timestamps von 0.5s auf 1.0s angehoben damit Single-Cam-Fallback triggert
- diff_detector-Tests (test_idle_updates_baseline, test_board_wire_filtered_by_opening) bestehen isoliert, scheitern nur im Gesamtlauf — State Pollution durch anderes Testmodul

### Learnings
- Wenn Implementierungs-Defaults geaendert werden (z.B. durch Live-Tuning), muessen zugehoerige Tests zeitgleich aktualisiert werden. Sonst divergieren Tests und Impl still.
- Python-Version-Compat: asyncio.timeout ist nicht backportierbar ueber pip, braucht eigenen Shim.

---

## [2026-03-24] P77: Cricket Sektor-Validierung + Tests

**Category:** enhancement | **Severity:** minor | **Attempts:** 1

**Type:** feature
**Summary:** Cricket-Sektorvalidierung war bereits implizit vorhanden (`if target not in player.cricket_marks: return`). Ergaenzt: explizite `CRICKET_SECTORS` Klassenkonstante, debug-Logging fuer nicht-Cricket-Wuerfe, 8 neue Tests (Dart-Verbrauch, Turn-Completion, Bull-Varianten, Win-Szenario, Boundary-Sektoren, Excess-Marks).
**Files changed:** src/game/engine.py, tests/test_game_engine.py
**Tests:** 32 passed (24 pre-existing + 8 new), 0 regressions
**Confidence:** 5/5
**Tags:** python, game-engine, cricket, validation, testing

### Details
- Bestehende Logik in `_score_cricket()` filterte nicht-Cricket-Sektoren korrekt, aber ohne Logging oder explizite Dokumentation
- `CRICKET_SECTORS = frozenset({15, 16, 17, 18, 19, 20, 25})` als Klassen-Konstante hinzugefuegt
- `logger.debug()` bei nicht-Cricket-Wuerfen eingefuegt
- Neue Tests decken: non-cricket darts still count toward turn, 3 non-cricket darts complete turn, outer bull single mark, double bull 2 marks, cricket win all-closed, boundary sectors (1-14, 21+), CRICKET_SECTORS constant, excess marks scoring

### Learnings
- P77 war als "keine Pruefung vorhanden" beschrieben, tatsaechlich war die Pruefung bereits implementiert. Analyse vor Implementierung spart unnoetige Aenderungen.
- Wert lag primaer in den Tests, nicht in Code-Aenderungen.

---

## [2026-03-24] Board-XY-Mapping: solvePnP-Transform war nicht invertiert

**Category:** logic | **Severity:** critical | **Attempts:** 1

**Type:** bugfix
**Summary:** solvePnP liefert Board→Camera (R_bc, t_bc), aber der Code speicherte das direkt als R_cb/t_cb (Camera→Board). transform_to_board_frame() produzierte dadurch unsinnige Koordinaten — Scoring zeigte immer "miss".
**Files changed:** src/web/routes.py, src/cv/stereo_utils.py, tests/test_stereo_utils.py
**Tests:** passed (83 fokussiert, 2 pre-existing env-failures)
**Confidence:** 5/5
**Tags:** python, opencv, solvepnp, triangulation, coordinate-transform, multi-cam

### Details
- `cv2.solvePnP(object_points, image_points, ...)` gibt rvec/tvec zurueck die von **Object-Frame (Board) nach Camera-Frame** transformieren: `p_cam = R_bc @ p_board + t_bc`
- Der Code benannte das Ergebnis faelschlicherweise R_cb/t_cb und wendete `R_cb @ p_cam + t_cb` an — mathematisch falsch
- Fix: Im board_pose_calibration Endpoint die Inverse berechnen: `R_cb = R_bc.T`, `t_cb = -R_bc.T @ t_bc`
- Zusaetzlich 7 Debug-Logs von INFO auf DEBUG gestuft

### Learnings
- solvePnP gibt IMMER Object→Camera. Die Variable-Benennung muss das reflektieren. Faustregel: R aus solvePnP = R_object_to_camera, nie umgekehrt.
- Bestehende Board-Pose-Kalibrierungsdaten sind nach diesem Fix ungueltig und muessen neu erstellt werden.

### Errors
- E11: solvepnp-transform-not-inverted

---

## [2026-03-23 21:10] ChArUco Auto-Capture sammelte keine Frames

**Category:** logic | **Severity:** critical | **Attempts:** 1

**Type:** bugfix
**Summary:** charuco-progress Endpoint aktualisierte nur Detection-State, rief aber nie add_frame_if_diverse() auf — Auto-Capture war komplett kaputt.
**Files changed:** src/web/routes.py
**Tests:** passed (1427)
**Confidence:** 5/5
**Tags:** python, fastapi, charuco, auto-capture, calibration

### Details
- Der `/api/calibration/charuco-progress/{camera_id}` Endpoint fuehrte `detect_charuco_board()` und `collector.update_detection()` aus, aber bei `capture_mode=auto` wurde `add_frame_if_diverse()` nie aufgerufen.
- Ergebnis: 0 usable Frames trotz sichtbarem Board (14 Corners erkannt).
- Fix: Auto-Capture Block hinzugefuegt der bei `interpolation_ok` und `>=6 Corners` automatisch Frames sammelt.
- Verifiziert: Live-Test mit echten Kameras, 15/15 Frames in ~20s gesammelt, Lens RMS 0.23px.

### Learnings
- Progress/Status-Endpoints die nur lesen sollen koennen bei Auto-Modi auch Seiteneffekte (Frame-Sammlung) haben muessen — das ist ein Pattern das leicht uebersehen wird.

### Errors
- E8: charuco-auto-capture-no-frames

---

## [2026-03-23 21:20] Multi-Cam Kalibrierung end-to-end durchgefuehrt

**Type:** feature
**Summary:** Erstmals vollstaendige Multi-Cam-Kalibrierung auf Hardware: Lens (ChArUco 40/28), Board (ArUco 4x4), Stereo — beide Kameras.
**Files changed:** src/web/routes.py, static/js/app.js
**Tests:** passed (1427)
**Confidence:** 4/5
**Tags:** multi-cam, calibration, charuco, aruco, stereo, hardware-test

### Details
- Kalibrierungs-Reset fuer beide Kameras durchgefuehrt
- Lens cam_left: RMS 0.230px, cam_right: RMS 0.223px (Preset 7x5_40x28)
- Board ArUco: mm_per_px 2.385 (left), 2.343 (right), alle 4 Marker erkannt
- Stereo-Paar: calibrated=true, quality_level=full
- Board-Pose fehlt noch (kein Endpoint vorhanden)

---

## [2026-03-19 13:15] Multi-Cam-Kalibrierung war auf Single-Cam-Routen verdrahtet

**Category:** logic | **Severity:** major | **Attempts:** 2

**Problem:** Im Multi-Cam-Kalibriermodus funktionierte nur der manuelle Board-Pfad. ArUco, Lens, Status, ROI/Overlay und Optical-Center liefen in eine generische Meldung "Pipeline nicht aktiv".

**Root Cause:** Die betroffenen Kalibrier-Endpunkte verwendeten nur `app_state["pipeline"]`. Im Multi-Cam-Betrieb lebt die aktive Live-Pipeline aber in `app_state["multi_pipeline"]`, und das Frontend uebergab keinen expliziten Kamera-Kontext.

**Solution:** In `src/web/routes.py` eine Multi-Cam-faehige Aufloesung der aktiven Kalibrierpipeline pro `camera_id` eingebaut und das Kalibriermodal in `static/js/app.js`/`templates/index.html` um Kamera-Auswahl sowie zielbezogene Statusmeldungen erweitert. Dazu 5 neue Regressionstests fuer die Auswahl der richtigen Sub-Pipeline.

**Failed Approaches:**
- Nur implizit auf die erste Multi-Cam-Sub-Pipeline fallen lassen - funktional, aber fuer Nutzer und gespeicherte per-Kamera-Kalibrierungen zu intransparent

**Takeaway:** Live-Kalibrierung ist im Multi-Cam-Modus immer kamera-spezifisch. Backend und Frontend muessen denselben Kamera-Kontext explizit tragen; ein stiller Single-Cam-Fallback ist hier ein Designfehler.

---

## [2026-03-17 14:00] Motion-Gate blockiert SETTLING-State

**Category:** architecture | **Severity:** major | **Attempts:** 1

**Problem:** frame_diff_detector.update() war im Plan nach dem Motion-Gate-Early-Return platziert — SETTLING-State bekam keine bewegungsfreien Frames.

**Root Cause:** pipeline.process_frame() gab bei has_motion=False fruehzeitig zurueck. Der neue Detektor wurde danach eingebaut und blieb dauerhaft in SETTLING haengen.

**Solution:** update() vor den Early-Return verschoben. Jeder Frame erreicht den Detektor.

**Failed Approaches:** keine (im Plan-Review erkannt, vor Implementierung behoben)

**Takeaway:** State-Machines mit Countdown-Logik muessen VOR jedem Gate-Early-Return aufgerufen werden — nicht danach.

---

## [2026-03-17 14:30] Baseline wird auf Motion-Frame gesetzt

**Category:** logic | **Severity:** major | **Attempts:** 1

**Problem:** _handle_idle() setzte Baseline bedingungslos — auch auf den Dart-in-Flight-Frame. Diff gegen eigene Baseline = kein Unterschied.

**Root Cause:** self._baseline = frame.copy() stand vor der has_motion-Pruefung.

**Solution:** Baseline nur aktualisieren wenn has_motion=False. Bei Motion: Baseline einfrieren.

**Failed Approaches:** keine (vom Implementer beim Schreiben erkannt)

**Takeaway:** Bei Frame-Diff-Detektoren immer: Baseline = letzter ruhiger Frame. Jede Bewegung friert die Baseline ein.

---

## [2026-03-17 15:00] MOG2 kein Reset zwischen Turns

**Category:** logic | **Severity:** major | **Attempts:** 1

**Problem:** Nach reset_turn() wurde kein has_motion=True mehr erzeugt. Zweiter Wurf blieb unerkannt.

**Root Cause:** MOG2 adaptiert den Hintergrund fortlaufend. Der erste Dart wurde Teil des Hintergrundmodells. Naechster Wurf erzeugte kein Signal mehr.

**Solution:** motion_detector.reset() in reset_turn() aufgenommen.

**Failed Approaches:** keine (vom Implementer beim Testen erkannt)

**Takeaway:** MOG2 muss nach jedem semantischen Turn-Reset neu initialisiert werden, sonst sind neue Darts "unsichtbar".

---

## [2026-03-17 19:00] Centroid ≠ Dartspitze — Tip-Detection noetig

**Category:** architecture | **Severity:** minor | **Attempts:** 1

**Problem:** Centroid liegt ~28px von der Spitze entfernt (Richtung Flights). Bei Segmentgrenzen fuehrt das zu falschem Scoring.

**Root Cause:** Flaechenschwerpunkt einer Dart-Silhouette liegt naturgemaess zur Mitte, weil Flights viel mehr Flaeche haben als die Spitze.

**Solution:** minAreaRect → Achse bestimmen → Kontur halbieren → schmalere Haelfte = Tip-Seite → aeusserster Punkt = Tip. Validiert auf 18 echten Aufnahmen.

**Failed Approaches:** keine (datengetriebener Ansatz — erst Aufnahmen, dann Algorithmus)

**Takeaway:** Daten-zuerst-Ansatz spart Iterationen. Erst echte Aufnahmen sammeln, dann Algorithmus auf realen Daten designen statt blind synthetisch zu entwickeln.

---

## [2026-03-17 19:10] Kamera-Qualitaet variiert stark

**Category:** environment | **Severity:** minor | **Attempts:** 1

**Problem:** cam_left deutlich schaerfer als cam_right. Board-Draehte als Diff-Artefakte bei scharfer Kamera.

**Root Cause:** Unterschiedliche Kameramodelle/Fokus.

**Solution:** Dokumentiert als P26. Algorithmus funktioniert auf beiden Qualitaetsstufen (18/18).

**Failed Approaches:** keine

**Takeaway:** Bei Multi-Cam-Setups: frueh Diagnostics einbauen um Kamera-Unterschiede zu erkennen. Algorithmen muessen auf verschiedenen Qualitaetsstufen robust sein.

---

## [2026-03-17 22:00] Ueberzaehlige Klammer bricht DartApp-Klasse ab

**Category:** syntax | **Severity:** critical | **Attempts:** 3

**Problem:** CV-Tuning-Methoden standen ausserhalb der DartApp-Klasse — SyntaxError verhinderte das Laden der gesamten JS-Datei. Tune-Button nicht funktional.

**Root Cause:** Agent-generierter Code hatte eine ueberzaehlige schliessende Klammer } vor den neuen Methoden. Die Klasse endete zu frueh.

**Solution:** Ueberzaehlige } entfernt. Verifiziert mit node -c.

**Failed Approaches:**
- Browser-Caching vermutet — ?v=2 Cache-Busting half nicht
- Preview-Tool-Limitation vermutet — tatsaechlich war der Code fehlerhaft

**Takeaway:** Nach dem Einfuegen von Methoden in JS-Klassen immer `node -c <file>` ausfuehren. Nicht sofort Browser-Caching verdaechtigen — erst Syntax pruefen.

---
