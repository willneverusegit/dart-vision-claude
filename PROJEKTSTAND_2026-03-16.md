# Projektstand Dart-Vision

## Zweck und Grundlage

Dieses Dokument beschreibt den aktuellen Stand des Projekts `dart-vision-claude` zum Stand **2026-03-16**. Die Bewertung basiert auf:

- dem aktuellen Repository-Inhalt
- der Hardwarevorgabe aus `C:/Users/domes/OneDrive/Desktop/Laptop_hardware/hardware_constraints.md`
- einer Codeanalyse der Kernmodule
- ausgefuehrten Tests und Benchmarks im aktuellen Workspace

Die Hardwarebewertung wird bewusst in zwei Ebenen getrennt:

- **belegt**: direkt aus Code, Konfiguration oder ausgefuehrten Tests ableitbar
- **abgeleitet**: technische Einschaetzung aus Architektur und Ressourcenprofil

## Kurzfazit

Der aktuelle Projektstand ist fuer einen **CPU-only Laptop der Klasse Intel i5-1035G1** grundsaetzlich **lauffaehig**. Das gilt insbesondere fuer den **Single-Camera-Betrieb**, der im aktuellen Repository den reifesten Zustand hat. Die Architektur ist klar auf klassische Computer Vision mit OpenCV und ohne GPU-Zwang ausgelegt. Das passt gut zu den vorgegebenen Hardwaregrenzen.

Fuer **Multi-Camera** ist bereits viel Funktionalitaet vorhanden, inklusive Kalibrierung, Stereo-Parametern, Triangulation und UI-Unterstuetzung. Dieser Bereich ist aber noch nicht auf demselben Reifegrad wie der Single-Cam-Pfad. Aus dem Code ergibt sich vor allem ein Risiko in der **Pipeline-Lifecycle-Steuerung** beim Umschalten zwischen Single- und Multi-Cam. Das ist aktuell der wichtigste technische Punkt fuer die reale Betriebsstabilitaet.

## Projektueberblick

### Technologiestack

- Backend: FastAPI
- CV-Core: OpenCV + NumPy
- Frontend: HTML, CSS, Vanilla JavaScript
- Kommunikation: REST + WebSocket + MJPEG-Streams
- Konfiguration: YAML
- Tests: pytest, pytest-asyncio, pytest-cov

### Grobe Codebasis-Kennzahlen

- `29` Python-Dateien in `src/`
- `4` JavaScript-Dateien in `static/js/`
- `1` HTML-Template in `templates/`
- `21` Testdateien in `tests/`
- ca. `4363` Zeilen Python-Anwendungslogik in `src/`
- ca. `2474` Zeilen Frontend-Code in `static/` und `templates/`
- ca. `2228` Zeilen Testcode

### Arbeitsstand des Repositories

Das Repository ist zum Bewertungszeitpunkt **nicht in einem sauberen Git-Zustand**. `git status --short` zeigt mehrere geaenderte Dateien in `src/`, `tests/`, `templates/`, `static/` sowie diverse `__pycache__`-Artefakte. Das ist fuer die Statusaufnahme relevant, weil sich der aktuelle Stand nicht auf einen exakt sauberen Commit zurueckfuehren laesst.

## Agent-Dokumentation und Multi-Cam-Arbeitsmodell aktualisiert

Nach der technischen Bestandsaufnahme wurde die Repo-Dokumentation fuer Coding Agents neu strukturiert und an den aktuellen Projektzustand angepasst.

Wesentliche Punkte:

- `AGENTS.md` ist jetzt die kanonische Hauptanweisung fuer Codex und allgemeine Coding Agents.
- `CLAUDE.md` ist jetzt ein eigener Claude-Code-Einstieg statt nur ein Verweis.
- `agent_docs/` enthaelt jetzt getrennte Leitfaeden fuer Codex, Claude Code, Architektur, Hardwaregrenzen, Workflow und Prioritaeten.
- `MULTI_CAM_INSTRUCTIONS.md` und `MULTI_CAM_WORKFLOW.md` wurden von einem historischen Step-Plan auf ein aktuelles Hardening- und Work-Package-Modell umgestellt.

