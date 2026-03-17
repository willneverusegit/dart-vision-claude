# Session Log - 2026-03-17 - P21 Calibration Module Split

## Ziel

- `src/cv/calibration.py` entlang echter Workflows aufteilen
- Fehler- und Persistenzpfade der Kalibrierung gezielter testbar machen
- bestehende API fuer Manager, Routen und abhängige Module unveraendert lassen

## Umsetzung

- neue Hilfsmodule angelegt:
  - `src/cv/calibration_common.py` fuer gemeinsame Defaults und Konstanten
  - `src/cv/calibration_store.py` fuer YAML-Load/Atomic-Save und Legacy-Migration
  - `src/cv/calibration_board.py` fuer Manual-/ArUco-/Ring-/Optical-Center-Workflowlogik
  - `src/cv/charuco_detection.py` fuer gemeinsame ChArUco-Frame-Observation
- `src/cv/calibration.py` auf einen schlankeren Manager-/CLI-Wrapper reduziert
- `src/cv/camera_calibration.py` auf die gemeinsame ChArUco-Observation-Hilfe umgestellt
- `tests/test_calibration.py` erweitert um:
  - kamera-spezifisches Laden aus Multi-Cam-Config
  - Legacy-Migration beim Atomic Save
  - ArUco-Fehlerpfad bei fehlender erwarteter Marker-ID
  - ChArUco-Fehlerpfad bei zu wenigen nutzbaren Frames

## Verifikation

- `python -m pytest tests/test_calibration.py tests/test_stereo_calibration.py tests/test_stereo_utils.py tests/test_board_detection_p6.py -q`
- `python -m pytest tests/test_pipeline.py tests/test_web.py -q`
- `python -m pytest -q`

Ergebnis: `512 passed` am 2026-03-17.

## Restrisiken

- Es wurde bewusst nur die interne Struktur getrennt; reale End-to-End-Kalibrierung auf Hardware bleibt weiterhin wichtig.
- `src/cv/multi_camera.py` bleibt der naechste groessere Hardening-Bereich.
