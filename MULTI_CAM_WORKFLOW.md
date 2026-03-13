# Multi-Kamera Implementierung — Workflow für Claude Code

> **Zweck:** Diese Datei steuert die schrittweise Abarbeitung der Multi-Kamera-Erweiterung.
> Die technischen Details stehen in `MULTI_CAM_INSTRUCTIONS.md` (gleicher Ordner).
>
> **Ablauf:** Ein Step pro Claude-Code-Session. Nach jedem Step: `pytest` laufen lassen,
> Diff reviewen, committen. Erst dann den nächsten Step starten.

---

## Vorbereitung

1. Lege beide Dateien ins Projekt-Root:
   ```
   dart-vision-claude/
   ├── MULTI_CAM_INSTRUCTIONS.md   ← Technische Spezifikation
   ├── MULTI_CAM_WORKFLOW.md        ← Diese Datei (Workflow-Steuerung)
   ├── AGENTS.md                    ← Bestehende Agent-Instruktionen
   ├── CLAUDE.md → AGENTS.md        ← Symlink bleibt unverändert
   └── ...
   ```

2. Stelle sicher, dass die Test-Suite vorher grün ist:
   ```bash
   pytest --tb=short -q
   ```

3. Erstelle einen Feature-Branch:
   ```bash
   git checkout -b feature/multi-camera
   ```

---

## Prompts (Copy-Paste für Claude Code)

### Step 2: Konfigurations-Refactoring

```
Lies MULTI_CAM_INSTRUCTIONS.md, Abschnitt "Step 2: Konfigurations-Refactoring".

Setze NUR Step 2 um. Fasse die bestehende Codebase NICHT anders an als dort beschrieben.

Zusammenfassung der Aufgaben:
- CalibrationManager um camera_id Parameter erweitern (Default: "default")
- Legacy-Config (flaches YAML) transparent migrieren auf cameras.<id>-Struktur
- File-Level Lock für gleichzeitigen Zugriff einbauen
- BoardCalibrationManager und CameraCalibrationManager: camera_id durchreichen
- config/multi_cam.yaml Skelett anlegen
- src/utils/config.py um Stereo-Paar-Funktionen erweitern
- Neue Tests in tests/test_multi_cam_config.py schreiben

Qualitätskriterien:
- pytest muss mit 0 Failures durchlaufen (bestehende + neue Tests)
- Einzelkamera-Betrieb (camera_id="default") muss identisch funktionieren
- Kein Breaking Change an öffentlichen APIs

Wenn du fertig bist, zeige mir: geänderte Dateien, neue Dateien, pytest-Ergebnis.
```

**Nach Step 2:**
```bash
pytest --tb=short -q
git add -A && git commit -m "feat: multi-cam config refactoring (Step 2)

- CalibrationManager supports camera_id parameter
- Legacy YAML auto-migrated to cameras.<id> structure
- File-level lock for concurrent access
- config/multi_cam.yaml skeleton for stereo extrinsics
- Stereo pair helpers in src/utils/config.py"
```

---

### Step 3: Stereo-Kalibrierung

```
Lies MULTI_CAM_INSTRUCTIONS.md, Abschnitt "Step 3: Stereo-Kalibrierung implementieren".

Setze NUR Step 3 um. Step 2 ist bereits implementiert und committet.

Zusammenfassung der Aufgaben:
- src/cv/stereo_calibration.py: stereo_calibrate() und detect_charuco_corners()
- StereoResult NamedTuple
- Tests in tests/test_stereo_calibration.py (Fehlerhandling, Interfaces)
- API-Stub /api/calibration/stereo in routes.py
- __init__.py Exporte aktualisieren

Qualitätskriterien:
- pytest muss mit 0 Failures durchlaufen
- Keine Änderungen an Step-2-Code nötig (wenn doch: explizit benennen warum)

Wenn du fertig bist, zeige mir: geänderte Dateien, neue Dateien, pytest-Ergebnis.
```

**Nach Step 3:**
```bash
pytest --tb=short -q
git add -A && git commit -m "feat: stereo calibration module (Step 3)

- stereo_calibrate() with ChArUco DICT_6X6_250
- detect_charuco_corners() helper
- API stub /api/calibration/stereo
- Error handling and interface tests"
```

---

### Step 4: Multi-Kamera-Pipeline

```
Lies MULTI_CAM_INSTRUCTIONS.md, Abschnitt "Step 4: Multi-Kamera-Pipeline bauen".

Setze NUR Step 4 um. Steps 2–3 sind bereits implementiert.

Zusammenfassung der Aufgaben:
- src/cv/stereo_utils.py: CameraParams, triangulate_point(), point_3d_to_board_2d()
- src/cv/multi_camera.py: MultiCameraPipeline mit Thread-pro-Kamera, Fusion-Thread,
  Zeitfenster-Synchronisation (MAX_DETECTION_TIME_DIFF_S = 0.15),
  Triangulation + Voting-Fallback
- Tests: tests/test_stereo_utils.py (synthetische Triangulation)
- Tests: tests/test_multi_camera.py (Lifecycle, Fallback, Buffer)
- __init__.py Exporte

Qualitätskriterien:
- pytest 0 Failures
- DartPipeline bleibt unverändert (Einzelkamera-Betrieb unberührt)
- Thread-Safety: _buffer_lock konsequent nutzen

Wenn du fertig bist, zeige mir: geänderte Dateien, neue Dateien, pytest-Ergebnis.
```