Bedeutung fuer die weitere Entwicklung:

- Der Multi-Cam-Bereich wird nicht mehr als Gruenfeld-Implementierung behandelt, sondern als vorhandener, aber sensibler Teil des Systems.
- Die Prioritaeten fuer weitere Agentenarbeit sind jetzt klar auf Lifecycle-Stabilitaet, Lastkontrolle, Testhaertung und reale Verifikation ausgerichtet.

## Aktuell implementierter Funktionsumfang

### 1. Anwendung und Betriebsmodell

Die Anwendung startet als FastAPI-App ueber `src/main.py`. Dort werden beim Lifespan-Start folgende Komponenten aufgebaut:

- `GameEngine`
- `EventManager`
- globaler `app_state`
- Hintergrundthread fuer Single-Camera oder Multi-Camera

Die App ist darauf ausgelegt, dauerhaft zu laufen und die CV-Pipeline parallel zur Webanwendung im Hintergrund zu betreiben.

### 2. Single-Camera CV-Pipeline

Der Single-Cam-Pfad ist derzeit das staerkste und am besten abgesicherte Kernstueck.

Implementierte Pipeline:

1. Kamera-Capture ueber `ThreadedCamera`
2. optionales Remapping / Homographie
3. ROI-Verarbeitung auf Zielgroesse `400x400`
4. Graustufe + CLAHE-Kontrastverbesserung
5. Motion Detection via MOG2
6. Dart-Erkennung per Kontur-/Formanalyse
7. Scoring ueber Board-Geometrie
8. Ausgabe als Hit-Kandidat statt sofortiger Verbuchung

Wichtige Merkmale:

- CPU-only Design, keine ML- oder GPU-Abhaengigkeit
- begrenzte Frame-Queue (`max_queue_size=5`)
- Frame-Dropping bei Rueckstau
- Overlay-Unterstuetzung fuer Marker und Motion
- Replay-Modus fuer Offline-Auswertung vorhanden

### 3. Spiel-Engine

Die Spiel-Engine in `src/game/engine.py` deckt aktuell ab:

- X01
- Cricket
- Free Play
- Undo-Stack
- Runden-/Spielerwechsel
- Sieglogik
- Bust-Logik bei X01

Die Engine ist vom CV-Teil getrennt, was fuer Testbarkeit und spaetere Erweiterungen sinnvoll ist.

### 4. Trefferfreigabe statt Blind-Automatismus

Ein wichtiger Reifeindikator ist der implementierte **Hit-Candidate-Review-Flow**:

- CV erzeugt Treffer-Kandidaten
- UI zeigt diese an
- Treffer koennen bestaetigt, verworfen oder korrigiert werden

Das reduziert Fehlbuchungen und ist gerade fuer ein CPU-basiertes Vision-System ohne Deep Learning ein sinnvoller Sicherheitsmechanismus.

### 5. Kalibrierung

Vorhanden sind aktuell:

- manuelle Board-Kalibrierung
- ArUco-basierte Board-Kalibrierung
- ChArUco-basierte Lens-Kalibrierung
- Ring-Verifikation
- manuelle und automatische Mittelpunktbestimmung

Der Kalibrierungsbereich ist funktional breit aufgestellt, aber im Test-Coverage-Bericht noch deutlich weniger abgesichert als Engine, Geometrie oder Events.

### 6. Multi-Camera

Multi-Camera ist bereits substantiell implementiert:

- mehrere `DartPipeline`-Instanzen parallel
- pro Kamera eigene Kalibrierungsdaten
- Fusion-Thread fuer Mehrkamera-Auswertung
- Stereo-Kalibrierung
- Board-Pose-Kalibrierung
- Triangulation mit Plausibilitaetspruefung
- Voting-Fallback bei fehlgeschlagener Triangulation
- UI fuer Start/Stop, Kamera-Konfiguration und Stereo-Setup

