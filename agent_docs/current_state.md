# Current State

Stand dieser Zusammenfassung: 2026-03-17 (P7, P13-P17 erledigt; P19-P23 neu priorisiert)

## Technischer Kern

Das Projekt ist ein lokales Dart-Scoring-System mit:

- FastAPI als Server
- OpenCV + NumPy fuer Bildverarbeitung
- einer CV-Pipeline fuer Treffererkennung
- Spiel-Engine fuer X01, Cricket und Free Play
- einer Weboberflaeche mit Live-Bild, Scoreboard und Kalibrierungsdialogen

## Was heute als stabil gilt

- Single-Camera als Standard-Startpfad
- grundlegende Spiel-Engine
- Board-Geometrie und Scoring
- WebSocket-Eventfluss
- Hit-Candidate-Review statt sofortiger Auto-Buchung
- Pipeline-Lifecycle (Start/Stop/Umschalten) mit Stop-Events und Thread-Handles
- Kamera-Reconnect mit exponentiellem Backoff (1-30s), State-Tracking (connected/reconnecting/disconnected)
- Kamera-Health-API (`/api/camera/health`) und WebSocket-Event (`camera_state`)
- Frontend-Warnbanner bei Kamera-Ausfall (Echtzeit via WebSocket + Polling-Fallback)
- Kamera-Input konfigurierbar (Aufloesung, FPS)
- 4-stufige ArUco-Erkennung (robust gegen Beleuchtungsschwankungen)
- Kalibrier-Qualitaetsmetrik (quality 0-100, Ringradien-Abweichung in mm)
- Optische-Mittelpunkt-Erkennung mit Intensity-Fallback
- Kalibrierungs-UX mit Statusanzeige und gefuehrten Schritten
- Telemetrie im Header (FPS, Dropped Frames, Queue-Druck, RAM)
- Idempotentes Logging mit Session-ID, optionalem File-Rotation-Log (`DARTVISION_LOG_FILE`)
- Windows-Startskript (`start.bat`) mit venv, Dependency-Check, Diagnose
- Diagnose-CLI (`python -m src.diagnose`): Python, Deps, Kameras, Config, Kalibrierung
- Deutsche Fehlermeldungen in allen Kalibrierungs-Endpunkten
- Input-Validierung in Web-Routes (score, sector, multiplier, ring, game params)
- Game-Engine: Schutz gegen fehlende Keys, >3 Darts, ungueltige starting_score
- CV-Pipeline: Parameter-Validierung (area bounds, thresholds), inclusive Boundary-Check, Kandidaten-Limit
- Frontend: response.ok-Checks auf allen fetch-Aufrufen, Error-Toast bei HTTP-Fehlern
- Config-Schema-Validierung beim Laden (Warn-Logging) und Speichern (ValueError)
- Hit-Candidate Auto-Timeout (30s) mit Countdown-Anzeige
- Audio-Feedback bei bestaetigtem Treffer (Web Audio API)
- Wurf-Badges im Scoreboard statt Klartext
- Pulsierender Glow-Effekt fuer aktiven Spieler
- X01-Checkout-Vorschlaege (Scores 2-170) mit Backend-Lookup

## Was heute als fortgeschritten, aber noch sensibel gilt

- Multi-Camera-Pipeline (gehaertet: Readiness-Diagnose, Config-Persistenz, Setup-Wizard)
- Stereo-Kalibrierung (Triangulations-Genauigkeit validiert: <5mm auf 8 Board-Positionen)
- Board-Pose-Kalibrierung
- Triangulation und Voting-Fallback
- Umschalten zwischen Single- und Multi-Cam (Fix: Kamera-Release-Timing)

## Verifizierte Kennzahlen

- `494` Tests bestanden (Stand 2026-03-17)
- Gesamt-Coverage 76%
- Wichtige Module: main.py 78%, routes.py 66%, pipeline.py 75%, multi_camera.py 61%, capture.py 95%
- synthetische Pipeline-Benchmarks fuer `1`, `2` und `3` Kameras innerhalb der definierten KPI-Grenzen
- E2E-Replay-Tests: 90% Hit Rate, 100% Score Accuracy auf synthetischen Clips (6 Tests)

## Analysebefunde 2026-03-17 (fuer neue Prioritaeten)

- `src/web/routes.py` ist mit 1453 Zeilen weiterhin das groesste Modul und kombiniert API, Lifecycle-Waits und Stream-Logik.
- Es gibt weiterhin blockierende `_time.sleep(...)`-Wartepfade in asynchronen Route-Handlern.
- `src/cv/calibration.py` bleibt mit 53% Coverage der schwaechste betriebsrelevante Kernbereich.
- `src/cv/multi_camera.py` hat 61% Coverage; Burst-/Timing-Faelle in der Fusion bleiben ein Hardening-Thema.
- Der `pending_hits`-Lifecycle ist funktional, aber Timeout-Verhalten ist aktuell stark frontend-getrieben.

## Wichtige Projektfakten

- `config/calibration_config.yaml` enthaelt eine gueltige Kalibrierung fuer `default`
- `config/multi_cam.yaml` speichert jetzt auch `last_cameras` fuer schnellen Multi-Cam-Neustart
- Telemetrie-Endpunkt `/api/stats` liefert FPS, Dropped Frames, Queue-Druck, RAM
- `/api/multi/readiness` liefert pro-Kamera-Diagnose fuer Multi-Cam-Setup
- Alle API-Fehlermeldungen sind deutsch und handlungsorientiert

## Arbeitsannahmen fuer Agents

1. Single-Cam ist der reale Hauptpfad.
2. Multi-Cam ist gehaertet, aber braucht weiterhin defensive Aenderungen.
3. Hardware ist begrenzt. Performance und Stabilitaet gehen vor Feature-Breite.
4. Kalibrierung ist kein Nebenthema, sondern Kernfunktion.
5. Windows ist die Zielplattform — Kamera-Release-Timing beachten.

## Was Agents nicht annehmen sollten

- dass Multi-Cam bereits produktionsreif ist
- dass hohe Kameraauflosungen automatisch vertretbar sind
- dass synthetische Benchmarks reale USB-Last komplett abbilden
- dass ungetestete Lifecycle-Aenderungen harmlos sind

## Referenzdokumente

- `SESSION_2026-03-17.md` — ausfuehrliche Session-Doku aller Aenderungen
- `PROJEKTSTAND_2026-03-16.md` — vorige technische Einordnung
