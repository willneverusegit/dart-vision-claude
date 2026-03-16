# AGENTS.md

Zentrale Arbeitsanweisung fuer Coding Agents in diesem Repository.

Primarziel dieser Datei:

- **Codex**
- andere allgemeine Coding Agents

Claude Code soll zusaetzlich immer `CLAUDE.md` und `agent_docs/claude_code.md` lesen.

## Ziel

Dieses Projekt entwickelt ein CPU-optimiertes Dart-Scoring-System auf Basis von:

- FastAPI
- OpenCV + NumPy
- klassischer Computer Vision
- WebSocket + MJPEG fuer Live-Feedback
- einer Weboberflaeche in Vanilla JS

Agents sollen den aktuellen Stand **stabil weiterentwickeln**, nicht unnoetig neu erfinden.

## Pflicht-Lesereihenfolge

Bevor du an Code arbeitest, lies in dieser Reihenfolge:

1. `README.md`
2. `PROJEKTSTAND_2026-03-16.md`
3. `agent_docs/INDEX.md`
4. `agent_docs/codex.md`, wenn du als Codex arbeitest
5. die fuer deine Aufgabe relevanten Dateien in `agent_docs/`
6. erst dann die betroffenen Code-Module in `src/`, `static/`, `templates/`, `tests/`

## Agentenspezifische Aufteilung

### Codex

- `AGENTS.md` ist die kanonische Hauptdatei.
- zusaetzlich `agent_docs/codex.md` lesen

### Claude Code

- `CLAUDE.md` ist der Einstieg
- danach `AGENTS.md`
- danach `agent_docs/claude_code.md`

Wenn sich Anweisungen unterscheiden:

1. aufgabenspezifische Detaildatei in `agent_docs/`
2. `AGENTS.md` oder `CLAUDE.md` fuer den jeweiligen Agenten
3. Code und Tests

## Projektwahrheiten

Diese Punkte gelten als aktueller Arbeitsstand:

- **Single-Camera** ist der stabile Hauptpfad.
- **Multi-Camera** ist funktional weit entwickelt, aber noch nicht voll betriebsstabil.
- Das Zielsystem ist ein **Laptop ohne dedizierte GPU**.
- CPU-only ist kein Fallback, sondern der geplante Betriebsmodus.
- Treffer werden bewusst ueber einen **Hit-Candidate-Review-Flow** bestaetigt.
- Kalibrierung ist zentral fuer die reale Nutzbarkeit.

## Nicht verhandlungsfaehige Leitplanken

1. Verschlechtere den Single-Camera-Pfad nicht, nur um Multi-Cam schneller voranzubringen.
2. Fuehre keine GPU-Pflicht, kein Deep Learning und keine schweren Laufzeitabhaengigkeiten ein, wenn der User das nicht explizit fordert.
3. Erhoehe Last nicht stillschweigend durch hoehere Kamera-Defaults, ungebremste Threads, grosse Queues oder ungebundene Speicherpuffer.
4. Behandle `config/calibration_config.yaml` und `config/multi_cam.yaml` als reale Betriebsdaten, nicht als Wegwerf-Testdateien.
5. Aendere Kalibrierungs- oder API-Verhalten nicht ohne passende Tests und Doku-Anpassung.
6. Bevorzuge kleine, pruefbare Schritte vor grossen Umbauten.

## Fokus fuer Weiterentwicklung

Wenn keine andere Priorisierung vom User kommt, arbeite in dieser Reihenfolge:

1. Runtime-Stabilitaet und sauberer Pipeline-Lifecycle
2. Vorhersagbare Hardwarelast auf dem Ziel-Laptop
3. Testabdeckung fuer betriebsnahe Pfade
4. Reale End-to-End-Verifikation mit Replay oder Referenzmaterial
5. Multi-Camera-Haertung
6. Bedienbarkeit und gefuehrte Kalibrierung

## Erwartetes Arbeitsverhalten

### Vor dem Coden

