# Multi-Camera Instructions

Leitfaden fuer die Weiterentwicklung des Multi-Camera-Bereichs im aktuellen Projektstand.

Diese Datei ersetzt den frueheren sequenziellen Implementierungsplan. Der Multi-Cam-Stack ist im Repository bereits weitgehend vorhanden. Ziel ist jetzt nicht mehr "von null aufbauen", sondern den vorhandenen Stand kontrolliert weiterzuentwickeln.

## Einordnung

Diese Datei ist eine bereichsspezifische Ergaenzung zu:

- `AGENTS.md`
- `CLAUDE.md`
- `agent_docs/INDEX.md`
- `agent_docs/priorities.md`
- `agent_docs/architecture.md`

Wenn sich Aussagen widersprechen, gilt in dieser Reihenfolge:

1. Code und Tests
2. `AGENTS.md` oder `CLAUDE.md` fuer den jeweiligen Agenten
3. `agent_docs/`
4. diese Datei

## Ziel des Multi-Cam-Bereichs

Die Multi-Camera-Erweiterung soll:

- mehrere Kameras parallel betreiben
- detections zeitlich synchronisieren
- Treffer per Triangulation oder Voting-Fallback fusionieren
- pro Kamera eigene Kalibrierungsdaten nutzen
- in die bestehende Single-Cam- und Hit-Candidate-Logik integrierbar bleiben

## Aktueller Stand

Der folgende Funktionsumfang ist bereits im Code vorhanden:

- `config/multi_cam.yaml`
- per-Kamera Kalibrierungsdaten
- `src/cv/stereo_calibration.py`
- `src/cv/stereo_utils.py`
- `src/cv/multi_camera.py`
- Multi-Cam-Routen in `src/web/routes.py`
- Multi-Cam-UI in `templates/index.html` und `static/js/app.js`
- Benchmark mit `--cameras`
- Tests fuer Config, Stereo, Multi-Cam und Robustheit

Das bedeutet:

- diese Datei ist keine Gruenfeld-Spezifikation mehr
- Aenderungen muessen auf den bestehenden Code ruecksicht nehmen

## Arbeitsannahmen

1. Single-Camera bleibt der stabile Hauptpfad.
2. Multi-Camera ist ein High-Risk-Bereich.
3. CPU-only bleibt harte Vorgabe.
4. Multi-Cam darf Single-Cam nicht destabilisieren.
5. Reale Nutzbarkeit ist wichtiger als theoretische Eleganz.

## High-Risk-Dateien

Besonders vorsichtig arbeiten in:

- `src/main.py`
- `src/web/routes.py`
- `src/cv/multi_camera.py`
- `src/cv/stereo_calibration.py`
- `src/cv/stereo_utils.py`
- `config/multi_cam.yaml`

## Bereiche, die nicht stillschweigend gebrochen werden duerfen

### 1. Single-Camera-Startpfad

- Standardstart darf weiter ohne Multi-Cam-Konfiguration funktionieren.
- `config/multi_cam.yaml` im Modus `single` muss weiter der sichere Default sein.

### 2. Hit-Candidate-Review-Flow

- Multi-Cam darf die bestaetigen/verwerfen/korrigieren-Logik nicht umgehen.
- Auch fusionierte Treffer sollen weiter als Kandidaten ins System gehen.

### 3. Kalibrierungsdaten

- Bestehende Schluessel in `config/multi_cam.yaml` nicht leichtfertig umbenennen.
- `schema_version` beachten.
- Rueckwaertskompatibilitaet bevorzugen.

### 4. Hardwareverhalten

- keine unkontrollierte Mehrlast durch hoehere Kameraauflosungen, groessere Buffers oder ungebremste Polling-Loops

## Was aktuell priorisiert werden soll

Diese Prioritaeten leiten sich aus `agent_docs/priorities.md` ab und gelten speziell fuer Multi-Cam:

1. Pipeline-Lifecycle stabilisieren
2. Kamera-Input kontrollierbar machen
3. betriebsnahe Testabdeckung erhoehen
4. Replay- und E2E-Verifikation verbessern
5. Setup und Diagnose haerten

## Empfohlene Work Packages

Immer nur ein Work Package pro Aenderungsrunde.

### Work Package A: Lifecycle Hardening

Ziel:

- sauberes Start/Stop-Verhalten
- kein Thread-Leak beim Wechsel zwischen Single und Multi
- klarer Besitz von Hintergrundthreads und Stop-Signalen

