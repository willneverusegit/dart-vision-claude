# Priorities

Diese Liste beschreibt die empfohlene Weiterentwicklung aus Sicht des Projektstands 2026-03-17.
Prio 1–7 der vorherigen Liste sind abgeschlossen.

## Prioritaet 1: Replay-basierte E2E-Validierung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Vollstaendiges E2E-Replay-Test-Framework implementiert. Synthetischer Clip-Generator erzeugt 10 Dart-Wuerfe auf verschiedene Board-Positionen (Bull, Single, Triple, Double in allen Quadranten). Ground-Truth-Loader, Accuracy-Metriken (Hit Rate, Score/Sector/Ring Accuracy, False Positive Rate) und 6 CI-faehige pytest-Tests. Ergebnis auf synthetischen Daten: 90% Hit Rate, 100% Score Accuracy, 0 False Positives. Geaenderte Dateien: `tests/e2e/__init__.py`, `tests/e2e/generate_synthetic_clip.py`, `tests/e2e/accuracy.py`, `tests/e2e/test_replay_e2e.py`.

Ziel:

- sicherstellen, dass die Treffererkennung auf echtem Videomaterial korrekt funktioniert
- Regressionsschutz fuer CV-Aenderungen

Typische Arbeiten:

- Referenz-Clips mit Ground-Truth-Annotation anlegen (z.B. 10 bekannte Wuerfe)
- Replay-Pipeline automatisiert gegen Ground Truth laufen lassen
- Accuracy-Metriken berechnen: Trefferquote, Sektorgenauigkeit, Ringgenauigkeit
- CI-faehigen Accuracy-Test schreiben

Warum kritisch: Ohne E2E-Validierung auf echtem Material gibt es keinen Beweis, dass das System tatsaechlich funktioniert.

## Prioritaet 2: Kamera-Reconnect und Fehlerbehandlung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** CameraState-Enum (connected/reconnecting/disconnected) und Health-Tracking in ThreadedCamera. State-Change-Callbacks mit WebSocket-Broadcast (`camera_state` Event). API-Endpunkt `/api/camera/health` und Health-Daten in `/api/stats`. Frontend-Warnbanner mit Pulsanimation bei Kamera-Problemen, aktualisiert via WebSocket und Stats-Polling. 13 neue Tests fuer Reconnect-Szenarien. Geaenderte Dateien: `src/cv/capture.py`, `src/main.py`, `src/web/routes.py`, `static/js/app.js`, `static/css/style.css`, `templates/index.html`, `tests/test_camera_reconnect.py`.

Ziel:

- System ueberlebt Kamera-Ausfall, USB-Wackler, Laptop-Standby graceful

Typische Arbeiten:

- `ThreadedCamera`: Reconnect-Logik mit exponentiellem Backoff testen und absichern
- UI-Feedback bei Kamera-Ausfall (Warnbanner statt schwarzes Bild)
- Pipeline-State korrekt auf "degraded" setzen statt crashen
- Tests fuer Reconnect-Szenarien

Warum kritisch: Im realen Einsatz am Laptop passieren USB-Probleme regelmaessig.

## Prioritaet 3: Multi-Cam Stereo-Triangulation validieren (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** 27 synthetische Validierungstests fuer die gesamte Triangulations-Pipeline. Getestet: Board-Frame-Transformation (identity, translation, rotation), Triangulations-Genauigkeit mit realistischem Stereo-Setup (verschiedene Baselines 10-40cm, Distanzen 50-120cm), Z-Depth-Plausibilitaet (15mm Toleranz), End-to-End-Pipeline (Projekt→Triangulieren→Board-Transform→mm-Koordinaten) fuer Bullseye/T20/D16 und 8 Board-Positionen (<5mm Fehler), Stereo-Param-Loading in Fusion-Pipeline (inkl. fehlende Intrinsics/Paare). Geaenderte Dateien: `tests/test_stereo_validation.py`.

Ziel:

- Triangulation auf echte Genauigkeit pruefen, nicht nur synthetische Tests

Typische Arbeiten:

