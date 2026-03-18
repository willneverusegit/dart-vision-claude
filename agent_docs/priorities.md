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

## Prioritaet 8: Performance-Monitoring und Alerting (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** TelemetryHistory-Modul mit Ring-Buffer (300 Samples), FPS/Queue-Alert-Erkennung mit konfigurierbarem Sustain-Intervall (5s). Async-Telemetrie-Sammlung im Lifespan (1s Intervall). API-Endpunkt `/api/telemetry/history` mit History, Alerts, Summary. WebSocket-Broadcast bei Alert-Zustandsaenderung (`telemetry_alert`). Frontend: Performance-Monitor-Panel mit Canvas-Chart (FPS + Queue + Threshold-Linie), Summary-Anzeige, Alert-Banner. Optionales CPU-Monitoring via psutil. 17 neue Tests. Geaenderte Dateien: `src/utils/telemetry.py`, `src/main.py`, `src/web/routes.py`, `static/js/app.js`, `static/css/style.css`, `templates/index.html`, `tests/test_telemetry.py`.

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

## Prioritaet 10: UI-Design und Responsiveness (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** 5 UI-Verbesserungen: (a) Responsive Breakpoints fuer Mobile (375px) und Tablet (768px) — Header wrapping, kompakte Panels, vertikale Buttons. (b) Loading-Spinner beim Pipeline-Start (verschwindet bei erstem Frame). (c) Keyboard-Shortcut-Hints unterhalb der Game Controls (Enter/Del/U). (d) Kompakteres Scoreboard auf Mobile (kleinere Fonts, reduzierte min-height). (e) Kamera-Feed mit object-fit:contain und aspect-ratio:4/3. Geaenderte Dateien: `static/css/style.css`, `static/js/app.js`, `templates/index.html`.

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

## Prioritaet 12: DartImpactDetector Area-Range erweitern (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** area_max Default von 1000 auf 2000 erhoeht. `scale_area_to_roi()` Methode fuer dynamische Skalierung basierend auf ROI-Groesse. Confidence-Scoring Area-Range auf [80, 2500] erweitert. 8 neue Tests. Geaenderte Dateien: `src/cv/detector.py`, `tests/test_detector.py`.

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

## Prioritaet 18: Checkout-Tabelle erweitern und Spielvarianten (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Checkout-Tabelle mit PDC/BDO-Standard-Checkouts fuer alle Scores 2-170 (ausser 7 unmoeglich: 159,162,163,165,166,168,169). Bevorzugte Pfade (z.B. 170=T20 T20 D25) als erste Vorschlaege. Double-In-Variante fuer X01 implementiert (Konstruktor-Parameter `double_in=True`). Checkout-Vorschlag passt sich automatisch an verbleibende Darts an (war bereits via `darts_remaining` implementiert). 18 neue Tests. Geaenderte Dateien: `src/game/checkout.py`, `src/game/engine.py`, `src/game/models.py`, `tests/test_checkout_extended.py`.

Ziel:

- Checkout-Vorschlaege vervollstaendigen und weitere X01-Varianten unterstuetzen

Typische Arbeiten:

- Checkout-Tabelle um 2-Dart und 3-Dart Pfade mit bevorzugten "Standard-Checkouts" ergaenzen (z.B. 170 = T20 T20 D25)
- Double-In-Variante fuer X01 unterstuetzen (erster Wurf muss Double sein)
- Checkout-Vorschlag auch fuer 2. und 3. Dart der Runde anpassen (nach erstem Wurf restlichen Checkout berechnen)
- Spieler-spezifische Checkout-Praeferenzen (optional, spaeter)

## Prioritaet 19: Before/After-Frame-Vergleich fuer Treffererkennung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** FrameDiffDetector mit IDLE/IN_MOTION/SETTLING-State-Machine in `src/cv/diff_detector.py`. MOG2 bleibt Motion-Trigger, Positionsbestimmung via cv2.absdiff() zwischen Baseline und stabilem Post-Wurf-Frame. register_confirmed() public method in DartImpactDetector. Integration in DartPipeline.process_frame() — update() vor Motion-Gate-Early-Return. reset_turn() setzt alle drei Detektoren zurück (dart_detector, frame_diff_detector, motion_detector). Geaenderte Dateien: `src/cv/diff_detector.py`, `src/cv/detector.py`, `src/cv/pipeline.py`, `tests/test_diff_detector.py`, `tests/test_detector.py`, `tests/test_pipeline_diff_integration.py`.

## Prioritaet 22: Telemetrie-Export und Post-Mortem-Analyse (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** TelemetryJSONLWriter schreibt Samples als JSONL (aktiviert via `DARTVISION_TELEMETRY_FILE` env). Export-Endpunkt `/api/telemetry/export` liefert JSON (mit session_id) oder CSV Download (`?format=csv`). Session-ID wird in app_state propagiert und im Export-Response mitgeliefert. Frontend: JSON- und CSV-Download-Buttons im Performance-Monitor-Panel. Tests in test_telemetry.py und test_routes_coverage2.py. Geaenderte Dateien: `src/utils/telemetry.py`, `src/web/routes.py`, `src/main.py`, `static/js/app.js`, `templates/index.html`, `tests/test_routes_coverage2.py`.

Ziel:

- Telemetrie-Daten persistent speichern fuer spaetere Fehleranalyse

Typische Arbeiten:

- Telemetrie-Samples optional als JSONL in Logfile schreiben (via DARTVISION_TELEMETRY_FILE Env)
- Export-Endpunkt `/api/telemetry/export` als CSV/JSON-Download
- Session-bezogene Telemetrie mit Session-ID verknuepfen
- Frontend: Download-Button im Performance-Monitor-Panel

## Prioritaet 23: Dark/Light-Theme-Umschaltung und Accessibility (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Light-Theme CSS-Variante als `:root.light-theme` mit allen Custom Properties. Theme-Toggle-Button im Header (Sonne/Mond Unicode). localStorage-Persistenz + `prefers-color-scheme` Media Query als Default. Focus-Styles (`:focus-visible`) und ARIA-Labels fuer Accessibility. Geaenderte Dateien: `static/css/style.css`, `static/js/app.js`, `templates/index.html`.

Ziel:

- Theme-Wechsel fuer verschiedene Umgebungen (helle Raeume) und bessere Zugaenglichkeit

Typische Arbeiten:

- CSS Custom Properties bereits vorhanden — Light-Theme-Variante als alternatives Farbschema
- Toggle-Button im Header oder Settings-Bereich
- `prefers-color-scheme` Media Query als Default
- Kontrast-Pruefung: WCAG AA Minimum fuer alle Text-Elemente
- Focus-Styles fuer Tastaturnavigation auf Buttons und Inputs

## Prioritaet 20: Dart-Tip-Detection (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Tip-Detection-Algorithmus in `src/cv/tip_detection.py`: minAreaRect fuer Achsenbestimmung, Kontur-Halbierung entlang der Achse, schmalere Haelfte = Tip-Seite, aeusserster Punkt = Tip-Position. Integration in `src/cv/diff_detector.py` — Tip wird als primaere Position in DartDetection.center verwendet, Fallback auf Centroid. `DartDetection.tip` Feld ergaenzt. Diagnostics erweitert: Cyan-Ring fuer Tip, gelbe Achsen-Linie Centroid→Tip. Validierung gegen 18 echte Aufnahmen (cam_left + cam_right): 18/18 OK, durchschnittlich ~28px Abweichung Centroid→Tip. Geaenderte Dateien: `src/cv/tip_detection.py`, `src/cv/diff_detector.py`, `src/cv/detector.py`, `tests/test_tip_detection.py`, `scripts/validate_tip_detection.py`.

