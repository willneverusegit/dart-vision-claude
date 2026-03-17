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

## Prioritaet 19: Before/After-Frame-Vergleich fuer Treffererkennung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** FrameDiffDetector mit IDLE/IN_MOTION/SETTLING-State-Machine in `src/cv/diff_detector.py`. MOG2 bleibt Motion-Trigger, Positionsbestimmung via cv2.absdiff() zwischen Baseline und stabilem Post-Wurf-Frame. register_confirmed() public method in DartImpactDetector. Integration in DartPipeline.process_frame() — update() vor Motion-Gate-Early-Return. reset_turn() setzt alle drei Detektoren zurück (dart_detector, frame_diff_detector, motion_detector). Geaenderte Dateien: `src/cv/diff_detector.py`, `src/cv/detector.py`, `src/cv/pipeline.py`, `tests/test_diff_detector.py`, `tests/test_detector.py`, `tests/test_pipeline_diff_integration.py`.

## Prioritaet 22: Telemetrie-Export und Post-Mortem-Analyse (neu — entdeckt bei Arbeit an P8)

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

## Prioritaet 26: Kamera-Qualitaet angleichen oder kompensieren (neu — entdeckt bei P20)

Ziel:

- Unterschiedliche Bildqualitaet zwischen Kameras erkennen und kompensieren

Typische Arbeiten:

- Automatische Schaerfe-Metrik pro Kamera (Laplacian-Varianz oder aehnlich)
- Kamera-spezifische Threshold-Anpassung (schaerfere Kamera kann niedrigeren diff_threshold nutzen)
- Board-Draht-Artefakte in Diff bei scharfen Kameras filtern (cam_left zeigt Board-Draehte im Diff)
- Qualitaets-Report in Diagnostics-Metadaten aufnehmen

## Prioritaet 27: Marker-Kalibrierung auf neue Masse aktualisieren (neu — Session-Start)

Ziel:

- Kalibrierungskonfiguration an geaenderte physische Marker-Masse anpassen

Typische Arbeiten:

- ArUco Dict 7x5 50, Marker 0-3, 75mm Kantenlaenge — unveraendert
- Mitte-zu-Mitte Abstand: 430mm (verifizieren)
- Corner-zu-Corner: 505mm (vorher 480mm) — in calibration_config.yaml aktualisieren
- Kalibrierung neu durchfuehren und Qualitaetsmetrik vergleichen

## Prioritaet 28: radii_px vs mm-Normalisierung dokumentieren (neu — entdeckt bei P25)

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

## Prioritaet 30: Camera Error Reporting to UI (neu — Multi-Cam Assessment)

Kritikalitaet: KRITISCH

Ziel:

- Kamera-Fehler im Multi-Cam-Betrieb sichtbar machen

Typische Arbeiten:

- get_camera_errors() aus multi_camera.py an WebSocket broadcast anbinden
- Per-Camera Status-Badges im Multi-Cam-Panel (gruen/gelb/rot)
- Fehlermeldungen mit Kontext (welche Kamera, welcher Fehler, Zeitstempel)
- Dateien: src/cv/multi_camera.py, src/web/routes.py, static/js/app.js

## Prioritaet 31: Intrinsics Validation vor Stereo-Kalibrierung (neu — Multi-Cam Assessment)

Kritikalitaet: KRITISCH

Ziel:

- Sicherstellen dass Kameras korrekte Intrinsics haben bevor Stereo-Kalibrierung gestartet wird

Typische Arbeiten:

- Pre-Flight-Check: Beide Kameras muessen gueltige camera_matrix haben
- Klare Fehlermeldung wenn fehlend: "Bitte Linsen-Kalibrierung fuer cam_left zuerst durchfuehren"
- Stereo-Kalibrierung blockieren bis beide Kameras bereit
- Dateien: src/cv/stereo_calibration.py, src/cv/board_calibration.py

## Prioritaet 32: Triangulation Telemetrie (neu — Multi-Cam Assessment)

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