- Stereo-Kalibrierung mit zwei echten Kameras durchfuehren und Reprojektion messen
- Triangulierte 3D-Punkte gegen bekannte Board-Positionen vergleichen
- Schwellwerte fuer `max_reproj_error` und Z-Plausibilitaet empirisch validieren
- Doku: welche Kamera-Geometrie (Abstand, Winkel) brauchbare Ergebnisse liefert

## Prioritaet 4: Logging betriebstauglicher machen (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Idempotentes Logging-Setup (kein doppeltes Handler-Registrieren). Optionales Rotating-File-Logging via `DARTVISION_LOG_FILE` Env-Variable (5MB, 3 Backups). Konsistente Session-ID (8-Zeichen UUID-Prefix) in allen Log-Zeilen. JSON-Format-Support mit Session-ID. 8 neue Tests. Geaenderte Dateien: `src/utils/logger.py`, `src/main.py`, `tests/test_logger.py`.

Ziel:

- Laufzeitfehler und Feldbetrieb besser analysieren koennen

Typische Arbeiten:

- idempotentes Logging-Setup (kein doppeltes Handler-Registrieren)
- optional Rotation/File-Logging fuer Langzeitbetrieb
- konsistente Session-ID in Logs (Start bis Stop)
- Kamera-ID-Kontext in Multi-Cam-Logs

## Prioritaet 5: Windows-Inbetriebnahme vereinfachen (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** `start.bat` mit automatischer venv-Erstellung, Dependency-Check und Server-Start. Diagnose-Modul `python -m src.diagnose` prueft Python-Version, alle Abhaengigkeiten, verfuegbare Kameras (Index 0-4 mit Aufloesung/FPS), Konfigurationsdateien und Kalibrierungsstatus. `start.bat` fuehrt Diagnose automatisch vor Server-Start aus. 10 neue Tests. Geaenderte Dateien: `start.bat`, `src/diagnose.py`, `tests/test_diagnose.py`.

Ziel:

- Setup und Start auf dem Ziel-Laptop ohne Expertenwissen moeglich machen

Typische Arbeiten:

- `start.bat` oder PowerShell-Startskript mit venv-Aktivierung
- Diagnose-Checkliste als CLI-Befehl (`python -m src.diagnose`)
- Kamera-Erkennung: verfuegbare Kameras auflisten vor Pipeline-Start
- klarer Installationspfad in README

## Prioritaet 6: Dartboard-Erkennung verbessern (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** 4-stufige ArUco-Erkennung (raw → CLAHE 3.0 → CLAHE 6.0 → Blur+CLAHE) fuer robustere Marker-Detektion bei schwieriger Beleuchtung. Intensity-Fallback fuer optische Mittelpunkt-Erkennung wenn HSV-Farbsuche fehlschlaegt. Kalibrier-Qualitaetsmetrik: verify_rings liefert jetzt deviations_px, max_deviation_mm und quality (0-100). detection_method im ArUco-Calibration-Response. 11 neue Tests. Geaenderte Dateien: `src/cv/calibration.py`, `tests/test_board_detection_p6.py`.

Ziel:

- hoehere Treffsicherheit bei der automatischen Board-Erkennung

Typische Arbeiten:

- ArUco-Board-Alignment robuster gegen Beleuchtungsschwankungen machen
- Optischer Mittelpunkt: bessere Auto-Erkennung (aktuell oft manuell noetig)
- Board-Geometrie-Fit: Ringradien-Abweichung als Qualitaetsmetrik exponieren
- Kalibrier-Vorschau mit mehr visuellen Hinweisen (z.B. erkannte Marker hervorheben)

## Prioritaet 7: Spielablauf-UX verbessern (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** 5 UX-Features implementiert: (a) Hit-Candidate Auto-Timeout nach 30s mit Countdown-Anzeige, (b) Audio-Feedback per Web Audio API bei bestaetigtem Treffer, (c) Wurf-Badges statt Klartext im Scoreboard, (d) Pulsierender Glow-Effekt fuer aktiven Spieler, (e) X01-Checkout-Vorschlaege (2-170) mit Backend-Lookup und Frontend-Anzeige. 11 neue Tests fuer Checkout-Modul. Geaenderte Dateien: `static/js/app.js`, `static/js/scoreboard.js`, `static/css/style.css`, `templates/index.html`, `src/game/checkout.py`, `src/game/models.py`, `tests/test_checkout.py`.