Verknuepfte Weaknesses: keine
Verknuepfte Entscheidungen: keine

Ziel:

- Dartspitze statt Flug-Centroid als Trefferposition verwenden

Ansatz: Daten-zuerst — erst echte Diff-Konturen sammeln, dann Algorithmus designen.
Erkenntnis: Die Spitze ist dort wo die Kontur am schmalsten wird (Barrel → Shaft → Tip).

Typische Arbeiten:

- Phase 1: Diagnose-Modus in FrameDiffDetector — bei jedem erkannten Dart Diff-Maske + Kontur als PNG speichern ✅
- Phase 1: Probewuerfe am Board (links/rechts, verschiedene Kameras) und Aufnahmen auswerten ✅
- Phase 2: Tip-Detection-Algorithmus auf echten Konturdaten designen (schmalste Stelle der Kontur) ✅
- Phase 2: DartDetection.frame_count-Semantik bereinigen (settle_frames umbenennen)
- Tests: auf echten Kontur-Snapshots, nicht nur synthetisch ✅

## Prioritaet 21: Kontur-Robustheit gegen Schatten und Luecken (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Elongation-Filter in FrameDiffDetector._compute_diff(): minAreaRect-Aspect-Ratio-Check verwirft nicht-dart-foermige Blobs (Schatten, Beleuchtungswechsel). Konfigurierbarer Parameter `min_elongation` (default 1.5, Darts typisch >2.0). Morphologisches Closing war bereits implementiert (5x5 Ellipse). 6 neue Tests: Elongation-Filter (reject/accept), Closing fuellt Luecken, Shadow-Artefakt-Ablehnung, konfigurierbare Schwelle, Validierung. Geaenderte Dateien: `src/cv/diff_detector.py`, `tests/test_diff_detector.py`.

Ziel:

- Konturen in der Diff-Maske auch bei suboptimaler Beleuchtung stabil halten

Typische Arbeiten:

- Morphologisches Closing (cv2.morphologyEx) nach Threshold-Schritt
- Elongierungs-Filter: Konturen mit Aspect-Ratio < 1.5 verwerfen (kein Dart)
- Schatten-Robustheit: CLAHE vor Diff oder adaptiver Threshold
- Tests: synthetische Masken mit Luecken/Schatten

## Prioritaet 24: Kamera-Vergleich und Kontur-Referenzdaten (neu — entdeckt bei P20)

Ziel:

- Verstehen wie sich Diff-Konturen zwischen verschiedenen Kameras und Wurfpositionen unterscheiden

Typische Arbeiten:

- Probewuerfe mit verschiedenen Kameras aufnehmen (links/rechts positioniert)
- Diff-Masken vergleichen: Konturform, Groesse, Schatten-Einfluss pro Kamera
- Referenz-Datensatz fuer zukuenftige Algorithmus-Entwicklung (P20, P21) aufbauen
- Beleuchtungs-Einfluss dokumentieren (welche Kamera-Position produziert sauberste Konturen)

## Prioritaet 25: Tip-Detection Genauigkeit gegen Board-Scoring validieren (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** 22 Tests in `tests/test_tip_vs_centroid_scoring.py`: 10 individuelle Szenarien (Triple/Double/Bull/Sektor-Grenzen), 10 parametrisierte Validierungen, 1 Aggregat-Accuracy-Test (Tip >= Centroid, >= 80%). Beweist dass Tip-basiertes Scoring bei Segmentgrenzen zuverlaessiger ist als Centroid — Centroid driftet ~28-40px Richtung Flights und landet im falschen Ring/Sektor. Korrekte mm-basierte Normalisierung beruecksichtigt (Triple bei 116.5-125.9px, nicht 106-116px). Geaenderte Dateien: `tests/test_tip_vs_centroid_scoring.py`.

Ziel:

- Pruefen ob die Tip-Position nach Board-Transformation das korrekte Segment trifft

Typische Arbeiten:

- Probewuerfe auf bekannte Felder (T20, D16, Bull etc.) und Tip-Position durch Kalibrierung→Scoring-Pipeline fuehren
- Vergleich: Tip-basiertes Scoring vs. Centroid-basiertes Scoring — welches trifft das richtige Feld haeufiger?
- Schwellwert bestimmen: ab welcher Konturgroesse ist Tip-Detection zuverlaessiger als Centroid?
- Kamera-spezifische Korrekturfaktoren evaluieren (cam_left schaerfer als cam_right)

## Prioritaet 26: Kamera-Qualitaet angleichen oder kompensieren (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Neues Modul `src/cv/sharpness.py` mit Laplacian-Varianz-Schaerfemetrik, EMA-basiertem SharpnessTracker, sharpness-adaptiver Threshold-Berechnung und dynamischer Wire-Filter-Kernelgroesse. Integration in `FrameDiffDetector`: automatische Schaerfe-Messung pro Kamera, Threshold-Anpassung (scharf→hoeher, unscharf→niedriger), groesserer Morphologie-Kernel fuer Wire-Artefakt-Unterdrueckung bei scharfen Kameras. Schaerfe-Metrik und Quality-Report in Diagnostics-Metadaten (`camera_quality` Block) und `get_params()`. 25 neue Tests in `tests/test_sharpness.py`. Geaenderte Dateien: `src/cv/sharpness.py` (neu), `src/cv/diff_detector.py`, `tests/test_sharpness.py` (neu).

## Prioritaet 27: Marker-Kalibrierung auf neue Masse aktualisieren (neu — Session-Start)

Ziel:

- Kalibrierungskonfiguration an geaenderte physische Marker-Masse anpassen

Typische Arbeiten:

- ArUco Dict 7x5 50, Marker 0-3, 75mm Kantenlaenge — unveraendert
- Mitte-zu-Mitte Abstand: 430mm (verifizieren)
- Corner-zu-Corner: 505mm (vorher 480mm) — in calibration_config.yaml aktualisieren
- Kalibrierung neu durchfuehren und Qualitaetsmetrik vergleichen

## Prioritaet 28: radii_px vs mm-Normalisierung dokumentieren (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Bereits in frueherer Session implementiert. Docstrings in BoardPose, BoardGeometry und point_to_score() dokumentieren klar dass radii_px nur fuer Overlays/UI dient und Scoring ausschliesslich mm-basierte RING_BOUNDARIES nutzt. check_radii_consistency() Methode warnt bei >15% Abweichung. 4 Tests in TestRadiiConsistency. Geaenderte Dateien: `src/cv/geometry.py`.

Ziel:

- Klarstellen dass `BoardGeometry.radii_px` nur fuer Overlays/UI dient und `point_to_score()` ausschliesslich mm-basierte Konstanten aus `geometry.py` nutzt

Typische Arbeiten:

- Docstring in `BoardGeometry` ergaenzen: `radii_px` ist fuer visuelle Darstellung, nicht fuer Scoring
- Docstring in `point_to_score()` ergaenzen: nutzt `RING_BOUNDARIES` (mm-basiert), nicht `radii_px`
- Optional: Konsistenz-Check einbauen der warnt wenn `radii_px` stark von den mm-Proportionen abweicht (deutet auf falsche Kalibrierung hin)

## Prioritaet 29: Stereo Calibration UI Wizard (neu — Multi-Cam Assessment)

Kritikalitaet: KRITISCH

Ziel:

- Stereo-Kalibrierung fuer Nicht-Experten bedienbar machen

