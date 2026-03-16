# Multi-Camera Workflow

Operativer Workflow fuer Coding Agents, die am Multi-Camera-Bereich arbeiten.

Diese Datei ist die praktische Arbeitssteuerung zu:

- `MULTI_CAM_INSTRUCTIONS.md`
- `AGENTS.md`
- `CLAUDE.md`
- `agent_docs/development_workflow.md`
- `agent_docs/priorities.md`

## Grundregel

Nur **ein klar abgegrenztes Multi-Cam-Work-Package pro Session**.

Nicht in einer Runde gleichzeitig:

- Lifecycle umbauen
- UI umbauen
- Kalibrierung umbauen
- Benchmarks umbauen

Wenn mehrere Themen noetig sind, zuerst den risikoreichsten Block isoliert fertig machen.

## Vorbereitung

Vor jeder Multi-Cam-Arbeit:

1. `README.md` lesen
2. `AGENTS.md` oder `CLAUDE.md` lesen
3. `MULTI_CAM_INSTRUCTIONS.md` lesen
4. relevante Dateien in `agent_docs/` lesen
5. betroffene Module und Tests oeffnen

## Empfohlene Reihenfolge fuer aktuelle Weiterentwicklung

### Phase 1: Lifecycle und Runtime-Sicherheit

Typische Aufgaben:

- Start/Stop robuster machen
- Thread-Besitz klaeren
- State-Umschaltung Single <-> Multi haerten

### Phase 2: Kamera-Konfiguration und Lastbegrenzung

Typische Aufgaben:

- Aufloesung/FPS konfigurierbar machen
- konservative Defaults
- bessere Fehlermeldungen bei ungeeignetem Setup

### Phase 3: Setup- und Kalibrierungs-Haertung

Typische Aufgaben:

- fehlende Intrinsics/Extrinsics sauber melden
- bessere Route- und UI-Fehlerpfade
- klarere Setup-Fuehrung

### Phase 4: Diagnose und Hardwarevalidierung

Typische Aufgaben:

- Telemetrie
- Replay-Validierung
- Benchmark-Auswertung

## Agentenspezifische Arbeitsweise

### Codex

Codex sollte:

- klein anfangen
- direkt umsetzen
- sofort die relevanten Tests ausfuehren
- den Scope nicht unnoetig verbreitern

Empfohlener Arbeitsablauf:

1. betroffenes Work Package festlegen
2. Risikodateien lesen
3. Tests lesen
4. kleinsten wirksamen Eingriff machen
5. gezielte Tests
6. optional Gesamttests

### Claude Code

Claude Code sollte:

- den betroffenen Bereich zuerst kurz strukturieren
- bei High-Risk-Dateien defensiv aendern
- den Eingriff und Restrisiken explizit benennen

Empfohlener Arbeitsablauf:

1. betroffene Teilsysteme benennen
2. relevanten Lesepfad in `agent_docs/` ziehen
3. kleinsten sinnvollen Eingriff waehlen
4. gezielte Verifikation
5. offene Folgepunkte knapp benennen

## Copy-Paste-Auftraege fuer Agents

Die folgenden Aufgaben sind auf den aktuellen Projektstand zugeschnitten.

### Auftrag A: Lifecycle Hardening

```text
Lies README.md, AGENTS.md bzw. CLAUDE.md, MULTI_CAM_INSTRUCTIONS.md und die relevanten Dateien in agent_docs/.

Arbeite nur am Multi-Cam-Lifecycle. Ziel:
- sauberes Start/Stop-Verhalten
- kein Thread-Leak beim Wechsel zwischen Single und Multi
- keine Regression im Single-Cam-Startpfad

Bearbeite nur die minimal noetigen Dateien. Fuehre danach gezielte Tests aus und nenne Restrisiken.
```

### Auftrag B: Kamera-Input kontrollierbar machen

```text
Lies README.md, AGENTS.md bzw. CLAUDE.md, MULTI_CAM_INSTRUCTIONS.md und agent_docs/hardware_constraints.md.

Arbeite nur daran, die reale Kamera-Last fuer Multi-Cam vorhersehbarer zu machen. Ziel:
- explizite Aufloesungs-/FPS-Steuerung oder konservative Defaults
- keine unkontrollierte Mehrlast auf dem Ziel-Laptop
- Single-Cam weiter intakt

Fuehre danach die relevanten Pipeline-Tests und den Benchmark fuer 1 und 2 Kameras aus.
```

### Auftrag C: Kalibrierungs- und Setup-Haertung

```text
Lies README.md, AGENTS.md bzw. CLAUDE.md, MULTI_CAM_INSTRUCTIONS.md und agent_docs/development_workflow.md.

Arbeite nur am Multi-Cam-Setup und an der Kalibrierungs-Haertung. Ziel:
- bessere Fehlertexte
- robustere Routen und Guards
- klarere Diagnose bei fehlenden Intrinsics, Stereo-Daten oder Board-Transforms

Fuehre danach gezielte Kalibrierungs- und Web-Tests aus.
```

### Auftrag D: Diagnose und Telemetrie

```text
Lies README.md, AGENTS.md bzw. CLAUDE.md, MULTI_CAM_INSTRUCTIONS.md und agent_docs/priorities.md.

Arbeite nur an Multi-Cam-Diagnose und Telemetrie. Ziel:
- Status und Probleme auf echter Hardware besser sichtbar machen
- keine schwere neue Runtime-Last
- API und UI konsistent halten

Fuehre danach die relevanten Web-, Multi-Cam- und Robustheitstests aus.
```

## Mindest-Checks je Session

### Bei Logik in `src/cv/multi_camera.py`

```powershell
python -m pytest tests/test_multi_camera.py tests/test_multi_robustness.py -q
```

### Bei Aenderungen an Konfiguration oder Stereo/Kalibrierung

```powershell
python -m pytest tests/test_multi_cam_config.py tests/test_stereo_calibration.py tests/test_stereo_utils.py -q
```

### Bei API/UI-Aenderungen

```powershell
python -m pytest tests/test_web.py tests/test_routes_extra.py tests/test_websocket.py -q
```

### Bei Last- oder Hot-Path-Aenderungen

```powershell
python -m tests.benchmark_pipeline --duration 5 --cameras 1
python -m tests.benchmark_pipeline --duration 5 --cameras 2
```

## Abschluss einer Multi-Cam-Session

Am Ende sollte der Agent berichten:

- welches Work Package bearbeitet wurde
- welche Dateien geaendert wurden
- welche Tests oder Benchmarks gelaufen sind
- welche Risiken offen bleiben

## Was diese Datei bewusst nicht mehr ist

Diese Datei ist kein alter Step-2-bis-Step-6-Implementierungsplan mehr. Wenn groessere neue Multi-Cam-Funktionen geplant werden, sollten sie als neue Work Packages in dieser Datei und in `MULTI_CAM_INSTRUCTIONS.md` beschrieben werden, statt den historischen Plan wiederzubeleben.