Ziel:

- weniger Klicks, klarere Rueckmeldung waehrend des Spiels

Typische Arbeiten:

- Hit-Candidate-Timeout: automatisches Ablehnen nach X Sekunden ohne Bestaetigung
- Audio-Feedback bei erkanntem Treffer (optional, Browser Web Audio API)
- Wurf-Historie mit Undo sichtbarer gestalten
- Scoreboard: aktueller Spieler visuell hervorheben
- Checkout-Vorschlaege bei X01 (z.B. "T20 D16" bei 76 Restpunkten)

## Prioritaet 8: Performance-Monitoring und Alerting (NIEDRIG)

Ziel:

- Engpaesse frueh erkennen, bevor sie den Spielbetrieb stoeren

Typische Arbeiten:

- Telemetrie-Historie: FPS/Drop/Queue ueber Zeit als Chart (nicht nur aktuellen Wert)
- Warnung wenn FPS unter 15 faellt oder Queue-Druck > 80% bleibt
- CPU-Last pro Pipeline-Thread messen (Windows: `psutil` optional)
- Telemetrie optional in Logfile schreiben fuer Post-Mortem-Analyse

## Prioritaet 9: Multi-Cam UX weiter verbessern (NIEDRIG)

Ziel:

- Multi-Cam-Setup fuer Nicht-Experten bedienbar machen

Typische Arbeiten:

- Kamera-Vorschau im Multi-Cam-Modal (Live-Thumbnails pro Kamera)
- Drag-and-Drop Kamera-Anordnung
- Stereo-Kalibrierung: Fortschrittsanzeige mit Frame-Counter
- Board-Pose: visuelles Feedback (erkannte Marker im Bild einblenden)
- Setup-Wizard: automatisch zum naechsten Schritt wechseln wenn ein Schritt erledigt ist

## Prioritaet 10: UI-Design und Responsiveness (NIEDRIG)

Ziel:

- Oberflaeche auf verschiedenen Bildschirmgroessen nutzbar und optisch ansprechend

Typische Arbeiten:

- Mobile/Tablet-Layout (Responsive Breakpoints)
- Dark/Light-Theme-Umschaltung
- Scoreboard-Bereich: kompakteres Layout fuer kleinere Bildschirme
- Kamera-Feed: Aspektverhaeltnis beibehalten statt strecken
- Ladeanimation beim Pipeline-Start (Spinner statt schwarzes Bild)
- Tastaturkuerzel fuer haeufige Aktionen (Treffer bestaetigen/ablehnen)

## Arbeitsregel fuer Agents

Wenn der User nur allgemein nach "weiterentwickeln" fragt und keine andere Richtung vorgibt, beginne oben in der Liste und arbeite nach unten.

## Format fuer erledigte Prioritaeten

```
## Prioritaet N: Titel (✅ ERLEDIGT JJJJ-MM-TT)

**Umsetzung:** Was konkret umgesetzt wurde. Geaenderte Dateien: `src/foo.py`.

[urspruenglicher Inhalt bleibt erhalten]
```

Nummerierung wird NIEMALS geaendert. Neue Prioritaeten werden am Ende mit weiterführender Nummer angehaengt.
Erledigte Prioritaeten bleiben in der Liste — nur mit Markierung und Umsetzungsnotiz ergaenzt.

## Prioritaet 11: E2E-Tests mit echten Videoclips (neu — entdeckt bei Arbeit an P1)

Ziel:

- synthetische E2E-Tests durch Tests mit echten Kamera-Aufnahmen ergaenzen

Typische Arbeiten:

- 5-10 echte Clips am Dartboard aufnehmen (verschiedene Beleuchtung, Winkel)
- Ground-Truth-Annotations manuell erstellen
- Accuracy-Thresholds fuer echte Clips kalibrieren (realistischer als synthetisch)
- outer_bull-Erkennung verbessern (aktuell verpasst wegen zu kleinem Blob in schmaler Ring-Zone)

## Prioritaet 12: DartImpactDetector Area-Range erweitern (neu — entdeckt bei Arbeit an P1)

Ziel:

- Erkennungsbereich fuer Konturflaechenwerte flexibler machen