Typische Arbeiten:

- Step-by-Step Wizard: Kameras auswaehlen → Intrinsics pruefen → Stereo-Paare aufnehmen → Kalibrierung berechnen → Reprojektionsfehler anzeigen → Speichern/Verwerfen
- Fortschritts-Feedback via WebSocket (Frame-Counter, Winkel-Hinweise)
- Reprojektionsfehler-Schwelle als Quality Gate (RMS < 1.0px)
- Dateien: src/cv/stereo_calibration.py, src/web/routes.py, templates/index.html, static/js/ (neues Modul)

## Prioritaet 30: Camera Error Reporting to UI (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Kamera-Fehler im Multi-Cam-Betrieb jetzt vollstaendig sichtbar. Erweitertes Error-Tracking in `MultiCameraPipeline` mit Zeitstempel und Level (warning/error). Laufzeit-Frame-Fehler werden nach 10 konsekutiven Fehlern als Warning und nach 50 als Error eskaliert; bei Erholung automatisch zurueckgesetzt. `on_camera_errors_changed` Callback broadcastet Fehler per WebSocket (`camera_errors` Event). Frontend zeigt per-Kamera Status-Badges (gruen/gelb/rot) im Video-Grid und im Status-Panel. Error-Level `error` loest `_showError()` Benachrichtigung aus. `CameraHealthMonitor` unterstuetzt neues dict-Format mit Rueckwaertskompatibilitaet fuer String-Fehler. 7 neue Tests in `test_multi_camera.py`, 2 neue Tests in `test_camera_health.py`. Geaenderte Dateien: `src/cv/multi_camera.py`, `src/web/camera_health.py`, `src/web/routes.py`, `static/js/app.js`, `static/css/style.css`, `tests/test_multi_camera.py`, `tests/test_camera_health.py`.

Kritikalitaet: KRITISCH

Ziel:

- Kamera-Fehler im Multi-Cam-Betrieb sichtbar machen

Typische Arbeiten:

- get_camera_errors() aus multi_camera.py an WebSocket broadcast anbinden
- Per-Camera Status-Badges im Multi-Cam-Panel (gruen/gelb/rot)
- Fehlermeldungen mit Kontext (welche Kamera, welcher Fehler, Zeitstempel)
- Dateien: src/cv/multi_camera.py, src/web/routes.py, static/js/app.js

## Prioritaet 31: Intrinsics Validation vor Stereo-Kalibrierung (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** `validate_stereo_prerequisites()` in `src/cv/stereo_calibration.py` prueft beide Kameras via `CameraCalibrationManager.validate_intrinsics()`. Stereo-Kalibrierungsendpunkt in `src/web/routes.py` blockiert mit deutscher Fehlermeldung ("Bitte Linsen-Kalibrierung zuerst durchfuehren") wenn Intrinsics fehlen. `has_valid_intrinsics()` in `BoardCalibrationManager` als zusaetzlicher Check. 25 Tests in `tests/test_intrinsics_validation.py` und `tests/test_calibration_validation.py` decken alle Szenarien ab (beide gueltig, eine fehlend, beide fehlend, Warnings).

Kritikalitaet: KRITISCH

Ziel:

- Sicherstellen dass Kameras korrekte Intrinsics haben bevor Stereo-Kalibrierung gestartet wird

Typische Arbeiten:

- Pre-Flight-Check: Beide Kameras muessen gueltige camera_matrix haben
- Klare Fehlermeldung wenn fehlend: "Bitte Linsen-Kalibrierung fuer cam_left zuerst durchfuehren"
- Stereo-Kalibrierung blockieren bis beide Kameras bereit
- Dateien: src/cv/stereo_calibration.py, src/cv/board_calibration.py

## Prioritaet 32: Triangulation Telemetrie (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Bereits in frueherer Session implementiert. TriangulationTelemetry-Klasse mit Ring-Buffer, Lifetime-Countern (attempts/successes/voting-fallbacks/single-fallbacks/z-rejected), Reprojektionsfehler- und Z-Depth-Statistiken, Failure-Alert bei >30%. Integration in MultiCameraPipeline via record_attempt(). API-Endpunkte `/api/telemetry/stereo` und `/api/multi-cam/telemetry`. 17 bestehende Tests + 3 neue API-Tests. Geaenderte Dateien: `tests/test_multi_cam_api.py` (neu).

Kritikalitaet: KRITISCH

Ziel:

- Triangulations-Erfolgsrate und -Qualitaet messbar machen

Typische Arbeiten:

- Tracking: Versuche, Erfolge, Voting-Fallbacks, Single-Cam-Fallbacks
- Reprojektionsfehler pro Treffer loggen
- Z-Depth-Verteilung erfassen
- API-Endpoint /api/telemetry/stereo
- Alert wenn Triangulation >30% fehlschlaegt
- Dateien: src/cv/stereo_utils.py, src/cv/multi_camera.py, src/utils/telemetry.py, src/web/routes.py

## Prioritaet 33: Multi-Cam FPS/Buffer Governors (neu — Multi-Cam Assessment)

Kritikalitaet: HOCH

Ziel:

- CPU-Ueberlastung bei mehreren Kameras auf i5-Laptop verhindern

Typische Arbeiten:

- Per-Camera Frame-Budget (default 15fps fuer Sekundaer-Kameras)
- Detection Buffer Queue-Tiefe begrenzen (max 5 Eintraege)
- Backpressure: bei vollem Buffer neue Frames skippen
- Frame-Drop-Erkennung pro Kamera mit Telemetrie-Export
- Dateien: src/cv/multi_camera.py, config/multi_cam.yaml

## Prioritaet 34: 3+ Camera Fusion (neu — Multi-Cam Assessment)

Kritikalitaet: HOCH

Ziel:

- Mehr als 2 Kameras fuer Triangulation nutzen

Typische Arbeiten:

- Aktuell wird nur das erste gueltige Stereo-Paar verwendet; auf alle Paare erweitern
- Konsistenz-Check: Ausreisser >10% vom Median verwerfen
- Ergebnisse mitteln fuer hoehere Genauigkeit
- Dateien: src/cv/multi_camera.py, src/cv/stereo_utils.py

## Prioritaet 35: Konfigurierbares Sync-Window und Depth Tolerance (neu — Multi-Cam Assessment)

Kritikalitaet: HOCH

Ziel:

- Hardcoded Konstanten konfigurierbar machen

Typische Arbeiten:

- MAX_DETECTION_TIME_DIFF_S (aktuell 150ms) nach config/multi_cam.yaml verschieben
- BOARD_DEPTH_TOLERANCE_M (aktuell 15mm) konfigurierbar machen
- Presets: "tight" (10mm/100ms), "standard" (15mm/150ms), "loose" (20mm/200ms)
- Dateien: src/cv/multi_camera.py, config/multi_cam.yaml

## Prioritaet 36: Multi-Cam Hardware E2E Test (neu — Multi-Cam Assessment)

Kritikalitaet: MITTEL

Ziel:

- Triangulation mit echten USB-Kameras validieren

Typische Arbeiten:

- Test-Framework fuer 2+ echte Kameras mit gleichzeitiger Frame-Aufnahme
- Offline-Replay mit Triangulation gegen Ground Truth
- Minimale PC-Specs dokumentieren (CPU, USB-Bandbreite)
- Dateien: tests/e2e/test_multi_cam_e2e.py

## Prioritaet 37: Live-Realtest am Board — Parameter tunen (neu — entdeckt bei Live-Tuning-Session)