Der Funktionsumfang ist also **nicht nur geplant**, sondern bereits real im Code vorhanden. Der Bereich wirkt aber eher wie **fortgeschrittenes Entwicklungsstadium** als wie voll abgesicherter Produktionspfad.

### 7. Frontend und Bedienung

Die Weboberflaeche ist fuer den aktuellen Stand relativ weit:

- Live-Kameraansicht
- Scoreboard
- visuelles Dartboard
- Treffer-Kandidatenliste
- Kalibrierungs-Modal
- Multi-Cam-Modal
- WebSocket-Status
- responsive Layout-Anpassungen

Die Bedienung ist damit deutlich ueber reines Technik-Prototyping hinaus.

## Konfigurations- und Kalibrierungsstand

### `config/calibration_config.yaml`

Der aktuelle Stand zeigt fuer die Kamera `default` bereits eine **gueltige Einzelkamera-Kalibrierung**:

- `valid: true`
- `lens_valid: true`
- `method: aruco`
- `lens_method: charuco`
- `lens_image_size: [640, 480]`
- `lens_reprojection_error: 0.1466`
- `schema_version: 3`

Das ist ein gutes Zeichen: Der Single-Cam-Weg ist nicht nur implementiert, sondern offenbar bereits praktisch verwendet und mit echten Kalibrierdaten befuellt.

### `config/multi_cam.yaml`

Der aktuelle Stand fuer Multi-Camera ist deutlich frueher:

- `startup.mode: single`
- keine eingetragenen Stereo-Paare
- keine eingetragenen Board-Transforms
- keine vorkonfigurierten Startkameras

Das bedeutet:

- Multi-Camera ist im Code vorhanden
- Multi-Camera ist im Projekt aber **noch nicht betriebsfertig vorkonfiguriert**
- der Standardlauf ist klar auf **Single-Camera** ausgerichtet

## Verifizierter Ist-Zustand

### Teststand

Ausgefuehrt wurde:

```powershell
python -m pytest -q
```

Ergebnis:

- **209 Tests bestanden**
- Laufzeit: **12.84s**

Das ist ein starker Wert fuer den generellen Projektzustand.

### Coverage

Ausgefuehrt wurde:

```powershell
python -m pytest --cov=src --cov-report=term
```

Ergebnis:

- Gesamt-Coverage: **54%**

Auffaellig:

- stark: `game/engine.py` 92%, `geometry.py` 91%, `detector.py` 91%, `events.py` 93%
- mittel: `capture.py` 66%, `stereo_calibration.py` 61%
- schwach: `pipeline.py` 43%, `multi_camera.py` 49%, `main.py` 37%, `routes.py` 32%, `calibration.py` 30%

Interpretation:

- die Kernlogik fuer Regeln, Geometrie und einfache CV-Bausteine ist solide abgesichert
- die betriebsnahen Schichten (Routen, Lifecycles, Kalibrierungsflows, Multi-Cam-Steuerung) sind deutlich weniger abgesichert

### Synthetische Performance-Benchmarks

Ausgefuehrt wurde:

```powershell
python -m tests.benchmark_pipeline --duration 5 --cameras 1
python -m tests.benchmark_pipeline --duration 5 --cameras 2
python -m tests.benchmark_pipeline --duration 5 --cameras 3
```

Ergebnisse:

| Szenario | Median FPS | P95 FPS | Median-Latenz | P95-Latenz | Bewertung |
|---|---:|---:|---:|---:|---|
| 1 Kamera | 94.94 | 52.95 | 10.53 ms | 18.88 ms | sehr gut |
| 2 Kameras | min. 74.29 pro Kamera | min. 34.48 pro Kamera | max. 13.46 ms | max. 29.00 ms | sehr gut |
| 3 Kameras | min. 50.56 pro Kamera | min. 36.09 pro Kamera | max. 19.78 ms | max. 27.70 ms | gut |

Wichtige Einordnung:

- Diese Benchmarks sind **synthetisch** und arbeiten mit Mock-/Replay-artigen Frames.
- Sie beweisen **nicht** die gleiche Performance unter realem USB-Kamera-I/O.
- Sie zeigen aber deutlich, dass die reine Verarbeitungslogik fuer die Zielhardwareklasse nicht zu schwer ist.

