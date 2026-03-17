# Development Workflow

## Grundregel

Arbeite so, dass die naechste Aenderung:

- lokal nachvollziehbar
- testbar
- hardwarebewusst
- ruecknehmbar

ist.

## Vor jeder Aenderung

1. betroffene Module bestimmen
2. vorhandene Tests lesen
3. Risiken einschaetzen:
   - Single-Cam?
   - Multi-Cam?
   - Kalibrierung?
   - Start/Stop?
   - UI/API?
4. entscheiden, welche minimale Testmatrix noetig ist

## Testmatrix nach Bereich

### Spiel-Engine

```powershell
python -m pytest tests/test_game_engine.py tests/test_modes.py -q
```

### Web und API

```powershell
python -m pytest tests/test_web.py tests/test_websocket.py tests/test_routes_extra.py -q
```

### Single-Camera / Pipeline

```powershell
python -m pytest tests/test_pipeline.py tests/test_detector.py tests/test_geometry.py -q
python -m tests.benchmark_pipeline --duration 5 --cameras 1
```

### Multi-Camera

```powershell
python -m pytest tests/test_multi_camera.py tests/test_multi_cam_config.py tests/test_multi_robustness.py -q
python -m tests.benchmark_pipeline --duration 5 --cameras 2
```

### Kalibrierung

```powershell
python -m pytest tests/test_calibration.py tests/test_stereo_calibration.py tests/test_stereo_utils.py -q
```

### Bei unsicherem Impact

```powershell
python -m pytest -q
```

## Change-Checkliste

Vor Abgabe einer Aenderung sollte ein Agent pruefen:

- Bleibt der Single-Camera-Startpfad intakt?
- Bleibt die API rueckwaertskompatibel oder ist der Bruch dokumentiert?
- Wurden relevante Tests angepasst oder ergaenzt?
- Wurden Konfigurationsschluessel oder Schemas geaendert?
- Wurde die Hardwarelast stillschweigend erhoeht?
- Ist die Doku noch konsistent?
- Hinterlaesst der Lauf keine neu getrackten Python-Artefakte (`__pycache__`, `.pyc`)?

## Artefakt-Hygiene

- Python-Artefakte und pytest-Caches sind per `.gitignore` ausgeschlossen und sollen lokal bleiben.
- Falls historisch getrackte Cache-Dateien wieder im Worktree auftauchen, entferne sie aus dem Git-Tracking mit:

```powershell
git rm --cached -r src/__pycache__ src/cv/__pycache__ src/game/__pycache__ src/utils/__pycache__ src/web/__pycache__ tests/__pycache__
```

- Danach keine generierten Artefakte wieder einchecken; die lokale Laufzeitkopie darf bestehen bleiben.

## Spezielle Regeln fuer sensible Bereiche

### `src/main.py`

- dort keine komplexe neue Logik einbetten, wenn sie kapselbar ist
- Lifecycle-Aenderungen nur mit besonderer Vorsicht

### `src/web/routes.py`

- keine schwergewichtige Fachlogik direkt im Route-Handler, wenn sie extrahierbar ist
- neue Endpunkte mit Tests

### `src/cv/multi_camera.py`

- timing- und threadbezogene Aenderungen immer testen
- Fallbacks nicht still entfernen

### `config/*.yaml`

- Struktur aendern nur kontrolliert
- `schema_version` beachten

## Doku-Regel

Wenn du einen Workflow, eine Prioritaet oder einen grundlegenden Betriebsweg veraenderst, aktualisiere:

- `AGENTS.md` falls die generelle Repo-Anweisung betroffen ist
- passende Datei in `agent_docs/`
- optional `PROJEKTSTAND_2026-03-16.md`, wenn die Aenderung den dokumentierten Ist-Stand klar ueberholt

## Was ein Agent in der finalen Antwort benennen sollte

- was geaendert wurde
- welche Tests gelaufen sind
- was nicht verifiziert wurde
- welche Restrisiken bleiben