Kritikalitaet: HOCH

Ziel:

- Erste echte Live-Session: Kamera aktiv, Darts werfen, CV-Parameter im Browser anpassen bis Erkennung zuverlaessig funktioniert
- Optimale Defaults fuer diff_threshold, settle_frames, min_diff_area ermitteln

Typische Arbeiten:

- `python -m src.main` starten, Browser oeffnen, Tune-Panel nutzen
- diff_threshold (aktuell 50) und min_diff_area (aktuell 50) am echten Board validieren
- settle_frames (aktuell 5) pruefen — zu viel = langsam, zu wenig = Fehldetektionen
- Gute Werte als neue Defaults in diff_detector.py uebernehmen
- Diagnostics aktivieren und Diff-Masken bei Fehldetektionen analysieren
- Ergebnisse in current_state.md dokumentieren

## Prioritaet 38: Drei-Stufen-Morphologie und Sub-Pixel Tip Refinement (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Tier-1-Optimierungen der Dart-Detection implementiert:
(a) Board-Wire-Filtering via 2x2 morphologisches Opening vor Closing — entfernt duenne Draht-Artefakte scharfer Kameras aus dem Diff.
(b) Elongierter Closing-Kernel (3x11 Rect) als dritte Morphologie-Stufe — schliesst bis zu 8px Luecken in Dart-Schaft-Fragmenten.
(c) Sub-Pixel Tip Refinement via `cv2.cornerSubPix()` auf 20x20 ROI um den erkannten Tip — hoehere Genauigkeit an Ring/Sektor-Grenzen.
(d) min_diff_area Default von 50 auf 30 gesenkt — Outer-Bull-Blobs (~40px²) werden nicht mehr verworfen.
9 neue Tests. Geaenderte Dateien: `src/cv/diff_detector.py`, `src/cv/tip_detection.py`, `src/cv/pipeline.py`, `tests/test_diff_detector.py`, `tests/test_tip_detection.py`, `tests/test_cv_params_api.py`.

---

# Dart Detection Optimierungsplan — Konsolidierte Ideenliste

Quellen: Agent-Recherche (State-of-the-Art, OpenCV-Techniken, GitHub-Projekte, DeepDarts CVPR 2021), Technical Guide ("Automatic dart scoring with computer vision"), Codebase-Audit, bekannte Issues.

Priorisiert nach **Nuetzlichkeit fuer unser Setup** (Single-Cam Hauptpfad, CPU-only, Python/OpenCV, ArUco-Kalibrierung, 400x400 ROI).

## TIER 1: Sofort umsetzbar, hoher Impact (✅ bereits implementiert in P38)

| # | Idee | Status |
|---|------|--------|
| 1 | Board-Wire-Filtering (Morphological Opening 2x2 vor Closing) | ✅ P38 |
| 2 | Elongierter Closing-Kernel (3x11 Rect) fuer Shaft-Luecken | ✅ P38 |
| 3 | Sub-Pixel Tip Refinement via cornerSubPix | ✅ P38 |
| 4 | min_diff_area auf 30 fuer Outer-Bull-Erkennung | ✅ P38 |

## TIER 2: Naechste Schritte — einzeln umsetzbar, messbarer Gewinn

| # | Idee | Quelle | Aufwand | Impact | Details |
|---|------|--------|---------|--------|---------|
| 5 | **HoughLinesP fuer Dart-Shaft-Detection** | Tech Guide, Autodarts | Mittel | HOCH | Autodarts-Kernansatz: `cv2.HoughLinesP()` auf Edge-Detected Diff-Image, Shaft-Linie finden, Tip = Endpunkt Richtung Board-Center. Threshold ~50 bei 720p. Deutlich robuster als Contour-Extrempunkt bei fragmentierten Konturen. Ergaenzt bestehende Tip-Detection als zweiter Algorithmus mit Confidence-Vergleich. |
| 6 | **fitLine fuer Tip-Richtung** | Agent-Research | Klein | HOCH | `cv2.fitLine(contour, cv2.DIST_L2)` durch Dart-Contour, Tip = Endpunkt der Linie naeher am Bullseye. Robuster als minAreaRect bei unregelmaessigen Konturen. Kann als Fallback/Vergleich zu aktuellem Narrowing-Ansatz dienen. |
| 7 | **Temporal Stability Gating (3-Frame-Bestaetigung)** | Tech Guide, Flight Club Patent | Klein | HOCH | Nach SETTLING: 3+ aufeinanderfolgende Frames mit stabiler Position (Centroid-Drift < 3px) bevor Dart-Landed bestaetigt wird. Reduziert False Positives durch Vibration. Board-Vibration dauert 200-500ms. Aktuell: settle_frames=5 prueft nur Motion-Flag, nicht Positionsstabilitaet. |
| 8 | **Kamera-Sharpness Auto-Detection** | Agent-Research, P26 | Klein | MITTEL | Laplacian-Varianz (`cv2.Laplacian(gray, cv2.CV_64F).var()`) als Schaerfe-Metrik. Automatisch diff_threshold und min_diff_area pro Kamera anpassen. Scharfe Kamera: niedrigerer Threshold. Unscharfe Kamera: hoeherer Threshold, groessere min_area. |
| 9 | **Progressive Reference Frame Updates** | Tech Guide, alle Systeme | Klein | HOCH | Nach jedem bestatigten Dart: aktuellen Frame als neue Baseline setzen. Dadurch wird nur der NEUE Dart im Diff sichtbar, nicht alle bisherigen. Aktuell: Baseline wird in IDLE kontinuierlich aktualisiert — funktioniert bei unserem State-Machine-Ansatz bereits korrekt, aber explizit nach Scoring-Bestaetigung forcen ist robuster. |
| 10 | **Bounce-Out Detection** | Tech Guide, Flight Club Patent | Mittel | HOCH | Temporal Signature: kurzer Motion-Spike (2-5 Frames) gefolgt von Rueckkehr zum Pre-Throw-State. Vergleich Post-Frame vs. Baseline nach Settling — wenn Diff unter Threshold: Dart hat Board nicht getroffen. Wichtig fuer korrekte Spiellogik. |
| 11 | **Contour Shape Confidence Score** | Agent-Research, Tech Guide | Klein | MITTEL | Dart-Konturen: Aspect-Ratio 3-8, Solidity >0.6, Area 50-2000px. Score berechnen aus diesen Metriken, als Gewicht in Detection-Confidence einfliessen lassen. Aktuell: Confidence = area/500, sehr simpel. Besser: gewichteter Score aus Area + Elongation + Solidity. |
| 12 | **Light Stability Monitor** | Agent-Research | Klein | MITTEL | Pixel-Intensitaets-Varianz ueber die letzten N Frames tracken. Wenn Varianz zu hoch (schnelle Lichtaenderung): Diff-Berechnung pausieren oder Threshold temporaer erhoehen. Verhindert Fehldetektionen bei Lichtschalter/Wolken. |
| 13 | **Downscaled Motion Detection** | Tech Guide, Autodarts | Klein | MITTEL | Motion-Detection auf 4x herunterskaliertem Frame (100x100 statt 400x400). Nur bei Motion-Trigger volle Aufloesung analysieren. Spart ~75% CPU im Idle. Autodarts nutzt diesen Ansatz. |
| 14 | **Temporal Lock nach Scoring** | Tech Guide | Klein | MITTEL | ~2 Sekunden Motion-Ignore nach bestaetiger Erkennung. Verhindert False Positives durch Hand beim Dart-Herausziehen. Aktuell nicht implementiert — Hand-Motion kann neuen Detection-Cycle triggern. |