**Nach Step 4:**
```bash
pytest --tb=short -q
git add -A && git commit -m "feat: multi-camera pipeline with triangulation (Step 4)

- CameraParams + triangulate_point() in stereo_utils
- MultiCameraPipeline: thread-per-camera, fusion thread
- Software sync via 150ms time window
- Triangulation with voting fallback
- Single-camera fallback on timeout"
```

---

### Step 5: API und Frontend

```
Lies MULTI_CAM_INSTRUCTIONS.md, Abschnitt "Step 5: API und Frontend anpassen".

Setze NUR Step 5 um. Steps 2–4 sind bereits implementiert.

Zusammenfassung der Aufgaben:
- src/main.py: app_state erweitern, _run_multi_pipeline Funktion
- src/web/routes.py: /api/multi/start, /api/multi/stop, /api/multi/status,
  /api/calibration/stereo vollständig implementieren
- WebSocket: Score-Events transparent aus Single- oder Multi-Pipeline
- Frontend: Kamera-Auswahl UI, Multi-Video-Grid, Stereo-Kalibrierung im Modal
- README.md: Multi-Kamera-Dokumentation (Hardware, Platzierung, Workflow)

Qualitätskriterien:
- pytest 0 Failures
- Einzelkamera-Modus (kein /api/multi/start aufgerufen) funktioniert wie bisher
- Frontend graceful degradation: ohne Multi-Pipeline sieht UI aus wie vorher

Wenn du fertig bist, zeige mir: geänderte Dateien, neue Dateien, pytest-Ergebnis.
```

**Nach Step 5:**
```bash
pytest --tb=short -q
git add -A && git commit -m "feat: multi-camera API routes and frontend (Step 5)

- /api/multi/start, /stop, /status endpoints
- /api/calibration/stereo fully implemented
- Multi-camera video grid in frontend
- Stereo calibration UI in modal
- README updated with multi-camera documentation"
```

---

### Step 6: Tests, Benchmarks, Feinschliff

```
Lies MULTI_CAM_INSTRUCTIONS.md, Abschnitt "Step 6: Tests, Benchmarks und Feinschliff".

Setze NUR Step 6 um. Steps 2–5 sind bereits implementiert.

Zusammenfassung der Aufgaben:
- tests/benchmark_pipeline.py: --cameras N Parameter, neue KPIs für Mehrkamera
- tests/test_multi_robustness.py: Kamera-Ausfall, Z<0, Timeout, Confidence-Voting
- src/utils/logger.py: JSON-Logging-Option
- MultiCameraPipeline: Voting-Fallback gewichten nach Confidence
- Alle Log-Meldungen in Multi-Modulen enthalten camera_id

Qualitätskriterien:
- Gesamte Test-Suite grün
- Benchmark mit --cameras 2 zeigt Ergebnisse
- Kein Regression in Einzelkamera-Performance

Wenn du fertig bist, zeige mir: geänderte Dateien, neue Dateien, pytest-Ergebnis,
Benchmark-Ergebnis mit --cameras 1 und --cameras 2.
```

**Nach Step 6:**
```bash
pytest --tb=short -q
python -m tests.benchmark_pipeline --duration 5
python -m tests.benchmark_pipeline --duration 5 --cameras 2
git add -A && git commit -m "feat: multi-camera benchmarks and hardening (Step 6)

- Benchmark supports --cameras N parameter
- Robustness tests for camera dropout, Z<0, timeout
- JSON logging option
- Confidence-weighted voting fallback
- All multi-cam logs include camera_id"
```

---

## Nach Abschluss aller Steps

```bash
# Feature-Branch in main mergen
git checkout main
git merge feature/multi-camera

# Gesamte Suite nochmal
pytest --tb=short -q

# Optional: Tag setzen
git tag v0.3.0-multi-cam
```

---

## Troubleshooting

| Problem | Lösung |
|---------|--------|
| Claude Code will mehrere Steps gleichzeitig machen | Prompt wiederholen: "NUR Step N, nichts anderes" |
| Bestehende Tests brechen nach Step 2 | Wahrscheinlich Migration-Bug: CalibrationManager ohne camera_id muss "default" nutzen |
| pytest hängt in Step 4 (Threads) | Prüfe ob Threads in Tests sauber gestoppt werden (Fixtures mit Teardown) |
| Claude Code ändert Dateien ausserhalb des Steps | Explizit sagen: "Revertiere alle Änderungen die nicht in Step N beschrieben sind" |
| Import-Fehler nach neuem Modul | __init__.py Exporte vergessen — Claude Code daran erinnern |