## Hardware-Abgleich mit `hardware_constraints.md`

### CPU

### Vorgabe

- 4 Cores / 8 Threads
- empfohlen: 4-6 Worker, 2 Threads fuer OS/UI frei lassen
- Mobile-U-CPU, daher thermisch begrenzt

### Projekt-Fit

**Positiv**

- keine GPU- oder Deep-Learning-Abhaengigkeit
- klassische CV mit OpenCV und NumPy
- pro Pipeline feste Ziel-FPS von 30
- Frame-Dropping bei Rueckstau
- begrenzte Queue-Laenge

**Abgeleitete Einschaetzung**

- **Single-Cam:** sehr gut passend
- **2 Kameras:** gut passend
- **3 Kameras:** technisch wahrscheinlich moeglich, aber nur mit sauberer Kameraauflosung und thermischer Reserve empfehlenswert
- **4+ Kameras:** fuer den i5-1035G1 im Dauerbetrieb nicht sinnvoll

### CPU-Fazit

Die Architektur passt grundsaetzlich gut zur CPU-Vorgabe. Das Projekt ist klar fuer CPU-only gedacht. Kritisch ist nicht die mathematische Kernlogik, sondern eher der reale Dauerbetrieb mit Kamera-I/O, thermischer Last und Thread-Lifecycle.

### RAM

### Vorgabe

- konservative Zielgrenze: <= 4 GB Prozessspeicher bei angenommener 8-GB-Ausstattung

### Projekt-Fit

**Belegt**

- `ThreadedCamera` arbeitet mit `max_queue_size=5`
- ROI ist auf `400x400` begrenzt
- keine grossen In-Memory-Datensaetze
- keine ML-Modelle
- YAML-Konfiguration klein

**Abgeleitete Einschaetzung**

Selbst bei mehreren Kameras ist der Speicherbedarf der Pipeline nach heutigem Design voraussichtlich deutlich unter der 4-GB-Zielgrenze. Kritisch waere eher eine unkontrolliert hohe Kamera-Standardauflosung, weil im Code derzeit keine feste Capture-Aufloesung erzwungen wird.

### RAM-Fazit

Die Architektur ist fuer die vorgegebenen RAM-Grenzen **sehr gut geeignet**.

### Storage

### Vorgabe

- 116 GB frei
- keine unkontrollierten Tempfiles
- Rotation ab groesseren Logmengen sinnvoll

### Projekt-Fit

**Belegt**

- Konfiguration wird atomar per Tempfile + `os.replace` geschrieben
- keine grossen Cache- oder Modell-Downloads
- Logs gehen standardmaessig nach stdout

**Risiko**

- keine Log-Rotation, falls spaeter dateibasierte Logs dazukommen
- keine expliziten Cleanup- oder Guardrails fuer kuenftige Replay-/Video-Artefakte

### Storage-Fazit

Der aktuelle Stand ist fuer die vorhandene SSD-Kapazitaet unkritisch. Der Bereich ist momentan **kein Lauffaehigkeitsblocker**.

### GPU

### Vorgabe

- keine CUDA/ROCm
- Intel iGPU nur eingeschraenkt fuer Compute geeignet

### Projekt-Fit

Voll passend. Das Projekt benoetigt aktuell keine dedizierte GPU. Die Abhaengigkeiten und die Codebasis sind konsequent CPU-orientiert.

### GPU-Fazit

**Kein Problem.**

### Netzwerk

### Vorgabe

- WLAN-only, variable Latenz

### Projekt-Fit

Der Kernbetrieb ist lokal und benoetigt fuer die Grundfunktion keine externe Netzwerkinfrastruktur. Die Anwendung nutzt intern HTTP/WebSocket zwischen Browser und lokalem FastAPI-Server.

### Netzwerk-Fazit

Fuer den Hauptanwendungsfall **unkritisch**.

## Gesamtbewertung der Lauffaehigkeit

### Single-Camera

**Bewertung: lauffaehig und fuer die Zielhardware plausibel gut geeignet**