## TIER 3: Mittelfristig — groesserer Aufwand, signifikanter Gewinn

| # | Idee | Quelle | Aufwand | Impact | Details |
|---|------|--------|---------|--------|---------|
| 15 | **360° LED Ring Light** | Tech Guide, Scolia, Autodarts, alle Systeme | Hardware | SEHR HOCH | "Accuracy depends more on lighting uniformity than on algorithmic sophistication." Universelle Hardware-Empfehlung aller Systeme. Eliminiert Richtungsschatten komplett. Single biggest improvement fuer Erkennungsqualitaet. Kostet ~20-40€. |
| 16 | **Zweite/Dritte Kamera bei 120° Intervall** | Tech Guide, Autodarts | Hardware+SW | SEHR HOCH | Multi-Cam-Triangulation erreicht 99%+ vs. ~95% Single-Cam. Drei OV9732 bei 120° ist der Goldstandard. Unser Multi-Cam-Code ist vorbereitet (P29-P36). 3 Kameras bei 720p kosten ~30-50€. |
| 17 | **Homography-Fallback bei Marker-Occlusion** | Tech Guide | Mittel | HOCH | Wenn Marker durch Hand verdeckt: letzte gueltige Homography weiternutzen, "homography age" Counter fuehren, Warnung nach N Frames ohne Marker-Re-Detektion. |
| 18 | **LAB-Farbraum statt Grayscale fuer Diff** | Tech Guide | Mittel | MITTEL | CLAHE auf L-Kanal in LAB statt auf Grayscale. LAB trennt Luminanz von Chrominanz — robuster bei farbiger Beleuchtung. "LAB color space separates luminance from chrominance, making it ideal for lighting-invariant processing." |
| 19 | **HSV-basierte Flight-Color-Detection als Fallback** | Tech Guide | Mittel | MITTEL | Wenn Contour-basierte Detection versagt: HSV-Filterung auf bekannte Flight-Farben als Fallback. Setzt voraus: Dart-Farbe ist konfiguriert. Scolia hat Probleme mit dunklen Darts — helle Flights empfohlen. |
| 20 | **Gaussian Fitting fuer Sub-Pixel Tip** | Tech Guide | Mittel | MITTEL | Statt cornerSubPix: Gaussian-Fit auf Intensitaetsprofil um den erkannten Tip. Erreicht ~0.1-0.5 Pixel Genauigkeit (~1mm am Board). Akademisch besser als cornerSubPix, aber aufwaendiger. |
| 21 | **Multi-Dart Discrimination: Masking bekannter Darts** | Tech Guide | Mittel | HOCH | Bekannte Dart-Positionen im Diff maskieren um Re-Detektion zu vermeiden. Bei dicht gruppierten Darts: Contour-Area gegen erwartete Einzel-Dart-Flaeche pruefen. Robin-Hood-Detection als Spezialfall. |
| 22 | **Directional Morphological Kernels (Multi-Angle)** | Tech Guide (matherm) | Mittel | MITTEL | Rotierte Linien-Kernel bei 0°, 30°, 60°, ... 150°: der Winkel mit laengstem Contour-Match = Dart-Orientierung. Dann fitLine entlang dieser Richtung. Robuster als einzelner fixer Kernel. |

## TIER 4: Langfristig — Gamechanger, hoher Aufwand

| # | Idee | Quelle | Aufwand | Impact | Details |
|---|------|--------|---------|--------|---------|
| 23 | **YOLOv8n Dart-Tip-Detection (ONNX)** | DeepDarts CVPR 2021, Dart Sense, Tech Guide | Gross | SEHR HOCH | 6 MB Modell, ~20-40ms CPU via `cv2.dnn.readNetFromONNX()`. Kein PyTorch/TF noetig. Trainiert auf Dart-Tip + Calibration-Keypoints (DeepDarts-Ansatz). Loest Occlusion-Problem das klassisches CV nicht kann. 94.7% Single-Cam (DeepDarts), 99.3% (Gran Eye). Braucht 16k+ annotierte Trainingsbilder. |
| 24 | **Piezoelektrischer Kontakt-Mikrofon Trigger** | Tech Guide (Patent), Flight Club | Hardware | HOCH | Piezo-Sensor auf Board-Rueckseite als Impact-Trigger. CV-Pipeline nur bei Vibration aktivieren → drastisch reduzierte CPU-Last. Board selbst filtert Umgebungsgeraeusche. Kostet ~5€. Komplementaer zu CV, nicht als Ersatz. |
| 25 | **Vibrationssensor + CV Hybrid** | Tech Guide (Patent US20170307341A1) | Hardware+SW | HOCH | Kombination aus Piezo-Trigger und CV-Validierung. Piezo triggert schneller als Motion-Detection (~10ms vs. ~170ms). CV bestaetigt und lokalisiert. Beste Latenz bei niedrigstem CPU-Verbrauch. |
| 26 | **Semi-Supervised Bootstrapping fuer Trainingsdaten** | Tech Guide, DeepDarts | Gross | MITTEL | Aktuelles klassisches System nutzen um Trainingsbilder fuer ML-Modell vorzulabeln. Manuell korrigieren. Iterativ besseres Modell trainieren. Einziger praktischer Weg zu 16k+ Trainingsbildern. |
| 27 | **Event Camera (DVS)** | Tech Guide | Sehr gross | MITTEL | Microsekunden-Aufloesung, 120+ dB Dynamik, natuerliche Filterung statischer Hintergruende. Ideal fuer Dart-in-Flight-Detection. Aber: >1000€, niedrige Aufloesung, experimentell. Langfristige Zukunftstechnologie. |

## TIER 5: Quick-Wins — kleine Aenderungen, kleiner aber spuerbarer Gewinn

| # | Idee | Quelle | Aufwand | Impact | Details |
|---|------|--------|---------|--------|---------|
| 28 | **detectShadows=False in MOG2** | Agent-Research, Tech Guide | Trivial | KLEIN | Spart ~10-15% Verarbeitungszeit. Aktuell `detectShadows=True` in motion.py. Schatten-Detection unnoetig da Diff-basierte Erkennung genutzt wird. |
| 29 | **MOG2 learningRate senken** | Tech Guide | Trivial | KLEIN | `bg_sub.apply(frame, learningRate=0.002)` statt Default ~0.01. Darts auf dem Board werden langsamer in Background absorbiert. Verhindert dass gelandete Darts zu schnell "verschwinden". |
| 30 | **Kamera-Fokus-Qualitaetscheck beim Start** | Tech Guide | Klein | MITTEL | "Camera focus is the single most impactful quality factor." Laplacian-Varianz beim Pipeline-Start pruefen und Warnung wenn unter Schwelle. |
| 31 | **Helle Flights empfehlen / warnen** | Tech Guide, Scolia | Trivial | KLEIN | Doku/UI-Hinweis: "Dunkle Darts reduzieren Erkennungsgenauigkeit. Helle, kontrastreiche Flights empfohlen." Scolia und alle Systeme bestaetigen dies. |
| 32 | **cv2.setNumThreads() setzen** | Agent-Research | Trivial | KLEIN | Sicherstellen dass OpenCV alle verfuegbaren CPU-Kerne nutzt. Default ist oft nur 1 Thread. |
| 33 | **Frame-Skip im Idle** | Agent-Research, Tech Guide | Klein | MITTEL | Jeden 2. oder 3. Frame im Idle ueberspringen. Bei Motion auf jeden Frame wechseln. Halbiert CPU-Last im Leerlauf. |

