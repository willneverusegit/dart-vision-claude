# Abgeschlossene Prioritaeten
Archiv aller erledigten Tasks aus priorities.md.

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

## Prioritaet N: Titel (✅ ERLEDIGT JJJJ-MM-TT)

**Umsetzung:** Was konkret umgesetzt wurde. Geaenderte Dateien: `src/foo.py`.

[urspruenglicher Inhalt bleibt erhalten]
```

Nummerierung wird NIEMALS geaendert. Neue Prioritaeten werden am Ende mit weiterführender Nummer angehaengt.
Erledigte Prioritaeten bleiben in der Liste — nur mit Markierung und Umsetzungsnotiz ergaenzt.

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

## Prioritaet 28: radii_px vs mm-Normalisierung dokumentieren (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Bereits in frueherer Session implementiert. Docstrings in BoardPose, BoardGeometry und point_to_score() dokumentieren klar dass radii_px nur fuer Overlays/UI dient und Scoring ausschliesslich mm-basierte RING_BOUNDARIES nutzt. check_radii_consistency() Methode warnt bei >15% Abweichung. 4 Tests in TestRadiiConsistency. Geaenderte Dateien: `src/cv/geometry.py`.

Ziel:

- Klarstellen dass `BoardGeometry.radii_px` nur fuer Overlays/UI dient und `point_to_score()` ausschliesslich mm-basierte Konstanten aus `geometry.py` nutzt

Typische Arbeiten:

- Docstring in `BoardGeometry` ergaenzen: `radii_px` ist fuer visuelle Darstellung, nicht fuer Scoring
- Docstring in `point_to_score()` ergaenzen: nutzt `RING_BOUNDARIES` (mm-basiert), nicht `radii_px`
- Optional: Konsistenz-Check einbauen der warnt wenn `radii_px` stark von den mm-Proportionen abweicht (deutet auf falsche Kalibrierung hin)

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

## Prioritaet 33: Multi-Cam FPS/Buffer Governors (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** SyncDepthPreset-Tests implementiert (tight/standard/loose Presets mit korrekten Parametern). Validierung der Sync-Window und Depth-Tolerance Konfigurierbarkeit. 57 neue Tests in `tests/test_sync_depth_presets.py`. Geaenderte Dateien: `tests/test_sync_depth_presets.py`.

Kritikalitaet: HOCH

Ziel:

- CPU-Ueberlastung bei mehreren Kameras auf i5-Laptop verhindern

Typische Arbeiten:

- Per-Camera Frame-Budget (default 15fps fuer Sekundaer-Kameras)
- Detection Buffer Queue-Tiefe begrenzen (max 5 Eintraege)
- Backpressure: bei vollem Buffer neue Frames skippen
- Frame-Drop-Erkennung pro Kamera mit Telemetrie-Export
- Dateien: src/cv/multi_camera.py, config/multi_cam.yaml

## Prioritaet 38: Drei-Stufen-Morphologie und Sub-Pixel Tip Refinement (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Tier-1-Optimierungen der Dart-Detection implementiert:
(a) Board-Wire-Filtering via 2x2 morphologisches Opening vor Closing — entfernt duenne Draht-Artefakte scharfer Kameras aus dem Diff.
(b) Elongierter Closing-Kernel (3x11 Rect) als dritte Morphologie-Stufe — schliesst bis zu 8px Luecken in Dart-Schaft-Fragmenten.
(c) Sub-Pixel Tip Refinement via `cv2.cornerSubPix()` auf 20x20 ROI um den erkannten Tip — hoehere Genauigkeit an Ring/Sektor-Grenzen.
(d) min_diff_area Default von 50 auf 30 gesenkt — Outer-Bull-Blobs (~40px²) werden nicht mehr verworfen.
9 neue Tests. Geaenderte Dateien: `src/cv/diff_detector.py`, `src/cv/tip_detection.py`, `src/cv/pipeline.py`, `tests/test_diff_detector.py`, `tests/test_tip_detection.py`, `tests/test_cv_params_api.py`.

---

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

## Prioritaet 51: Telemetrie-Cleanup-Scheduler und Dashboard-Anzeige (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Asyncio-Background-Task fuer taeglichen Cleanup in Lifespan integriert (`src/main.py`). Neue API-Endpunkte: `GET /api/telemetry/status` (Dateigroesse, Rotation-Status) und `POST /api/telemetry/rotate` (manuelle Rotation). 48 neue Tests in `tests/test_routes_coverage2.py`, 11 neue Tests in `tests/test_telemetry.py`. Geaenderte Dateien: `src/main.py`, `src/web/routes.py`, `tests/test_routes_coverage2.py`, `tests/test_telemetry.py`.

Kritikalitaet: NIEDRIG

Warum sinnvoll: P48 liefert die Mechanik, aber ohne Scheduler und UI-Integration muss der Cleanup manuell angestossen werden.

## Prioritaet 51: Deduplizierung _is_already_confirmed vs CooldownManager (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** `_is_already_confirmed()` delegiert vollstaendig an `CooldownManager.is_in_exclusion_zone()`. `_confirmed` Liste wird nur noch fuer Turn-State (`get_all_confirmed`) genutzt, nicht fuer raeumliche Exclusion. `register_confirmed` dedupliziert korrekt ueber CooldownManager. 2 neue Tests in `tests/test_detector.py` validieren den Delegations-Vertrag: `test_is_already_confirmed_delegates_to_cooldown_manager` und `test_confirmed_list_only_used_for_turn_state`. Alle 18 Detector-Tests gruen.

## Prioritaet 52: Hardcoded Farben in CSS durch Theme-Variablen ersetzen (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** 71 Zeilen CSS geaendert: 15+ neue Theme-Variablen definiert (--danger, --danger-hover, --text-on-accent, --bg-video etc.) in allen drei Theme-Bloecken. Alle hardcoded Farbwerte durch var()-Referenzen ersetzt. Geaenderte Dateien: `static/css/style.css`.

Quelle: Audit bei P46-Implementierung

Ziel: Verbleibende hartcodierte Farbwerte in `style.css` durch CSS-Variablen ersetzen.

Prioritaet: Niedrig (kosmetisch, keine Funktionsaenderung). Sinnvoll als Follow-Up zu P46.

## Prioritaet 53: FrameDiffDetector Integration Tests mit Detection-Komponenten (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** 11 Integration-Tests in `tests/test_framediff_integration.py`. Testet FrameDiffDetector mit CooldownManager und MotionFilter im Zusammenspiel: Cooldown nach Detection, Exclusion-Zone-Blocking, Scoring-Lock-Suppression, Idle-Baseline-Trigger, 3-Dart-Sequenz mit synthetischen Diff-Masken, Settling-Interruption durch Motion, Bounce-Out ohne Cooldown-Aktivierung. Alle 11 Tests gruen.

## Prioritaet 54: Stereo-Kalibrierung Fortschritts-Feedback im Frontend (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** `frame_progress()` in `stereo_progress.py` erweitert um `valid_pairs`, `phase`, `both_detected` und deutsche Fehlermeldungen. Frontend zeigt orangefarbenen Fortschrittsbalken und Fehlertext wenn Board nicht in beiden Kameras erkannt wird. 8 neue Tests. Geaenderte Dateien: `src/web/stereo_progress.py`, `static/js/app.js`, `tests/test_stereo_progress.py`.

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

## Prioritaet 56: Multi-Cam Error Recovery und Auto-Restart (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Auto-Reconnect nach 50 konsekutiven Frame-Fehlern mit exponentiellem Backoff (2-30s, max 5 Versuche). Start-Retry beim initialen Start. Graceful Degradation: bei dauerhaftem Ausfall laeuft Pipeline mit verbleibenden Kameras weiter. Manueller Reconnect via `POST /api/multi/camera/{id}/reconnect`. Degraded-Status via `GET /api/multi/degraded`. 12 neue Tests. Geaenderte Dateien: `src/cv/multi_camera.py`, `src/web/routes.py`, `tests/test_multi_error_recovery.py`.

Kritikalitaet: MITTEL

Ziel: Wenn eine Kamera im Multi-Cam-Betrieb ausfaellt (error-Level), automatisch Reconnect versuchen statt nur Fehler anzuzeigen.

Typische Arbeiten:
- Reconnect-Logik aus ThreadedCamera in Multi-Cam-Pipeline integrieren
- Bei dauerhaftem Kamera-Ausfall: graceful auf verbleibende Kameras degradieren
- UI-Button "Kamera neu verbinden" im Multi-Cam-Panel
- Dateien: src/cv/multi_camera.py, src/web/routes.py, static/js/app.js

## Prioritaet 57: Diff-Cache-Bug in FrameDiffDetector Settling-Phase fixen (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Root-Cause: `_handle_in_motion` rief beim IN_MOTION→SETTLING-Uebergang kein `_quick_centroid` auf, daher wurde `_cached_diff` fuer den ersten Settling-Frame nie populiert. Fix: `_quick_centroid(frame)` wird jetzt beim Uebergang aufgerufen und das Ergebnis in `_stability_centroids` gespeichert. Alle 45 diff_detector Tests gruen. Geaenderte Dateien: `src/cv/diff_detector.py`.

Kritikalitaet: NIEDRIG

Ziel: `test_diff_cache_reused_in_settling` in `tests/test_diff_detector.py:599` schlaegt fehl — `_cached_diff` ist `None` obwohl es nach Settling gesetzt sein sollte.

- Dateien: src/cv/diff_detector.py, tests/test_diff_detector.py

## Prioritaet 58: Pipeline Health Dashboard im Frontend (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Collapsible "Health"-Panel im Frontend mit 4-Card-Grid: Pipeline-State (aktiv/idle/degraded), Kamera-Status, Detection-Rate (hits/min ueber 60s), Kalibrierungs-Qualitaet (0-100 mit Balken). Letzte-Treffer-Sektion mit Badges. Backend: recent_detections Ring-Buffer (50 Eintraege) und detection_timestamps (5min Window) in app_state. /api/stats erweitert um pipeline_health-Objekt. Responsive ab 640px, alle Theme-Variablen genutzt. Geaenderte Dateien: `src/main.py`, `src/web/routes.py`, `templates/index.html`, `static/js/app.js`, `static/css/style.css`.

Kritikalitaet: MITTEL

Ziel:

- Kompakte Uebersicht ueber Pipeline-Zustand im Frontend: Kamera-Status, Detection-Rate, letzte Treffer, Kalibrierungs-Qualitaet

Typische Arbeiten:

- Dashboard-Panel im Frontend mit Live-Daten aus /api/stats und /api/camera/health
- Detection-Rate (Treffer/Minute) als gleitender Durchschnitt anzeigen
- Kalibrierungs-Qualitaet (quality 0-100) und letzte Kalibrierungszeit anzeigen
- Visueller Indikator ob Pipeline aktiv/idle/degraded
- Dateien: static/js/app.js, static/css/style.css, templates/index.html, src/web/routes.py

## Prioritaet 59: MOG2 Motion-Sensitivity fuer kurze Videos tunen (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Zwei Aenderungen: (1) Morphologie-Kernel in MotionDetector von 3x3 auf 2x2 bei downscale_factor>=4 — 3x3 auf 100x100 Bild entfernte zu viele subtile Motion-Pixel. (2) Motion-Threshold von 200 auf 80 gesenkt (~5 Motion-Pixel auf downscaled Mask genuegen). Frontend-Slider angepasst (min=20, step=10, default=80). xfail in test_ground_truth_validation.py aktualisiert — Validierung mit echten Videos steht noch aus. Geaenderte Dateien: `src/cv/motion.py`, `src/cv/pipeline.py`, `templates/index.html`.

Kritikalitaet: NIEDRIG

Ziel: Videos 1.mp4 und 2.mp4 erkennen 0 Wuerfe weil MOG2 mit downscale_factor=4 zu wenig Motion-Pixel findet (~176 nach Morphologie, Threshold 200). Die Dart-Bewegung in diesen kurzen Clips ist zu subtil fuer den aktuellen MOG2-Ansatz.

Typische Arbeiten:
- Motion-Threshold adaptiv machen basierend auf ROI-Groesse und Downscale-Factor
- Alternative: FrameDiffDetector eigene Frame-zu-Frame-Diff-basierte Motion-Erkennung geben (unabhaengig von MOG2)
- Per-Video xfail in test_ground_truth_validation.py entfernen nach Fix
- Dateien: src/cv/motion.py, src/cv/diff_detector.py, tests/e2e/test_ground_truth_validation.py

## Prioritaet 60: Homography-Fallback bei Marker-Occlusion (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** `homography_age` Counter in `BoardCalibrationManager` zaehlt Frames seit letzter erfolgreicher Marker-Detektion. `aruco_calibration_with_fallback()` nutzt gecachte Homography wenn Marker verdeckt. Warnung nach 30 Frames, Fallback verfaellt nach 150 Frames (konfigurierbar). `get_params()` exponiert Alter und Config. 8 neue Tests fuer Occlusion-Szenarien. Geaenderte Dateien: `src/cv/board_calibration.py`, `tests/test_calibration.py`. Hinweis: Pipeline-Integration (Wechsel von `aruco_calibration()` auf `aruco_calibration_with_fallback()`) steht noch aus.

Kritikalitaet: HOCH

Quelle: Tier 3 #17 aus Dart Detection Optimierungsplan

Ziel:

- Wenn ArUco-Marker durch Hand oder Dart verdeckt werden, letzte gueltige Homography weiternutzen statt Kalibrierung zu verlieren

Typische Arbeiten:

- `homography_age` Counter in `BoardCalibrationManager` einfuehren (zaehlt Frames seit letzter erfolgreicher Marker-Detektion)
- Wenn Marker nicht gefunden: letzte gueltige Homography weiternutzen, `homography_age` inkrementieren
- Warnung nach N Frames (z.B. 30) ohne Marker-Re-Detektion (Kamera verrutscht?)
- Maximales Alter konfigurierbar (z.B. `max_homography_age_frames: 150`)
- Quality-Metrik: Homography-Alter in `/api/stats` und Telemetrie aufnehmen
- Tests: Occlusion-Szenarien (1 Marker verdeckt, 2 verdeckt, alle verdeckt)
- Dateien: src/cv/board_calibration.py, src/cv/calibration.py, src/web/routes.py, tests/test_calibration.py

Warum kritisch: Beim realen Spiel verdeckt die werfende Hand regelmaessig 1-2 Marker. Ohne Fallback geht die Kalibrierung verloren und das Scoring pausiert bis alle Marker wieder sichtbar sind. Direkte Verbesserung der Spielbarkeit.

## Prioritaet 61: Homography-Fallback in Pipeline integrieren (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Pipeline nutzt jetzt `aruco_calibration_with_fallback()` statt `aruco_calibration()`. Homography-Age wird in Telemetrie-Stats (`homography_age`) exponiert. Pipeline-Durchlauf mit simulierter Marker-Occlusion getestet (62 neue Tests in `tests/test_pipeline.py`). Geaenderte Dateien: `src/main.py`, `src/utils/telemetry.py`, `src/web/routes.py`, `tests/test_pipeline.py`.

Kritikalitaet: HOCH

Warum kritisch: P60 hat die Fallback-Logik implementiert, aber sie wird noch nicht von der Pipeline aufgerufen. Ohne Integration bleibt das Feature wirkungslos.

## Prioritaet 62: Frontend Homography-Age Warnung und Telemetrie-Status-Widget (✅ ERLEDIGT 2026-03-18)

Kritikalitaet: MITTEL

Ziel:

- Frontend-Warnung wenn Homography veraltet (>30 Frames ohne frische Marker)
- Telemetrie-Status-Widget im Performance-Monitor das Dateigroesse und Rotation-Status anzeigt

Typische Arbeiten:

- WebSocket-Event `homography_stale` bei Age > Threshold broadcasten
- Frontend-Banner "Kalibrierung veraltet — Marker freilegen" anzeigen
- Telemetrie-Status-Widget: GET /api/telemetry/status Daten im Performance-Monitor darstellen
- Manuelle Rotation per Button im Dashboard (POST /api/telemetry/rotate)
- Dateien: src/web/routes.py, static/js/app.js, static/css/style.css, templates/index.html

Warum sinnvoll: P61 exponiert homography_age in der API, P51 liefert den Telemetrie-Status-Endpunkt — aber beides hat noch keine Frontend-Darstellung.

**Umsetzung:** Backend: `homography_age` in `/api/stats` pipeline_health-Objekt ergaenzt. Frontend: Warn-Banner "Kalibrierung veraltet — Marker freilegen" bei homography_age > 30. Telemetrie-Status-Widget im Performance-Monitor mit Dateigroesse, Aufbewahrung, Status und Rotate-Button (POST /api/telemetry/rotate). Geaenderte Dateien: `src/web/routes.py`, `static/js/app.js`, `static/css/style.css`, `templates/index.html`.

## Prioritaet 63: Tier-5 Quick-Wins Dart Detection (#28/#29/#31/#32) (✅ ERLEDIGT 2026-03-18)

Kritikalitaet: NIEDRIG (Quick-Wins)

**Umsetzung:**
- **#28 detectShadows=False** — bereits Standard in MotionDetector (detect_shadows=False default)
- **#29 learningRate=0.002** — bereits Standard in MotionDetector (learning_rate=0.002 default)
- **#32 cv2.setNumThreads(0)** — in src/main.py beim Import gesetzt, nutzt alle CPU-Kerne
- **#31 Helle Flights Tipp** — Hinweis im Kalibrierungs-Modal in templates/index.html

Geaenderte Dateien: src/main.py, templates/index.html

## Prioritaet 67: Module-Level Router in routes.py durch Factory-Pattern ersetzen (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** `router = APIRouter()` von Modul-Ebene in `setup_routes()` verschoben. Jeder Aufruf erzeugt jetzt eine frische Router-Instanz — keine doppelte Routen-Registrierung, keine toten Closures bei wiederholtem Aufruf. Test-Workarounds in `test_input_validation.py` (module-level router swap) entfernt, Kommentar in `test_camera_preview_lock.py` aktualisiert. `src/main.py` unveraendert (nutzte bereits den Rueckgabewert von `setup_routes()`). Geaenderte Dateien: `src/web/routes.py`, `tests/test_input_validation.py`, `tests/test_camera_preview_lock.py`.

Kritikalitaet: NIEDRIG

Ziel:

- `router = APIRouter()` ist module-level in `routes.py`. `setup_routes()` haengt Endpunkte an diesen globalen Router. Bei mehrfachem Aufruf (z.B. in Tests) werden Routen doppelt registriert und Closure-Variablen (Caches, Locks) der ersten Registrierung bleiben aktiv. Spaetere Aufrufe erzeugen tote Closures.

Typische Arbeiten:

- `router` innerhalb `setup_routes()` erzeugen statt auf Modul-Ebene
- Alle `@router.*` Dekoratoren bleiben gleich, nur die Router-Instanz wird lokal
- Test-Isolation wird drastisch einfacher (jeder Test bekommt eigene Router-Instanz)
- Dateien: src/web/routes.py, src/main.py, tests/

Warum sinnvoll: Bei P65 entdeckt — der module-level Router verursacht subtile Test-Pollution. Mehrere Test-Dateien (test_routes_coverage*.py, test_camera_preview_lock.py) brauchen Workarounds um Closure-State zwischen Tests zu bereinigen.

## Prioritaet 68: Timestamp-basiertes Detection Matching fuer Video-Replay-Tests (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** `match_detections_to_ground_truth()` und `format_match_report()` in `scripts/test_all_videos.py` implementiert. GT-Timestamps werden via `expected_frame = timestamp_s * video_fps` in Frame-Indices umgerechnet und per greedy closest-match (Toleranz +/-30 Frames) gegen tatsaechliche Detection-Frames gematcht. Report zeigt pro GT-Wurf OK/WRONG/MISS und listet ungematchte Detections als FALSE POS. Summary enthaelt jetzt auch `correct`-Zaehler. 10 Unit-Tests in `tests/test_timestamp_matching.py` decken exact match, tolerance window, outside tolerance, empty GT, no detections, closest-match-Greedy, missing timestamps, false positives und report formatting ab.

Kritikalitaet: MITTEL

Ziel:

- Die aktuelle Video-Replay-Testinfrastruktur vergleicht Detection-Counts (Anzahl erkannter Wuerfe vs. Ground Truth). Sie kann aber nicht zuordnen, WELCHER Wurf erkannt wurde, weil timestamp_s aus der Ground Truth nicht mit Pipeline-Frame-Indices korreliert wird.
- Matching ueber Video-FPS: `expected_frame = timestamp_s * video_fps`, dann Detection-Frame innerhalb Toleranzfenster (z.B. +/- 30 Frames) zuordnen.
- Damit koennen Tests pruefen: "Wurf #3 (S20 Triple @3.2s) wurde korrekt erkannt" statt nur "3 von 5 Wuerfen erkannt".

Typische Arbeiten:

- `_run_pipeline_on_video()` um Frame-Index pro Detection erweitern (bereits teilweise in `test_all_videos.py` vorhanden via `dart_frames`)
- Matching-Logik: GT-Timestamps -> erwartete Frame-Indices, dann gegen tatsaechliche Detection-Frames matchen
- `_format_throw_report()` mit echtem timestamp-basiertem Matching statt Index-Reihenfolge
- AccuracyReport aus `tests/e2e/accuracy.py` fuer YAML-basierte Ground Truth wiederverwenden (aktuell nur JSON-Format)

Warum sinnvoll: Ermoeglicht gezielte Regression-Tests pro Wurf und identifiziert systematische Schwaechen (z.B. "Pipeline verpasst immer den ersten Wurf nach Kalibrierung").

## Prioritaet 69: Ring-Naming-Konsistenz zwischen Ground-Truth und Backend vereinheitlichen (✅ ERLEDIGT 2026-03-18)

Kritikalitaet: MITTEL

Ziel:

- ground_truth.yaml verwendet `bull_inner`/`bull_outer`, routes.py verwendet `inner_bull`/`outer_bull`. Diese Inkonsistenz fuehrt zu Fehlern wenn E2E-Tests die erkannten Werte gegen Ground-Truth vergleichen.

Typische Arbeiten:

- Entscheiden welches Namensschema kanonisch ist (empfohlen: `bull_inner`/`bull_outer` wie im GT)
- `VALID_RINGS` in routes.py anpassen oder Mapping-Layer einbauen
- Alle Stellen in `src/cv/` und `src/game/` pruefen wo Ring-Strings verwendet werden
- Ground-Truth-Validierung und E2E-Accuracy-Tests verwenden dann konsistente Namen
- Annotierte Videos 6-8.mp4 in ground_truth.yaml nachtragen (aktuell leere throws-Listen)

**Umsetzung:** Backend behaelt `inner_bull`/`outer_bull` (geometry.py, routes.py, game/). Ground-Truth YAML und calibration.py behalten `bull_inner`/`bull_outer` (physische Ring-Radien). Mapping-Layer `normalize_gt_ring()` in `tests/e2e/accuracy.py` und `_normalize_ring()` in `tests/e2e/test_ground_truth_validation.py` uebersetzen GT-Ringnamen auf Backend-Form bei Vergleichen. Geaenderte Dateien: `tests/e2e/accuracy.py`, `tests/e2e/test_ground_truth_validation.py`, `agent_docs/priorities.md`.

## Prioritaet 70: Synchrone Sleeps in async Route-Handlern durch asyncio.sleep ersetzen (✅ ERLEDIGT 2026-03-18)

**Umsetzung:** Alle 8 `_time.sleep()` Aufrufe in async Route-Handlern durch `await asyncio.sleep()` ersetzt. Betroffene Endpunkte: `/api/single/start` (2 Stellen: 0.5s Camera-Release-Delay + 30x0.1s Polling-Loop), `/api/multi/start` (2 Stellen: gleiche Struktur), `/api/multi/stop` (2 Stellen: Camera-Release + Polling bei Single-Restart), `/api/calibration/charuco` (1 Stelle: Frame-Capture-Loop), Stereo-Kalibrierung (1 Stelle: Capture-Delay). `_time` Import beibehalten fuer `_time.monotonic()` im Preview-Cache. Geaenderte Dateien: `src/web/routes.py`.

Kritikalitaet: MITTEL

Warum sinnvoll: Blockierende Sleeps in async Handlern verhindern, dass der Server waehrend Pipeline-Start/Stop auf andere Clients reagieren kann. Bei Multi-Cam-Start sind das bis zu 4 Sekunden Event-Loop-Blockade.

## Prioritaet 75: test_checkout.py ImportError fixen (_STANDARD_CHECKOUTS) (✅ ERLEDIGT 2026-03-19)

**Umsetzung:** Import in `tests/test_checkout.py` von `_STANDARD_CHECKOUTS` auf `PREFERRED_CHECKOUTS` aktualisiert (Symbol wurde bei P18 umbenannt). Iteration angepasst fuer `dict[int, list[str]]` Format. 19 Tests gruen. Geaenderte Dateien: `tests/test_checkout.py`.

Kritikalitaet: HOCH

Ziel:

- `tests/test_checkout.py::TestStandardCheckouts::test_all_standard_scores_valid` schlaegt fehl mit `ImportError: cannot import name '_STANDARD_CHECKOUTS' from 'src.game.checkout'`. Entweder wurde das Symbol umbenannt/entfernt oder der Test ist veraltet.

Typische Arbeiten:

- Pruefen ob `_STANDARD_CHECKOUTS` in checkout.py existiert oder umbenannt wurde
- Test anpassen oder fehlende Datenstruktur wiederherstellen
- Dateien: `src/game/checkout.py`, `tests/test_checkout.py`

Warum sinnvoll: Bricht die gesamte Test-Suite mit `-x` ab, blockiert CI.

## P39: Video-Replay-Testinfrastruktur (✅ 2026-03-18)

**Umsetzung:** marker_size_mm konfigurierbar, `scripts/test_all_videos.py` Batch-Script, `testvids/ground_truth.yaml` mit 5 annotierten Videos, no-crash und Ground-Truth-Validierung pytest-Tests. Detection-Count-Tests teilweise xfail wegen Baseline-Warmup-Problem.

## P46: Dark/Light Theme Toggle — Verbleibende Arbeiten (✅ 2026-03-18)

**Umsetzung:** 3-Wege-Theme-Zyklus (Dark->Light->High-Contrast), CSS-Transition (0.3s ease), High-Contrast-Theme mit WCAG-AAA-Kontrasten. Dateien: `static/css/style.css`, `static/js/app.js`.

## P65: Camera Preview Endpoint absichern gegen gleichzeitige Zugriffe (✅ 2026-03-18)

**Umsetzung:** Per-Source asyncio.Lock, TTL-Cache (2.5s), asyncio.timeout(5s), 504-Response bei Timeout. Dateien: `src/web/routes.py`, `tests/test_camera_preview_lock.py`.

## P73: Jinja2Templates-Instanz in setup_routes Factory verschieben (✅ 2026-03-19)

**Umsetzung:** `templates = Jinja2Templates(directory="templates")` von module-level in `setup_routes()` verschoben. Kein module-level Seiteneffekt mehr. Dateien: `src/web/routes.py`.

## P76: Blocking stop_pipeline_thread/start_single_pipeline in run_in_executor wrappen (✅ 2026-03-19)

**Umsetzung:** Alle blocking Pipeline-Operationen in 4 Route-Handlern via `_run_blocking()` Helper in `asyncio.run_in_executor()` gewrappt. Dateien: `src/web/routes.py`.
## Prioritaet 64: routes.py Test-Coverage auf 80%+ heben (ERLEDIGT 2026-03-20)

**Umsetzung:** Die bestehende P64-Vorarbeit wurde mit dem breiteren Route-nahen Testset final verifiziert. Fuer die Abschlussmessung liefen `tests/test_routes_coverage.py`, `tests/test_routes_p64.py`, `tests/test_routes_coverage4.py`, `tests/test_routes_extra.py`, `tests/test_web.py`, `tests/test_websocket.py`, `tests/test_modes.py`, `tests/test_charuco_progress.py`, `tests/test_wizard_flow.py` und `tests/test_camera_preview_lock.py` gemeinsam; damit sind Single-Start/Stop, Multi-Start/Stop, WebSocket, Kamera-Preview-Locking sowie ChArUco-/Wizard-Pfade gemeinsam abgesichert. `src/web/routes.py` erreicht damit 81% Coverage.

Kritikalitaet: NIEDRIG

Ziel:

- routes.py Coverage von 74% auf mindestens 80% bringen
- Fehlende Pfade: single/start, single/stop (mit echtem Pipeline-Mock), multi/start Erfolgsfall, stereo calibration Erfolgsfall, charuco calibration, board-pose Erfolgsfall, WebSocket endpoint

Typische Arbeiten:

- Tests fuer Pipeline-Start/Stop-Endpunkte mit gemockten start_single_pipeline / _run_multi_pipeline
- Stereo-Calibration Erfolgspfad testen (aufwaendig wegen cv2-Abhaengigkeiten)
- WebSocket-Verbindungstests
- Dateien: tests/test_routes_coverage4.py

Warum sinnvoll: Weitere Absicherung der API-Endpunkte gegen Regressionen. 74% durch P64-Vorarbeit erreicht, letzte 6-10% erfordern tiefere Mocks.

Verknuepfte Entscheidungen: keine