Begruendung:

- CPU-only Design passt
- begrenzte Puffer und kleine ROI
- bestehende Kalibrierdaten vorhanden
- Tests sehr stark
- synthetische Performance deutlich ueber den Zielwerten

### Multi-Camera mit 2 Kameras

**Bewertung: wahrscheinlich lauffaehig, aber noch nicht voll betriebsstabil abgesichert**

Begruendung:

- Architektur und Benchmarks sprechen dafuer
- Multi-Cam ist funktional weit entwickelt
- Konfigurationsstand ist noch leer
- Lifecycle-Steuerung ist noch riskant

### Multi-Camera mit 3 Kameras

**Bewertung: technisch moeglich, aber fuer den i5-1035G1 nur mit Disziplin sinnvoll**

Empfehlungen dafuer:

- Kameraauflosung begrenzen
- thermische Last beobachten
- nur nach echter Hardwaremessung freigeben

## Reifegrad nach Bereichen

| Bereich | Reifegrad | Kommentar |
|---|---|---|
| Spiel-Engine | hoch | gut testbar, gute Coverage |
| Geometrie / Scoring | hoch | zentrale Logik solide abgesichert |
| Single-Cam Pipeline | mittel bis hoch | architektonisch passend, praktisch nutzbar |
| Kalibrierung | mittel | breit implementiert, aber noch geringe Coverage |
| Web/API | mittel | funktional breit, aber Coverage in Randfaellen schwach |
| Multi-Camera | mittel | technisch weit, aber noch nicht stabil genug fuer "einfach einschalten und laufen lassen" |
| UX/Bedienung | mittel | bereits ordentlich, aber noch ausbaufahig |

## Wesentliche Risiken im aktuellen Stand

### 1. Pipeline-Lifecycle beim Umschalten Single <-> Multi

**Abgeleitet aus dem Code.**

`src/main.py` betreibt `_run_pipeline()` und `_run_multi_pipeline()` jeweils in eigenen Hintergrundthreads, deren Schleifen an `shutdown_event` gebunden sind. In `src/web/routes.py` werden beim Start/Stop von Multi-Cam zwar `pipeline.stop()` bzw. `multi.stop()` aufgerufen, aber der uebergeordnete Hintergrundthread wird dabei nicht ueber ein separates Lifecycle-Signal beendet.

Praktische Folge:

- moegliche Thread-Leaks
- potenziell mehrere aktive oder halbaktive Pipeline-Controller ueber die Laufzeit
- Risiko fuer schwer reproduzierbare Zustandsfehler nach wiederholtem Start/Stop

Das ist der wichtigste aktuelle Stabilitaetspunkt.

### 2. Keine explizite Begrenzung der Kamera-Capture-Aufloesung

`ThreadedCamera` setzt nur `CAP_PROP_BUFFERSIZE`, aber keine Zielwerte fuer Aufloesung oder Kamera-FPS. Dadurch haengt die reale Last stark vom Kamera-Default ab.

Praktische Folge:

- auf dem i5-1035G1 kann eine Kamera mit hoher Default-Aufloesung den CPU-Bedarf unnoetig anheben
- Multi-Cam-Betrieb wird dadurch deutlich unvorhersagbarer

### 3. Geringe Coverage in betriebsnahen Schichten

Mit nur 32-49% Coverage in `routes.py`, `main.py`, `pipeline.py` und `multi_camera.py` sind gerade die Pfade mit Threads, HTTP, Lifecycles und Kalibrierungsintegration die am wenigsten abgesicherten.

## Priorisierte Liste mit Verbesserungspotentialen

Die Reihenfolge geht von **kritisch fuer stabile Lauffaehigkeit** bis zu **leichterer Bedienbarkeit**.

1. **Pipeline-Lifecycle sauber trennen und beendbar machen.**  
   Single- und Multi-Cam brauchen eigene Start/Stop-Signale und referenzierte Thread-Handles, damit beim Umschalten keine ueberlebenden Steuerthreads im Hintergrund bleiben.