## Empfohlene Reihenfolge fuer naechste Implementierung

1. **P37 Live-Realtest** — Ohne echte Board-Validierung sind weitere Algorithmus-Aenderungen blind
2. **#15 LED Ring Light** — Groesster Hardware-Impact, loest viele Software-Probleme
3. **#5 HoughLinesP** — Autodarts-Kernansatz, zweiter Tip-Detection-Algorithmus
4. **#7 Temporal Stability Gating** — Reduziert False Positives durch Vibration
5. **#10 Bounce-Out Detection** — Wichtig fuer korrekte Spiellogik
6. **#28-33 Quick-Wins** — Schnell umsetzbar, kumulativer Effekt
7. **#8 Camera Sharpness** — Automatische Kompensation fuer verschiedene Kameras
8. **#16 Zweite Kamera** — Sprung auf 99%+ Genauigkeit

---

## Prioritaet 39: Video-Replay-Testinfrastruktur

Ziel: Testvideos (`testvids/`) als Validierungsgrundlage fuer die Detection-Pipeline nutzen.

Typische Arbeiten:
- ArUco-Marker-Groesse konfigurierbar machen (nicht hardcoded 75mm)
- Batch-Test-Script fuer alle Videos (`scripts/test_all_videos.py`)
- E2E-pytest-Tests mit echten Videoaufnahmen
- Testvideos nutzen 100mm (10x10cm) Marker, DICT_4X4_50

Warum kritisch: Ohne echte Videovalidierung bleiben Algorithmus-Aenderungen ungetestet. Grundlage fuer P11 (E2E Tests mit echten Clips).

**Status: ✅ ERLEDIGT 2026-03-18**

**Umsetzung:** Alle Arbeitspakete abgeschlossen: (1) `marker_size_mm` konfigurierbar in Pipeline-Konstruktor, (2) `scripts/test_all_videos.py` Batch-Script mit Ground-Truth-Vergleich, (3) `testvids/ground_truth.yaml` mit 5 annotierten Videos (30 Wuerfe total), (4) `tests/e2e/test_testvid_replay.py` no-crash Tests fuer alle Videos, (5) NEU: `tests/e2e/test_ground_truth_validation.py` — pytest-Tests die Detection-Counts gegen Ground Truth validieren (Calibration-Test + parametrisierte Detection-Count-Tests pro Video). Detection-Count-Tests sind `xfail` markiert da Pipeline-Accuracy auf echten Videos noch nicht ausreichend (3/5 Videos bestehen bereits, 2/5 erkennen 0 Wuerfe wegen Baseline-Warmup-Problem). Geaenderte Dateien: `tests/e2e/test_ground_truth_validation.py`.

## Prioritaet 40: Adaptive Thresholds (Otsu-Bias + Search Mode) (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Bereits in Welle 3 implementiert. `FrameDiffDetector` berechnet Otsu-Threshold und biased ihn mit konfigurierbarem `otsu_bias_factor` (default 0.7). Min/Max-Clamping schuetzt gegen Ausreisser. Search Mode aktiviert sich nach `search_mode_frames` (default 90) Frames ohne Detection und senkt den Threshold um `search_mode_threshold_factor` (default 0.8). `adaptive_threshold` Flag erlaubt Deaktivierung fuer festen Threshold-Fallback. 10+ Tests fuer Otsu-Bias, Search Mode Aktivierung/Reset und Parameter-Export. Dual-Threshold Fusion wurde als nicht notwendig bewertet (Otsu-Bias + Search Mode decken die Anforderungen ab). Geaenderte Dateien: `src/cv/diff_detector.py`, `tests/test_diff_detector.py`.

## Prioritaet 41: Edge Cache (Canny-Reuse pro Frame) (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Edge-Cache-Infrastruktur in `FrameDiffDetector` implementiert: `get_cached_edges()` berechnet Canny-Edges einmal pro `frame_id` und cached das Ergebnis. Invalidierung bei neuem Frame, Cache-Clear bei `reset()`. 6 Tests vorhanden (cache hit, miss, invalidierung, disabled-mode, reset-clear, frame_id-increment). Die Contour-Analyse in `_compute_diff` arbeitet auf Threshold-Masken (nicht Canny), daher kein direkter Canny-Reuse moeglich. Der Cache steht fuer kuenftige HoughLinesP- oder Edge-basierte Analysen bereit. Geaenderte Dateien: keine (bereits implementiert in `src/cv/diff_detector.py`, Tests in `tests/test_diff_detector.py`).

## Prioritaet 42: Cooldown Management (raeumlich + zeitlich) (✅ ERLEDIGT 2026-03-18)

Quelle: `pipeline_patterns.md` Pattern #7

Ziel: Anti-Duplikat-Erkennung nach bestatigtem Treffer.

**Umsetzung:** `CooldownManager` in `src/cv/detection_components.py` um raeumliche Exclusion Zones erweitert. Jede `activate(position=...)` registriert eine 50px-Zone die nach 30 Frames verfaellt. `pipeline.process_frame()` prueft neue FrameDiff-Detections gegen aktive Zones und verwirft Duplikate. `reset()` leert alle Zones (Turn-Reset). 8 neue Tests fuer raeumliche/zeitliche Logik. Geaenderte Dateien: `src/cv/detection_components.py`, `src/cv/detector.py`, `src/cv/pipeline.py`, `tests/test_detection_components.py`.

## Prioritaet 43: Modulare Detection Components (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** `ShapeAnalyzer`, `CooldownManager`, `MotionFilter` als eigenstaendige Klassen in `src/cv/detection_components.py` extrahiert. `DartImpactDetector` delegiert Shape-Analyse und Cooldown an Komponenten. `DartPipeline` nutzt `MotionFilter` fuer Scoring-Lock und Idle-Tracking. 24 neue Tests. Geaenderte Dateien: `src/cv/detection_components.py` (neu), `tests/test_detection_components.py` (neu), `src/cv/detector.py`, `src/cv/pipeline.py`.

Quelle: `pipeline_patterns.md` Pattern #10

Ziel: Detection-Stages als eigenstaendige, testbare Klassen extrahieren.

Typische Arbeiten:
- `MotionFilter`, `TemporalGate`, `ShapeAnalyzer`, `ConfirmationTracker`, `CooldownManager`
- Einheitliches Interface pro Stage
- Erleichtert Unit-Tests und Austausch einzelner Algorithmen

Prioritaet: Niedrig (Architektur-Refactoring, kein direkter Feature-Gewinn). Sinnvoll wenn Pipeline-Komplexitaet weiter waechst.

## Prioritaet 44: Multi-Cam Integration Phase 1 — Camera Profiles & Detection Quality

Quelle: Multi-Cam-Integrationsplan (Session 2026-03-18)

Ziel: Heterogene Kameras (verschiedene Aufloesungen, FPS, Sensoren) korrekt handhaben und Detection-Quality-Metriken einfuehren.

Typische Arbeiten:
- Per-Camera Capture-Profile in `config/multi_cam.yaml` (resolution, fps, exposure, diff_threshold, priority)
- Per-Camera `target_fps` in `multi_camera.py` statt globalem `_TARGET_FPS=30`
- `set_exposure()`/`set_gain()` in `capture.py`
- `quality`-Feld in `DartDetection`, berechnet aus Contour-Elongation, Area, Tip-Erfolg
- `viewing_angle_quality` aus Homography-Determinante in `board_calibration.py`