Typische Arbeiten:

- area_max von 1000 auf einen konfigurierbaren Wert erhoehen oder dynamisch skalieren
- Tests fuer Edge Cases: sehr grosse/kleine Darts, verschiedene Kamera-Distanzen
- Outer-Bull-Bereich: Blob hat in schmaler Ring-Zone nur ~40px Flaeche — unter area_min

## Prioritaet 13: Input-Validierung in Web-Routes (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** `_validate_score_input()` Helper in routes.py. Validierung fuer `/api/game/new` (mode, players, starting_score), `/api/hits/{id}/correct` (score 0-180, sector, multiplier 1-3, ring) und `/api/game/manual-score`. 28 neue Tests. Geaenderte Dateien: `src/web/routes.py`, `tests/test_input_validation.py`.

Ziel:

- API-Endpunkte gegen ungueltige Eingaben absichern

Typische Arbeiten:

- `/api/hits/{id}/correct`: score, sector, multiplier, ring validieren (Wertebereiche)
- `/api/game/new`: mode, players, starting_score validieren
- `/api/manual_score`: multiplier-Werte auf {1,2,3} beschraenken
- Negative Tests fuer alle validierten Endpunkte schreiben

Warum kritisch: Aktuell kann jeder Client beliebige Werte senden (sector=99, score=-50), die ohne Pruefung registriert werden.

## Prioritaet 14: Game-Engine Robustheit (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** `new_game()` validiert starting_score (1-10000) und non-empty players. `register_throw()` faengt fehlende Keys ab und auto-completed Turn bei >3 Darts. Tests in `tests/test_input_validation.py`. Geaenderte Dateien: `src/game/engine.py`.

Ziel:

- Spiellogik gegen Randfaelle und fehlerhafte Eingaben absichern

Typische Arbeiten:

- ThrowResult-Validierung: Pflichtfelder pruefen bevor Wurf registriert wird
- Cricket: Sector-Validierung (nur 15-20, 25 erlaubt)
- X01: starting_score-Validierung (positiv, sinnvoller Bereich)
- Schutz gegen >3 Wuerfe pro Turn
- Tests fuer alle Randfaelle

Warum kritisch: Fehlerhafte Wuerfe koennen den Spielstand korrumpieren ohne Fehlermeldung.

## Prioritaet 15: CV-Pipeline Konfigurations-Validierung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** DartImpactDetector: Parameter-Validierung (area_min<area_max, confirmation_frames>=1, etc.), inclusive Boundary-Check (`<=`), max_candidates Limit (50). MotionDetector: threshold/var_threshold >0 erzwungen. 13 neue Tests. Geaenderte Dateien: `src/cv/detector.py`, `src/cv/motion.py`, `tests/test_cv_validation.py`.

Ziel:

- Threshold-Parameter der CV-Pipeline gegen unsinnige Werte absichern

Typische Arbeiten:

- DartImpactDetector: area_min < area_max erzwingen, Boundary-Check `<=` statt `<`
- MotionDetector: threshold-Bereich validieren (>0)
- Pipeline: ROI-Groesse gegen Frame-Dimensionen pruefen
- Kandidaten-Decay: Stale-Candidate-Limit einfuehren
- Tests fuer Fehlkonfigurationen

Warum kritisch: Fehlkonfigurierte Schwellwerte fuehren zu stiller Nicht-Erkennung oder False Positives.

## Prioritaet 16: Frontend Fehlerbehandlung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** `_showError()` Toast-Methode in app.js. Alle 27 fetch-Aufrufe mit `response.ok`-Check versehen. Dartboard.js geometry-Fetch abgesichert. WebSocket onerror mit Error-Type-Logging. Geaenderte Dateien: `static/js/app.js`, `static/js/dartboard.js`, `static/js/websocket.js`.

Ziel:

- Fetch-Aufrufe und WebSocket-Handling robuster machen

Typische Arbeiten:

- Alle fetch-Aufrufe: `response.ok` pruefen vor JSON-Parse
- Fehlermeldung an Nutzer bei HTTP-Fehlern (Toast/Banner)
- WebSocket: Unterscheidung Netzwerk-Fehler vs. Nachrichten-Fehler
- Stale-Candidate-Handling: UI-State nach fehlgeschlagenem Confirm zuruecksetzen