- pruefe, welche Module betroffen sind
- suche vorhandene Tests
- lies die dazugehoerigen Agent-Dokumente
- identifiziere, ob Single-Cam, Multi-Cam, Kalibrierung, UI oder Spiel-Engine betroffen sind

### Beim Coden

- erhalte bestehende APIs, wenn kein Bruch verlangt ist
- kapsle neue Komplexitaet statt sie in `routes.py` oder `main.py` zu kippen
- halte Nebenwirkungen sichtbar
- bevorzuge konservative Defaults
- schreibe oder erweitere gezielte Tests mit jeder relevanten Logikaenderung

### Nach dem Coden

Fuehre mindestens die naheliegenden Checks aus. Typische Kommandos:

```powershell
python -m pytest -q
python -m pytest tests/test_pipeline.py tests/test_web.py -q
python -m pytest tests/test_multi_camera.py tests/test_multi_cam_config.py -q
python -m tests.benchmark_pipeline --duration 5 --cameras 1
```

Wenn du Tests nicht ausfuehren konntest, benenne das explizit.

## Aenderungsregeln nach Bereich

### CV / Pipeline

- bewahre die ROI-Zielgroesse und bounded-queue-Strategie, sofern nicht bewusst verbessert
- vermeide unkontrollierte Mehrarbeit pro Frame
- messe Performance-Auswirkungen, wenn du pro Frame neue Berechnungen einfuehrst

### Multi-Camera

- gehe davon aus, dass dieser Bereich sensibel ist
- behandle Lifecycle, Threading, Stereo-Daten und Fallback-Pfade als Hochrisiko
- veraendere Multi-Cam nur mit passenden Tests

### Kalibrierung

- erhalte Rueckwaertskompatibilitaet fuer gespeicherte YAML-Daten, wenn moeglich
- beachte `schema_version`
- dokumentiere jede Aenderung am Workflow

### Web / UI

- erhalte den aktuellen Vanilla-JS-Ansatz
- fuehre kein Framework ein, wenn es nicht explizit gefordert wird
- bevorzuge klare Fehlertexte und gefuehrte Nutzerfluesse

### Spiel-Engine

- Spielregeln muessen deterministisch bleiben
- neue Regelvarianten nur mit direkter Testabdeckung

## Standard-Deliverable fuer Agents

Ein guter Beitrag in diesem Repo enthaelt:

- den eigentlichen Codefix oder die Erweiterung
- passende Tests oder nachvollziehbare Begruendung, falls Tests fehlen
- kurze Aktualisierung betroffener Doku, wenn sich Verhalten aendert
- klare Aussage zu Restrisiken

## Codex-spezifische Erwartungen

Diese Hinweise sind besonders fuer Codex relevant:

- arbeite standardmaessig autonom und setze Aenderungen direkt um, statt nur Plaene zu skizzieren
- lies erst Code und Tests, dann aendere
- bevorzuge kleine, in sich pruefbare Commits von Logik
- wenn du mehrere moegliche Ursachen siehst, arbeite zuerst die mit dem hoechsten Laufzeitrisiko ab
- nenne in deiner Abschlussmeldung immer:
  - was geaendert wurde
  - was verifiziert wurde
  - was offen bleibt

## Dokumentenkarte

- `CLAUDE.md` - kompakter Einstieg fuer Claude-kompatible Agents
- `agent_docs/codex.md` - Codex-spezifische Arbeitsweise
- `agent_docs/claude_code.md` - Claude-Code-spezifische Arbeitsweise
- `AGEND.md` - Kompatibilitaetsalias auf diese Anweisungen
- `agent_docs/INDEX.md` - Einstieg und Lesepfade
- `agent_docs/current_state.md` - aktueller fachlicher und technischer Stand
- `agent_docs/architecture.md` - Systemaufbau und Dateikarte
- `agent_docs/hardware_constraints.md` - Designgrenzen fuer das Zielgeraet
- `agent_docs/development_workflow.md` - Arbeitsregeln, Testmatrix, Change-Checkliste
- `agent_docs/priorities.md` - priorisierte Weiterentwicklungsziele