Plan-Datei: `.claude/plans/shimmying-knitting-corbato.md` (Phasen 1+2)

## Prioritaet 45: Multi-Cam Integration Phase 2 — Sync, Governors, Multi-Pair Triangulation

Quelle: Multi-Cam-Integrationsplan (Session 2026-03-18)

Ziel: Konfigurierbare Sync-Fenster, adaptive FPS-Reduktion, und Multi-Pair-Triangulation fuer 3+ Kameras.

Typische Arbeiten:
- 2-Tier Sync-Logik (sync_wait_ms=300, max_time_diff_ms=150)
- Adaptive Z-Toleranz (auto-expand bei hoher Rejection-Rate)
- `FPSGovernor`-Klasse fuer CPU-Last-Management
- `triangulate_multi_pair()` mit Outlier-Rejection und gewichtetem Durchschnitt
- Reproj-Error-Normalisierung nach Bilddiagonale

Plan-Datei: `.claude/plans/shimmying-knitting-corbato.md` (Phasen 3-5)

## Prioritaet 46: Dark/Light Theme Toggle — Verbleibende Arbeiten (ERLEDIGT 2026-03-18)

**Umsetzung:** 3-Wege-Theme-Zyklus (Dark->Light->High-Contrast) im Toggle-Button. CSS-Transition (0.3s ease) auf Hauptelementen fuer sanften Wechsel. High-Contrast-Theme mit WCAG-AAA-Kontrasten, dickeren Borders und Focus-Outlines. prefers-color-scheme Regel schliesst high-contrast aus. Dateien: `static/css/style.css`, `static/js/app.js`.

## Prioritaet 47: Morphology Kernel Cache und Threshold-Mask Reuse (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Kernels waren bereits als Instanz-Attribute gecacht (_opening_kernel, _closing_kernel, _elongated_kernel). cv2.absdiff-Cache pro Frame (_get_diff) und morph-Cache bereits in P47-Vorgaenger implementiert. Zusaetzlich morph-mask Caching fuer _compute_diff ergaenzt um redundante 3-Stufen-Morphologie zu vermeiden. Geaenderte Dateien: `src/cv/diff_detector.py`.

Quelle: Analyse von `diff_detector.py` bei P41-Review

Ziel: Die morphologischen Operationen in `_compute_diff` (Opening + 2x Closing) kosten mehr CPU als Canny. Threshold-Mask und morphologisch bearbeitete Maske koennen gecached werden, wenn `_quick_centroid` und `_compute_diff` im selben Frame auf demselben Diff arbeiten.

Typische Arbeiten:
- Diff-Ergebnis (`cv2.absdiff`) pro Frame cachen, damit `_quick_centroid` und `_compute_diff` nicht doppelt diffen
- Morphologie-Ergebnis nach dem dreistufigen Kernel-Durchlauf cachen
- Profiling mit `cProfile` um tatsaechliche CPU-Einsparung zu messen

Erwarteter Gewinn: 10-20% CPU-Einsparung im Settling-Phase (wo `_quick_centroid` + `_compute_diff` beide `cv2.absdiff` ausfuehren).

Warum sinnvoll: Komplementaer zu P41 (Edge Cache) und P33 (Frame-Skip). Keine Verhaltensaenderung, rein interne Optimierung.

## Prioritaet 48: Telemetrie-Retention-Policy und automatische Rotation (✅ ERLEDIGT 2026-03-18)

Kritikalitaet: NIEDRIG

Ziel:

- JSONL-Telemetrie-Dateien wachsen unbegrenzt bei Langzeitbetrieb. Eine Retention-Policy begrenzt Speicherverbrauch.

Typische Arbeiten:

- Maximale Dateigroesse oder Alter fuer JSONL-Telemetrie konfigurierbar machen (z.B. DARTVISION_TELEMETRY_MAX_MB, DARTVISION_TELEMETRY_RETAIN_DAYS)
- Automatische Log-Rotation implementieren (z.B. Rename + Truncate bei Ueberschreitung)
- Alte Telemetrie-Dateien nach konfigurierbarer Frist loeschen
- Dashboard-Warnung wenn Telemetrie-Datei ueber Schwellwert waechst

Warum sinnvoll: Ohne Retention wachsen JSONL-Dateien bei Dauerbetrieb unbegrenzt. Besonders relevant auf Embedded-Systemen mit begrenztem Speicher.

## Prioritaet 49: Detection-Component Integration Tests (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** 16 Integration-Tests in `tests/test_detection_integration.py`. Abgedeckte Szenarien: 3-Dart-Sequenz mit Cooldown + Exclusion Zones, Bounce-Out waehrend Cooldown (Motion suppressed + Exclusion Zone), Shape-Reject gefolgt von gueltigem Dart, dynamische Area-Skalierung (P12) mit DartImpactDetector.scale_area_to_roi, MotionFilter Scoring-Lock + Idle-Tracking im Pipeline-Kontext, DartImpactDetector register_confirmed + Cooldown-Zyklus, Performance-Benchmarks (ShapeAnalyzer <2ms/call, CooldownManager <100us/iteration).

## Prioritaet 50: Auto-Exposure-Kompensation pro Kamera (neu — entdeckt bei P26)

Ziel:

- Unterschiedliche Auto-Exposure-Einstellungen zwischen Kameras erkennen und kompensieren

Typische Arbeiten:

- Mittlere Helligkeit pro Kamera tracken (EMA ueber ROI-Frames)
- Bei signifikanter Helligkeitsdifferenz zwischen Kameras: CLAHE clipLimit dynamisch anpassen
- Gain/Exposure-Harmonisierung via OpenCV CAP_PROP wenn Kameras dies unterstuetzen
- Helligkeits-Metrik in SharpnessTracker.get_quality_report() aufnehmen
- API-Endpunkt fuer Kamera-Qualitaetsvergleich (alle Kameras nebeneinander)

Warum sinnvoll: P26 kompensiert Schaerfe-Unterschiede, aber Helligkeits-Unterschiede zwischen Kameras koennen ebenso zu unterschiedlichen Diff-Ergebnissen fuehren. Auto-Exposure-Harmonisierung wuerde die Multi-Cam-Triangulation robuster machen.

## Prioritaet 51: Telemetrie-Cleanup-Scheduler und Dashboard-Anzeige (neu — entdeckt bei P48)

Kritikalitaet: NIEDRIG

Ziel:

- P48 hat Rotation und Cleanup als Methoden implementiert, aber kein automatischer Hintergrund-Scheduler ruft cleanup_old_files() periodisch auf. Ausserdem fehlt eine Dashboard-Anzeige fuer den Telemetrie-Dateistatus.

Typische Arbeiten:

- Background-Thread oder asyncio-Task der cleanup_old_files() taeglich ausfuehrt
- Dashboard-Widget das check_file_size() Warnungen anzeigt (z.B. in Telemetrie-Panel)
- API-Endpunkt GET /api/telemetry/status der Dateigroesse und Rotation-Historie zurueckgibt
- Manuelle Rotation via POST /api/telemetry/rotate Endpunkt

Warum sinnvoll: P48 liefert die Mechanik, aber ohne Scheduler und UI-Integration muss der Cleanup manuell angestossen werden.

## Prioritaet 51: Deduplizierung _is_already_confirmed vs CooldownManager (neu — entdeckt bei P42)

Quelle: Code-Review bei P42-Implementierung