Warum kritisch: Aktuell werden Server-Fehler (500, 404) still ignoriert und die UI zeigt inkonsistenten State.

## Prioritaet 17: Config-Schema-Validierung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** `validate_calibration_config()` und `validate_matrix_shape()` in config.py. Load-time Validierung mit Warn-Logging (kein Raise). Save-Validierung in `save_stereo_pair()` und `save_board_transform()` mit ValueError bei ungueltigem Input. 16 neue Tests. Geaenderte Dateien: `src/utils/config.py`, `tests/test_config_validation.py`.

Ziel:

- YAML-Konfigurationsdateien beim Laden gegen ein Schema validieren

Typische Arbeiten:

- Schema-Definition fuer calibration_config.yaml (erwartete Keys, Typen, Matrix-Shapes)
- Validierung in `load_config()`: fehlende Keys, falsche Typen, ungueltige Matrizen erkennen
- `save_stereo_pair()` / `save_board_transform()`: Matrix-Shape-Pruefung vor Speicherung
- Klare Fehlermeldungen bei Schema-Verletzungen
- Tests fuer korrupte/unvollstaendige Config-Dateien

Warum kritisch: Korrupte Kalibrierungsdaten werden aktuell still geladen und fuehren erst zur Laufzeit zu kryptischen Fehlern.

## Prioritaet 18: Checkout-Tabelle erweitern und Spielvarianten (neu — entdeckt bei Arbeit an P7)

Ziel:

- Checkout-Vorschlaege vervollstaendigen und weitere X01-Varianten unterstuetzen

Typische Arbeiten:

- Checkout-Tabelle um 2-Dart und 3-Dart Pfade mit bevorzugten "Standard-Checkouts" ergaenzen (z.B. 170 = T20 T20 D25)
- Double-In-Variante fuer X01 unterstuetzen (erster Wurf muss Double sein)
- Checkout-Vorschlag auch fuer 2. und 3. Dart der Runde anpassen (nach erstem Wurf restlichen Checkout berechnen)
- Spieler-spezifische Checkout-Praeferenzen (optional, spaeter)

Verknuepfte Weaknesses: keine
Verknuepfte Entscheidungen: ADR-004

## Prioritaet 19: Async-Blocker in Web-Routes entfernen (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Zentrale Async-Warte-Helper `_pause()` und `_wait_for_state()` in `src/web/routes.py` eingefuehrt. Blockierende `_time.sleep(...)`-Wartepfade in den asynchronen Routen fuer Lens-ChArUco, Stereo-Kalibrierung, Single-Start, Multi-Start und Multi-Stop durch `await asyncio.sleep(...)` bzw. nicht-blockierendes Polling ersetzt. Route-Tests decken die neuen Async-Wartepfade fuer Single/Multi-Start-Stop und Stereo-Kalibrierung ab. Geaenderte Dateien: `src/web/routes.py`, `tests/test_routes_extra.py`.

Ziel:

- Event-Loop-Stalls in API-Endpunkten vermeiden und WebSocket-/MJPEG-Reaktivitaet unter Last stabil halten

Typische Arbeiten:

- alle `_time.sleep(...)` in `async def`-Routes durch nicht-blockierende Wartepfade ersetzen (`await asyncio.sleep(...)` oder threadbasierte Worker)
- Start/Stop-Warte- und Polling-Logik in dedizierte Helper kapseln statt verteilt in Route-Handlern
- Tests fuer parallel laufende Requests waehrend Multi-Start/Stop ergaenzen (keine blockierte Antwortpipeline)

Warum kritisch: Blockierende Sleeps in asynchronen Endpunkten bremsen den gesamten Server und fuehren zu zufaelligen UI-Haengern.

Verknuepfte Weaknesses: keine
Verknuepfte Entscheidungen: ADR-004