Typische Dateien:

- `src/main.py`
- `src/web/routes.py`
- `src/cv/multi_camera.py`

Erwartete Verifikation:

```powershell
python -m pytest tests/test_multi_camera.py tests/test_multi_robustness.py tests/test_web.py -q
python -m pytest -q
```

### Work Package B: Kamera-Last kontrollierbar machen

Ziel:

- explizite Aufloesungs-/FPS-Steuerung
- konservative Defaults fuer Zielhardware

Typische Dateien:

- `src/cv/capture.py`
- `src/cv/multi_camera.py`
- `config/multi_cam.yaml`
- eventuell UI/API fuer Kameraoptionen

Erwartete Verifikation:

```powershell
python -m pytest tests/test_pipeline.py tests/test_multi_camera.py -q
python -m tests.benchmark_pipeline --duration 5 --cameras 1
python -m tests.benchmark_pipeline --duration 5 --cameras 2
```

### Work Package C: Kalibrierungs- und Setup-Haertung

Ziel:

- klarere Fehlermeldungen
- robustere Validierung fehlender Intrinsics/Extrinsics/Board-Transforms
- weniger "silent fallback" ohne Diagnose

Typische Dateien:

- `src/web/routes.py`
- `src/utils/config.py`
- `src/cv/stereo_calibration.py`
- `static/js/app.js`

Erwartete Verifikation:

```powershell
python -m pytest tests/test_calibration.py tests/test_stereo_calibration.py tests/test_multi_cam_config.py -q
```

### Work Package D: Diagnose und Telemetrie

Ziel:

- sichtbare Statusdaten fuer echte Hardwaretests
- Dropped Frames, Kamerafehler, Kalibrierungsstatus, ggf. CPU/RAM-Indikatoren

Typische Dateien:

- `src/main.py`
- `src/web/routes.py`
- `src/cv/pipeline.py`
- `src/cv/multi_camera.py`
- `static/js/app.js`

Erwartete Verifikation:

```powershell
python -m pytest tests/test_web.py tests/test_routes_extra.py tests/test_multi_robustness.py -q
```

### Work Package E: Reale Verifikation

Ziel:

- Replay- und Referenzmaterial staerker nutzen
- nicht nur synthetische Korrektheit, sondern reale Nutzbarkeit absichern

Typische Dateien:

- `tests/benchmark_pipeline.py`
- `tests/ground_truth/*`
- `tests/replays/*`
- neue Replay- oder Accuracy-Tests

## Technische Invarianten

Diese Invarianten sollten Agents nach Moeglichkeit erhalten:

- `MAX_DETECTION_TIME_DIFF_S` bleibt bewusst eng und nachvollziehbar
- Fusion muss weiter Fallbacks besitzen
- Kamera-spezifische Kalibrierung bleibt ueber `camera_id` adressierbar
- MJPEG- und WebSocket-Verhalten soll fuer das Frontend transparent bleiben

## Was Agents in Multi-Cam vermeiden sollen

1. Komplettumbau von `MultiCameraPipeline`, wenn ein kleiner gezielter Eingriff reicht.
2. Implizite Annahme, dass Stereo-Parameter oder Board-Transforms immer vorhanden sind.
3. Neue Hot-Path-Arbeit pro Frame ohne Benchmark oder Begrenzung.
4. API- oder YAML-Breaking-Changes ohne Migrationsstrategie.
5. Multi-Cam-Verbesserungen, die Single-Cam unbeabsichtigt mitziehen.

## Mindestverifikation nach Multi-Cam-Aenderungen

Je nach Eingriff mindestens:

```powershell
python -m pytest tests/test_multi_camera.py tests/test_multi_robustness.py tests/test_multi_cam_config.py -q
```

Bei Lifecycle-, API- oder UI-Eingriffen zusaetzlich:

```powershell
python -m pytest tests/test_web.py tests/test_routes_extra.py tests/test_websocket.py -q
```

Bei Performance-relevanten Aenderungen zusaetzlich:

```powershell
python -m tests.benchmark_pipeline --duration 5 --cameras 1
python -m tests.benchmark_pipeline --duration 5 --cameras 2
```

## Was eine gute Multi-Cam-Aenderung enthalten sollte

- klaren Scope
- kein versehentliches Single-Cam-Regressionsrisiko
- gezielte Tests
- bei Bedarf Doku-Update in:
  - `README.md`
  - `agent_docs/priorities.md`
  - `MULTI_CAM_WORKFLOW.md`