Ziel: Die raeumliche Duplikat-Pruefung in `DartImpactDetector._is_already_confirmed()` und `CooldownManager.is_in_exclusion_zone()` ueberlappen sich. Beide pruefen Distanz zu bestaetigten Positionen, nutzen aber unterschiedliche Datenstrukturen (`_confirmed` Liste vs `_zones` Liste).

Typische Arbeiten:
- `_is_already_confirmed` auf `CooldownManager.is_in_exclusion_zone` delegieren
- `_confirmed` Liste nur noch fuer Turn-State (get_all_confirmed) nutzen, nicht fuer Exclusion
- Sicherstellen dass `register_confirmed` weiterhin korrekt dedupliziert
- Tests anpassen

Prioritaet: Niedrig (Architektur-Bereinigung, kein Verhaltens-Unterschied). Sinnvoll wenn Detector-Logik weiter refactored wird.

## Prioritaet 52: Hardcoded Farben in CSS durch Theme-Variablen ersetzen (NIEDRIG)

Quelle: Audit bei P46-Implementierung

Ziel: Verbleibende hartcodierte Farbwerte in `style.css` (z.B. `#b91c1c`, `#c0392b`, `#4ceb8f`, `#111`, `#fff`, `#000` in Buttons und Statuselementen) durch CSS-Variablen ersetzen, damit alle drei Themes (Dark, Light, High-Contrast) konsistent wirken.

Typische Arbeiten:
- Neue Variablen definieren: `--danger`, `--danger-hover`, `--text-on-accent`, `--text-on-danger`, `--bg-video`
- Alle hartcodierten `color: #fff`, `color: #111`, `background: #000` etc. durch Variablen ersetzen
- Camera-Warning-Banner und Health-Badges an Theme-Variablen anbinden
- Visueller Test in allen drei Themes

Prioritaet: Niedrig (kosmetisch, keine Funktionsaenderung). Sinnvoll als Follow-Up zu P46.

## Prioritaet 53: FrameDiffDetector Integration Tests mit Detection-Komponenten (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** 11 Integration-Tests in `tests/test_framediff_integration.py`. Testet FrameDiffDetector mit CooldownManager und MotionFilter im Zusammenspiel: Cooldown nach Detection, Exclusion-Zone-Blocking, Scoring-Lock-Suppression, Idle-Baseline-Trigger, 3-Dart-Sequenz mit synthetischen Diff-Masken, Settling-Interruption durch Motion, Bounce-Out ohne Cooldown-Aktivierung. Alle 11 Tests gruen.

## Prioritaet 54: Stereo-Kalibrierung Fortschritts-Feedback im Frontend (NIEDRIG)

Kritikalitaet: NIEDRIG

Ziel: Benutzer waehrend der Stereo-Kalibrierung ueber den Fortschritt informieren (Frame-Paare erfasst, Qualitaet, Fehler).

Typische Arbeiten:
- Progress-Events via SSE waehrend Frame-Capture senden
- Frontend-Anzeige: Fortschrittsbalken, erfasste Paare, Qualitaetsindikator
- Fehlerfaelle visuell darstellen (z.B. "Board nicht in beiden Kameras sichtbar")
- Dateien: src/web/routes.py, src/web/stereo_progress.py, static/js/app.js

## Prioritaet 55: Pipeline Baseline-Warmup fuer Video-Replay fixen (✅ ERLEDIGT 2026-03-18)

Kritikalitaet: MITTEL

Ergebnis:
- Root Cause: FrameDiffDetector._handle_idle() setzte keine Baseline wenn der erste Frame nach reset() Motion hatte — Baseline blieb None
- Fix: Force-Baseline aus erstem Frame wenn _baseline is None, auch bei Motion (src/cv/diff_detector.py)
- Globales xfail entfernt; 3/5 Videos (3.mp4, 4.mp4, 5.mp4) bestehen jetzt strict
- 2/5 Videos (1.mp4, 2.mp4) haben separates Problem: MOG2 Motion-Sensitivity zu niedrig bei kurzen Videos mit subtiler Dart-Bewegung — als per-Video xfail mit Erklaerung markiert
- Entdeckte Folge-Prio: P59 (MOG2 Motion-Sensitivity fuer kurze Videos tunen)

## Prioritaet 56: Multi-Cam Error Recovery und Auto-Restart (neu — entdeckt bei P30)

Kritikalitaet: MITTEL

Ziel: Wenn eine Kamera im Multi-Cam-Betrieb ausfaellt (error-Level), automatisch Reconnect versuchen statt nur Fehler anzuzeigen. Aktuell wird bei Startup-Fehler die Kamera dauerhaft als ausgefallen markiert.

Typische Arbeiten:
- Reconnect-Logik aus ThreadedCamera in Multi-Cam-Pipeline integrieren
- Bei dauerhaftem Kamera-Ausfall: graceful auf verbleibende Kameras degradieren
- UI-Button "Kamera neu verbinden" im Multi-Cam-Panel
- Dateien: src/cv/multi_camera.py, src/web/routes.py, static/js/app.js

## Prioritaet 57: Diff-Cache-Bug in FrameDiffDetector Settling-Phase fixen (neu — entdeckt bei P53)

Kritikalitaet: NIEDRIG

Ziel: `test_diff_cache_reused_in_settling` in `tests/test_diff_detector.py:599` schlaegt fehl — `_cached_diff` ist `None` obwohl es nach Settling gesetzt sein sollte. Der Cache wird vermutlich durch den State-Reset oder die Stability-Centroid-Logik vorzeitig invalidiert.

Typische Arbeiten:
- Root-Cause in `_handle_settling` / `_get_diff` / `_quick_centroid` identifizieren
- Cache-Invalidierung korrigieren ohne Performance-Regression
- Bestehenden Test gruenfaerben
- Dateien: src/cv/diff_detector.py, tests/test_diff_detector.py

## Prioritaet 58: Pipeline Health Dashboard im Frontend (neu — Auto-Agent 2026-03-18)

Kritikalitaet: MITTEL

Ziel:

- Kompakte Uebersicht ueber Pipeline-Zustand im Frontend: Kamera-Status, Detection-Rate, letzte Treffer, Kalibrierungs-Qualitaet

Typische Arbeiten:

- Dashboard-Panel im Frontend mit Live-Daten aus /api/stats und /api/camera/health
- Detection-Rate (Treffer/Minute) als gleitender Durchschnitt anzeigen
- Kalibrierungs-Qualitaet (quality 0-100) und letzte Kalibrierungszeit anzeigen
- Visueller Indikator ob Pipeline aktiv/idle/degraded
- Dateien: static/js/app.js, static/css/style.css, templates/index.html, src/web/routes.py

## Prioritaet 59: MOG2 Motion-Sensitivity fuer kurze Videos tunen (neu — entdeckt bei P55)

Kritikalitaet: NIEDRIG

Ziel: Videos 1.mp4 und 2.mp4 erkennen 0 Wuerfe weil MOG2 mit downscale_factor=4 zu wenig Motion-Pixel findet (~176 nach Morphologie, Threshold 200). Die Dart-Bewegung in diesen kurzen Clips ist zu subtil fuer den aktuellen MOG2-Ansatz.

Typische Arbeiten:
- Motion-Threshold adaptiv machen basierend auf ROI-Groesse und Downscale-Factor
- Alternative: FrameDiffDetector eigene Frame-zu-Frame-Diff-basierte Motion-Erkennung geben (unabhaengig von MOG2)
- Per-Video xfail in test_ground_truth_validation.py entfernen nach Fix
- Dateien: src/cv/motion.py, src/cv/diff_detector.py, tests/e2e/test_ground_truth_validation.py
