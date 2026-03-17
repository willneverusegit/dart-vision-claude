# CLAUDE.md

Claude-Code-spezifischer Einstieg fuer dieses Repository.

## Projekt-Ueberblick

Dart-Vision ist ein kamerabasiertes Dart-Erkennungssystem (Python/FastAPI). Erkennt Dartpfeile auf dem Board via Computer Vision, berechnet Scores und streamt Ergebnisse ueber eine Web-Oberflaeche.

**Modulstruktur:**
- `src/cv/` — Computer Vision: Kalibrierung, Erkennung, Pipeline, Tip-Detection, Multi-Cam
- `src/game/` — Spiellogik: Engine, Modi, Checkout-Berechnung
- `src/web/` — FastAPI-Server: Routes, Events, Video-Stream
- `src/utils/` — Config, Logging, Telemetrie

## Erst lesen

1. `README.md`
2. `PROJEKTSTAND_2026-03-16.md`
3. `agent_docs/INDEX.md`
4. `agent_docs/claude_code.md`
5. `AGENTS.md`

## Befehle

```bash
pip install -r requirements.txt        # Abhaengigkeiten installieren
python -m src.main                     # App starten (FastAPI + Kamera)
python -m pytest -q                    # Tests ausfuehren
python -m pytest --cov=src -q          # Tests mit Coverage
ruff check src/ tests/                 # Linting
scripts/pre_commit_check.sh            # Pre-Commit Quality Gate
```

## Wichtige Repo-Regeln

- Single-Camera ist der stabile Hauptpfad
- Multi-Camera ist wichtig, aber High-Risk-Bereich
- CPU-only ist gewollt — keine GPU-Pflicht oder schwere ML-Stacks ohne expliziten Userwunsch
- Halte Hardwarelast konservativ
- Kalibrierungsdateien nicht leichtfertig aendern
- Tests fuer betroffene Bereiche immer mitdenken

## Wie Claude Code hier arbeiten soll

- Lies die relevanten Dokumente zuerst, bevor du groessere Refactorings vorschlaegst
- Halte Antworten knapp, aber konkret
- Wenn eine Aufgabe mehrere Teilsysteme beruehrt: kurz die betroffenen Bereiche beschreiben vor der Umsetzung
- Sensible Dateien (`src/main.py`, `src/web/routes.py`, `src/cv/multi_camera.py`) nur mit defensiver Begruendung aendern
- Lies die betroffenen Module und vorhandenen Tests zuerst
- Lies `agent_docs/pitfalls.md` wenn du in einem dort dokumentierten Bereich arbeitest
- Halte Aenderungen klein und pruefbar
- Verschlechtere nicht Startpfad, Kamera-Lifecycle oder Kalibrierung
- Nach Agent-Edits an JS-Dateien: `node -c <file>` zur Syntax-Pruefung ausfuehren
- Bei langen Sessions (>50 Nachrichten oder Multi-Agent-Runs): proaktiv `/save-session` vorschlagen bevor Context knapp wird

## Lesepfade nach Aufgabentyp

### Single-Cam / allgemeine Runtime-Arbeit
1. `agent_docs/current_state.md` → 2. `agent_docs/architecture.md` → 3. `agent_docs/development_workflow.md`

### Multi-Cam
1. `agent_docs/current_state.md` → 2. `agent_docs/architecture.md` → 3. `agent_docs/priorities.md` → 4. `MULTI_CAM_INSTRUCTIONS.md` → 5. `MULTI_CAM_WORKFLOW.md`

### Kalibrierung
1. `agent_docs/current_state.md` → 2. `agent_docs/hardware_constraints.md` → 3. `agent_docs/development_workflow.md`

## Pre-Commit Quality Gate

Vor jedem Commit:
1. `python -m pytest -q` — Tests muessen gruen sein
2. Coverage-Stand pruefen (kein Rueckgang)
3. Wenn `src/` geaendert: pruefen ob `priorities.md` und `current_state.md` aktualisiert wurden

## Abschlussformat

Nenne am Ende immer:
- welche Dateien du geaendert hast
- welche Tests du ausgefuehrt hast
- welche Risiken oder offenen Punkte bleiben

## Umgebung

- Windows: `.venv/Scripts/python.exe` nutzen wenn `.venv/` existiert
- Ruff-Hook laeuft automatisch nach jedem Python-Edit (PostToolUse)
- context7 MCP Server verfuegbar fuer OpenCV/FastAPI-Docs

## Verfuegbare Automations

- `/run-diagnostics` — Kamera-Diagnostik zwischen Kameras vergleichen
- `/session-log` — Session-Abschluss-Workflow (Log, priorities, current_state)
- `/save-session` — Kompletter Session-Abschluss: alle 6 Protokolle gebuendelt (iteration-logger, pattern-extractor, skill-generator, context-keeper, commit, CLAUDE.md revision)
- `/task-splitter` — Grosse Aufgaben in parallele Agenten zerlegen
- `.claude/agents/calibration-reviewer.md` — Review-Agent fuer Kalibrierungs-Aenderungen

## Agent-Workflow (Prozess-Regeln)

Alle Prozess-Regeln fuer Iteration-Logging, Session-Start/-Ende, Prioritaeten-Pflege und Fortschrittsdokumentation stehen in **`agent_docs/agent_workflow.md`**. Lies diese Datei bei Session-Start und vor Session-Ende.