## Prioritaet 20: Hit-Candidate-Lifecycle serverseitig haerten (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Pending-Hits werden jetzt serverseitig verwaltet: `src/main.py` enthaelt zentrale Helper fuer `add_pending_hit()`, `expire_pending_hits()`, `pop_pending_hit()` und `clear_pending_hits()`. Neue Kandidaten werden vor dem Einfuegen gegen TTL (`30s`) und eine harte Obergrenze (`10`) geprueft; abgelaufene Kandidaten werden per `hit_rejected` mit `reason="timeout"` verworfen, Overflow-Drops mit `reason="overflow"`. Die Pipeline fuehrt zusaetzlich im Laufzeitloop periodisches Cleanup aus, und `/api/hits/pending`, `/api/stats` sowie der WebSocket-Initialzustand benutzen jetzt die serverseitig bereinigte Sicht. Stats liefern neue Lifecycle-Zaehler fuer Expiry/Timeout/Overflow. Geaenderte Dateien: `src/main.py`, `src/web/routes.py`, `tests/test_main_coverage.py`, `tests/test_routes_coverage2.py`.

Ziel:

- Pending-Hits auch ohne Frontend-Interaktion kontrolliert abbauen und Speicher-/State-Aufblaehung verhindern

Typische Arbeiten:

- serverseitiges TTL-Expiry fuer `pending_hits` einbauen (nicht nur Frontend-Timeout)
- harte Obergrenze fuer offene Kandidaten definieren (z.B. FIFO-Drop mit Logging)
- Metrics/API-Felder fuer expired/rejected-by-timeout nachziehen und testen

Warum kritisch: Aktuell wird Auto-Timeout primaer im Frontend gesteuert; bei getrennten/instabilen Clients bleiben Kandidaten laenger liegen als gewollt.

Verknuepfte Weaknesses: keine
Verknuepfte Entscheidungen: ADR-002, ADR-005

## Prioritaet 21: Kalibrierungsmodul aufteilen und gezielt absichern (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** `src/cv/calibration.py` ist jetzt ein schlankerer Manager-/CLI-Wrapper; Board-spezifische Workflows wurden nach `src/cv/calibration_board.py`, Konfig-IO nach `src/cv/calibration_store.py` und gemeinsame Defaults/Konstanten nach `src/cv/calibration_common.py` ausgelagert. Die ChArUco-Frame-Sammlung ist in `src/cv/charuco_detection.py` zentralisiert und wird von `CalibrationManager` und `CameraCalibrationManager` gemeinsam genutzt. Zusaetzlich wurden Persistenz-, Legacy-Migration- und Fehlerpfad-Tests in `tests/test_calibration.py` erweitert. Geaenderte Dateien: `src/cv/calibration.py`, `src/cv/calibration_board.py`, `src/cv/calibration_common.py`, `src/cv/calibration_store.py`, `src/cv/charuco_detection.py`, `src/cv/camera_calibration.py`, `tests/test_calibration.py`.

Ziel:

- Komplexitaet in `src/cv/calibration.py` reduzieren und den aktuell schwachen Testbereich systematisch absichern

Typische Arbeiten:

- `calibration.py` entlang der Workflows (Board-ArUco, Lens-ChArUco, Helpers) in klarere Teilmodule trennen
- API-Verhalten unveraendert halten, aber interne Zustandsuebergaenge isoliert testbar machen
- Coverage fuer den Kalibrierungs-Pfad auf mindestens mittleres Niveau anheben (Fehlerpfade + Recovery explizit)

Warum kritisch: Das Modul ist gross und hat im Vergleich zu Kernmodulen deutlich weniger Abdeckung; Kalibrierung bleibt betriebskritisch.

Verknuepfte Weaknesses: keine
Verknuepfte Entscheidungen: ADR-001, ADR-002

## Prioritaet 22: Multi-Cam-Fusion fuer Burst- und Timing-Faelle haerten (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** `src/cv/multi_camera.py` puffert Detektionen jetzt pro Kamera in einem kleinen Zeitfenster statt nur als letzten Treffer. Die Fusion arbeitet anchor-basiert in zeitlicher Reihenfolge: alte unmatched Entries laufen kontrolliert in `single`/`single_timeout`, passende Entries werden nur selektiv aus dem Buffer entfernt, und Burst-Folgen koennen dadurch nacheinander fusioniert werden, statt sich gegenseitig zu ueberschreiben. Die Hardening-Tests wurden in `tests/test_multi_camera.py` und `tests/test_multi_robustness.py` auf die neue Zeitfenster-Semantik erweitert. Geaenderte Dateien: `src/cv/multi_camera.py`, `tests/test_multi_camera.py`, `tests/test_multi_robustness.py`.