2. **Kameraauflosung und Eingangs-FPS explizit konfigurierbar erzwingen.**  
   Fuer die Zielhardware sollte standardmaessig ein konservatives Profil wie 640x480 oder 720p hinterlegt werden, statt die Last dem Webcam-Default zu ueberlassen.

3. **Hardware- und Runtime-Selbsttest beim Start einbauen.**  
   Vor dem Betriebsstart sollten Kamera-Verfuegbarkeit, OpenCV-ArUco-Support, freie Disk, Python-Version und relevante Kalibrierungsdaten geprueft werden.

4. **Betriebsnahe Testabdeckung fuer `main`, `routes`, `pipeline`, `multi_camera` deutlich erhoehen.**  
   Besonders wichtig sind Start/Stop-Sequenzen, Fehlerpfade, Kamera-Ausfaelle, Umschalten Single/Multi und Reconnect-Szenarien.

5. **Replay-basierte End-to-End-Validierung mit echten Referenzclips aufbauen.**  
   Die synthetischen Benchmarks sind gut, aber fuer echte Freigabe braucht es Accuracy- und Stabilitaetsmessung mit realen Dart-Sequenzen.

6. **Live-Telemetrie fuer CPU, RAM, Dropped Frames, Reconnects und Queue-Druck nachruesten.**  
   Damit laesst sich auf der Zielhardware sichtbar machen, wann der i5-1035G1 an seine Grenzen kommt.

7. **Multi-Camera-Konfiguration und Kalibrierungszustand persistenter und gefuehrter machen.**  
   Aktuell ist der Code da, aber `multi_cam.yaml` ist noch praktisch leer. Ein gefuehrter kompletter Multi-Cam-Setup-Flow wuerde den Nutzwert deutlich erhoehen.

8. **Logging betriebstauglicher machen.**  
   `setup_logging()` sollte idempotent sein, optional Dateiausgabe mit Rotation unterstuetzen und Sessions sauber korrelierbar machen.

9. **Windows-Setup vereinfachen.**  
   Fuer das Zielgeraet waeren Startskripte, Installationschecks und ein klarer "erste Inbetriebnahme"-Pfad sinnvoll, damit die App auf dem Laptop reproduzierbar aufgesetzt werden kann.

10. **Bedienbarkeit und Fehlerrueckmeldungen im UI verfeinern.**  
   Dazu gehoeren klarere Kalibrierungshinweise, bessere Fehlertexte, gefuehrte Multi-Cam-Schritte und insgesamt weniger implizites Expertenwissen in der Oberflaeche.

## Abschliessende Bewertung

Der Projektstand ist fuer ein CPU-only-System wie den beschriebenen i5-1035G1 **substanziell weiter als ein Prototyp**. Besonders positiv sind:

- klare CPU-taugliche Architektur
- guter Testumfang
- bereits vorhandene reale Kalibrierdaten fuer Single-Cam
- brauchbare Weboberflaeche
- viel funktionaler Vorlauf fuer Multi-Cam

Der wichtigste Punkt fuer den naechsten Reifegrad ist **nicht** die rohe Rechenleistung, sondern die **Betriebsrobustheit**:

- Lifecycle sauber machen
- Last konservativ begrenzen
- echte Hardwaremessungen und Replay-Validierung nachziehen

Wenn diese Punkte sauber angegangen werden, ist die Zielhardware fuer den geplanten Einsatzzweck realistisch ausreichend.

## Anhang: verwendete Verifikation

Ausgefuehrte Kommandos:

```powershell
python --version
python -m pytest -q
python -m pytest --cov=src --cov-report=term
python -m tests.benchmark_pipeline --duration 5 --cameras 1
python -m tests.benchmark_pipeline --duration 5 --cameras 2
python -m tests.benchmark_pipeline --duration 5 --cameras 3
git status --short
```

Wichtige Messwerte:

- Python: `3.14.3`
- Tests: `209 passed`
- Coverage: `54%`
- Benchmark: Single-Cam sehr gut, 2-3 Kameras synthetisch ebenfalls innerhalb der gesetzten KPI-Grenzen