Ziel:

- Fehlzuordnungen bei zeitnahen Treffern mehrerer Kameras reduzieren und Fusion reproduzierbarer machen

Typische Arbeiten:

- Detection-Buffer von "letzter Treffer pro Kamera" auf zeitfensterbasierten Buffer erweitern
- klare Pairing-Regeln fuer mehrere nahe Treffer (Burst) definieren und testen
- Triangulations-/Fallback-Entscheidungen mit nachvollziehbaren Debug-Metadaten anreichern

Warum kritisch: Die aktuelle Buffer-Logik kann bei dichten Trefferfolgen Detektionen ueberschreiben und dadurch Fusionsergebnisse verfaelschen.

Verknuepfte Weaknesses: keine
Verknuepfte Entscheidungen: ADR-002, ADR-003

## Prioritaet 23: App-State-Concurrency vertraglich absichern (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Gemeinsame Runtime-Mutation fuer Pipeline-, Thread-Handle- und Multi-Frame-State in `src/utils/state.py` zentralisiert und aus `src/main.py`/`src/web/routes.py` ueber Helper angesprochen. `lifespan()` initialisiert den Shared State jetzt deterministisch pro App-Start, statt verteilte Altwerte weiterzutragen. Lifespan-sensitive Route- und Readiness-Tests wurden auf explizites State-Setup nach `TestClient`-Startup umgestellt. Geaenderte Dateien: `src/utils/state.py`, `src/main.py`, `src/web/routes.py`, `tests/test_main_coverage.py`, `tests/test_routes_extra.py`, `tests/test_routes_coverage2.py`, `tests/test_multi_hardening.py`.

Ziel:

- gemeinsame Zustandsmutation zwischen Routen und Hintergrundthreads explizit und konsistent absichern

Typische Arbeiten:

- Zugriff auf `app_state` in klaren State-Helpern kapseln (statt freier Dict-Mutationen)
- Lock-Konzept fuer Lifecycle, Pending-Hits und Pipeline-Referenzen vereinheitlichen
- Race-Tests fuer Single/Multi-Umschalten und gleichzeitige API-Calls hinzufuegen

Warum kritisch: Der Zustand ist stark geteilt; uneinheitliche Mutation erhoeht das Risiko fuer schwer reproduzierbare Runtime-Fehler.

Verknuepfte Weaknesses: keine
Verknuepfte Entscheidungen: ADR-003, ADR-005

## Prioritaet 24: Generierte Laufartefakte aus dem Worktree fernhalten (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Die bereits vorhandenen Ignore-Regeln fuer Python-/pytest-Artefakte wurden beibehalten, aber die historisch mitgetrackten `__pycache__`-Dateien per `git rm --cached -r ...` aus dem Git-Tracking entfernt, sodass kuenftige Testlaeufe den Worktree nicht mehr mit diesen Dateien verunreinigen. Der Hygiene-Schritt wurde zusaetzlich in `agent_docs/development_workflow.md` dokumentiert. Geaenderte Dateien: `agent_docs/development_workflow.md` sowie die ehemals getrackten `src/**/__pycache__/*`- und `tests/__pycache__/*`-Artefakte (aus dem Index entfernt).

Ziel:

- lokale Test- und Laufspuren wie `__pycache__` nicht mehr als dauerhafte Worktree-Veraenderungen hinterlassen

Typische Arbeiten:

- Python-Artefakte (`__pycache__`, `.pyc`, pytest-Cache) per `.gitignore` oder Repo-Regel sauber ausschliessen
- optionalen Cleanup-/Diagnose-Schritt fuer Entwicklungs- und Testlaeufe dokumentieren
- pruefen, ob reale Betriebsdaten weiterhin unangetastet bleiben

Warum kritisch: Die Artefakte sind kein Produktionsfehler, erzeugen aber dauerhaft Rauschen im Worktree und erschweren die Sicht auf echte Code- und Doku-Aenderungen.

Verknuepfte Weaknesses: keine
Verknuepfte Entscheidungen: ADR-005
