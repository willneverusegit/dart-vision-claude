# Priorities

Diese Liste beschreibt die empfohlene Weiterentwicklung aus Sicht des Projektstands 2026-03-19.
Erledigte Prioritaeten sind in `priorities_done.md` archiviert.

## Arbeitsregel fuer Agents

Wenn der User nur allgemein nach "weiterentwickeln" fragt und keine andere Richtung vorgibt, beginne oben in der Liste und arbeite nach unten.

## Format fuer erledigte Prioritaeten

```
## Prioritaet N: Titel (✅ ERLEDIGT JJJJ-MM-TT)

**Umsetzung:** Was konkret umgesetzt wurde. Geaenderte Dateien: `src/foo.py`.

[urspruenglicher Inhalt bleibt erhalten]
```

Nummerierung wird NIEMALS geaendert. Neue Prioritaeten werden am Ende mit weiterführender Nummer angehaengt.
Erledigte Prioritaeten werden nach `priorities_done.md` verschoben.

## Prioritaet 9: Multi-Cam UX weiter verbessern (NIEDRIG — teilweise erledigt)

**Teilfortschritt 2026-03-18:** Kamera-Vorschau-Thumbnails im Multi-Cam-Setup-Modal implementiert. Neuer Endpunkt `GET /api/camera/preview/{source}` liefert einzelnes JPEG-Bild von beliebiger Kamera-Quelle. Jede Kamera-Zeile zeigt 200x150px Vorschau mit Refresh-Button. Funktioniert unabhaengig von laufender Pipeline. Geaenderte Dateien: `src/web/routes.py`, `templates/index.html`, `static/js/app.js`, `static/css/style.css`.

**Teilfortschritt 2026-03-19:** Multi-Cam-Kalibriermodus repariert. Ursache war, dass fast alle Kalibrier-Endpunkte nur `app_state["pipeline"]` verwendeten, obwohl im Multi-Cam-Betrieb die aktiven Live-Pipelines unter `app_state["multi_pipeline"]` liegen. `src/web/routes.py` loest jetzt fuer Kalibrier-Frames, Status, Board-Alignment, Lens-Setup, ROI/Overlay, Ring-Check und optischen Mittelpunkt die gewaehlte Sub-Pipeline pro `camera_id` auf. Das Kalibrier-Modal erhielt in `templates/index.html` und `static/js/app.js` eine explizite Kamera-Auswahl, zielbezogene Status-/Fehlertexte und per-Kamera-Requests. Regression: `tests/test_routes_coverage4.py` um 5 Multi-Cam-Kalibrier-Tests erweitert; zusaetzlich 20 fokussierte Kalibrier-/Stereo-Tests und 163 Route-Coverage-Tests gruen. Geaenderte Dateien: `src/web/routes.py`, `static/js/app.js`, `templates/index.html`, `static/css/style.css`, `tests/test_routes_coverage4.py`.

**Teilfortschritt 2026-03-19:** Multi-Cam-Kalibrierdialog weiter gefuehrt. `static/js/app.js` nutzt jetzt den vorhandenen Multi-Status fuer klickbare Per-Kamera-Karten, eine dynamische Empfehlung der naechsten Aktion, visuelles Highlight des empfohlenen Buttons und einen "Weiter"-CTA nach erfolgreichem Schritt. Der CTA startet den empfohlenen Standardpfad jetzt direkt: gleiche Kamera fuehrt unmittelbar in Lens Setup bzw. Board-ArUco, Kamerawechsel schaltet zuerst auf die Zielkamera um und startet dann den naechsten Schritt. `templates/index.html` erhielt Guide- und Next-Step-Panels, `static/css/style.css` die dazugehoerigen Karten-/Guide-Stile. Verifikation: `node -c static/js/app.js`, `python -m pytest tests/test_web.py tests/test_routes_extra.py tests/test_websocket.py tests/test_stereo_wizard_api.py -q`, `python -m pytest tests/test_routes_coverage4.py::TestCalibrationEndpointsWithMultiCam -q`. Geaenderte Dateien: `static/js/app.js`, `templates/index.html`, `static/css/style.css`.

**Teilfortschritt 2026-03-19:** ChArUco-Kalibrierung gegen das reale Mehrkamera-Problem gehaertet. `src/cv/stereo_calibration.py` erkennt jetzt konkrete Layouts `7x5_40x20`, `7x5_40x28`, `5x7_40x20`, `5x7_40x28`; `preset="auto"` probiert alle Kandidaten und bewertet nach interpolierten Ecken. `src/cv/camera_calibration.py` waehlt vor Lens-Kalibrierung das konkrete Layout mit den meisten nutzbaren Frames und schreibt dieses Layout nach erfolgreicher Kalibrierung zurueck in die Kamera-Config. `CharucoFrameCollector`, `/api/calibration/charuco-progress/{camera_id}`, `/video/feed`, `/video/feed/{camera_id}` und `/api/calibration/stereo` unterscheiden jetzt sauber zwischen Rohmarkern und wirklich interpolierbaren ChArUco-Ecken; Stereo akzeptiert in `auto` nur Paare mit identisch aufgeloestem Layout in beiden Kameras. Die UI nutzt `auto` jetzt als Standard, startet im normalen Lens-Pfad Guided Capture statt sofortiger 3-Sekunden-Kalibrierung und zeigt das aufgeloeste Layout in Status/Ergebnis an. Das Print-Pack korrigiert die veraltete Marker-Angabe von `410 mm` auf `430 mm`. Verifikation: `python -m pytest tests/test_calibration.py tests/test_charuco_progress.py tests/test_stereo_calibration.py tests/test_stereo_wizard_api.py tests/test_wizard_flow.py -q`, `python -m pytest tests/test_web.py tests/test_routes_extra.py tests/test_routes_coverage4.py -q`, lokale 1080p-Clips `testvids/1.mp4` und `testvids/2.mp4` (konkretes `7x5_40x20` liefert 14 Rohmarker/0 ChArUco-Ecken, `auto` loest zu `5x7_40x20` mit 18 Ecken auf). Geaenderte Dateien: `src/cv/stereo_calibration.py`, `src/cv/camera_calibration.py`, `src/web/routes.py`, `static/js/app.js`, `templates/index.html`, `tests/test_stereo_calibration.py`, `tests/test_calibration.py`, `tests/test_charuco_progress.py`, `tests/test_routes_extra.py`, `tests/test_routes_coverage4.py`, `tests/test_web.py`, `tests/test_wizard_flow.py`, `scripts/generate_calibration_prints.py`, `output/pdf/calibration_print_notes.md`.

**Teilfortschritt 2026-03-20:** Live-Check des Multi-Cam-Kalibrierflows gegen `http://127.0.0.1:8000/` durchgefuehrt. Der Browser zeigte den aktiven Guided-Capture-Pfad fuer `cam_left`, inklusive ChArUco-Progress-API und globalem Fortschrittsbalken. Dabei fiel auf, dass der Kalibrierstatus bei laufender kamera-spezifischer Guided-Capture-/Wizard-Session auf `Single-Cam` zurueckfallen konnte, sobald das Frontend `multiCamRunning` temporaer verlor. `static/js/app.js` haelt den Kamera-Kontext jetzt ueber `_charucoPollingContext` bzw. `_wizardState.currentCamera`, sodass Status-/Folge-Requests in laufenden Sessions weiter auf der gestarteten Kamera bleiben. Verifikation: Live-DOM-/Network-Check in Playwright, `node -c static/js/app.js`, `python -m pytest tests/test_wizard_flow.py tests/test_stereo_wizard_api.py -q`. Geaenderte Dateien: `static/js/app.js`.

Verknuepfte Weaknesses: keine

Verknuepfte Entscheidungen: 2026-03-18-multi-cam-9-phase-plan

Ziel:

- Multi-Cam-Setup fuer Nicht-Experten bedienbar machen

Verbleibende Arbeiten:

- Drag-and-Drop Kamera-Anordnung (bewusst ausgelassen — kein Mehrwert erkannt)

Erledigt (2026-03-19, Branch `claude/stupefied-hellman`):

- Board-Pose: visuelles Feedback (Marker-Ecken + Scoring-Ringe + 3D-Achsen im Ergebnisbild)
- Setup-Wizard: Auto-Advance mit Stepper (Lens→Board→Pose→Stereo), Result-Preview nach jedem Schritt, Auto-Pose-Berechnung
- ChArUco-Guidance: Anleitung, Live-Fortschrittsbalken, Qualitaets-Tipps, Auto-Frame-Collection im MJPEG-Feed
- result_image + quality_info in allen 4 Kalibrier-Endpoints (ArUco, Lens, Board-Pose, Stereo)
- Neue Dateien: `src/cv/calibration_overlay.py`, `tests/test_calibration_overlay.py`, `tests/test_charuco_progress.py`, `tests/test_wizard_flow.py`

## Prioritaet 11: E2E-Tests mit echten Videoclips (neu — entdeckt bei Arbeit an P1)

Ziel:

- synthetische E2E-Tests durch Tests mit echten Kamera-Aufnahmen ergaenzen

Typische Arbeiten:

- 5-10 echte Clips am Dartboard aufnehmen (verschiedene Beleuchtung, Winkel)
- Ground-Truth-Annotations manuell erstellen
- Accuracy-Thresholds fuer echte Clips kalibrieren (realistischer als synthetisch)
- outer_bull-Erkennung verbessern (aktuell verpasst wegen zu kleinem Blob in schmaler Ring-Zone)

## Prioritaet 24: Kamera-Vergleich und Kontur-Referenzdaten (neu — entdeckt bei P20)

Ziel:

- Verstehen wie sich Diff-Konturen zwischen verschiedenen Kameras und Wurfpositionen unterscheiden

Typische Arbeiten:

- Probewuerfe mit verschiedenen Kameras aufnehmen (links/rechts positioniert)
- Diff-Masken vergleichen: Konturform, Groesse, Schatten-Einfluss pro Kamera
- Referenz-Datensatz fuer zukuenftige Algorithmus-Entwicklung (P20, P21) aufbauen
- Beleuchtungs-Einfluss dokumentieren (welche Kamera-Position produziert sauberste Konturen)

## Prioritaet 27: Marker-Kalibrierung auf neue Masse aktualisieren (neu — Session-Start)

Ziel:

- Kalibrierungskonfiguration an geaenderte physische Marker-Masse anpassen

Typische Arbeiten:

- ArUco Dict 7x5 50, Marker 0-3, 75mm Kantenlaenge — unveraendert
- Mitte-zu-Mitte Abstand: 430mm (verifizieren)
- Corner-zu-Corner: 505mm (vorher 480mm) — in calibration_config.yaml aktualisieren
- Kalibrierung neu durchfuehren und Qualitaetsmetrik vergleichen

## Prioritaet 29: Stereo Calibration UI Wizard (neu — Multi-Cam Assessment)

Kritikalitaet: KRITISCH

Ziel:

- Stereo-Kalibrierung fuer Nicht-Experten bedienbar machen

Typische Arbeiten:

- Step-by-Step Wizard: Kameras auswaehlen → Intrinsics pruefen → Stereo-Paare aufnehmen → Kalibrierung berechnen → Reprojektionsfehler anzeigen → Speichern/Verwerfen
- Fortschritts-Feedback via WebSocket (Frame-Counter, Winkel-Hinweise)
- Reprojektionsfehler-Schwelle als Quality Gate (RMS < 1.0px)
- Dateien: src/cv/stereo_calibration.py, src/web/routes.py, templates/index.html, static/js/ (neues Modul)

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

## Prioritaet 66: Telemetrie-Dashboard Langzeit-Trends

(reserviert)

## Prioritaet 74: Per-Throw Accuracy Regression Gate fuer CI (neu — entdeckt bei P68)

Kritikalitaet: MITTEL

Ziel:

- P68 hat timestamp-basiertes Matching eingefuehrt, das pro Wurf zeigt ob er korrekt erkannt wurde. Darauf aufbauend kann ein CI-Test pruefen, dass bekannte "stable" Wuerfe (die zuverlaessig erkannt werden) nicht regressieren. Ein YAML-Flag `stable: true` pro Wurf in ground_truth.yaml wuerde markieren, welche Wuerfe als Regressions-Gate dienen.
- Threshold: z.B. "alle stable-Wuerfe muessen korrekt erkannt werden" als harter CI-Check.

Typische Arbeiten:

- `stable: true` Flag in ground_truth.yaml fuer zuverlaessig erkannte Wuerfe setzen
- CI-Test der stable-Wuerfe via `match_detections_to_ground_truth()` prueft
- Separate Metriken fuer stable vs. unstable Wuerfe im Report

Warum sinnvoll: Verhindert Regressionen bei CV-Aenderungen, ohne dass alle Wuerfe (inkl. schwieriger Edge Cases) gruen sein muessen.

## Prioritaet 77: Game-Engine Cricket Sektor-Validierung (neu — entdeckt bei Agent-Run)

Kritikalitaet: MITTEL

Ziel:

- Cricket erlaubt nur Sektoren 15-20 und 25 (Bull). Aktuell wird jeder Sektor akzeptiert ohne Pruefung.

Typische Arbeiten:

- `register_throw()` im Cricket-Modus: Sektor gegen erlaubte Liste pruefen
- Ungueltige Sektoren ignorieren oder mit Warnung zurueckgeben
- Tests fuer Edge Cases (Sektor 14, 21, 0)
- Dateien: `src/game/engine.py`, `tests/test_game_engine.py`

Warum sinnvoll: P14 hat allgemeine Robustheit verbessert, aber Cricket-spezifische Sektorvalidierung fehlt noch.

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
| 15 | **360 LED Ring Light** | Tech Guide, Scolia, Autodarts, alle Systeme | Hardware | SEHR HOCH | "Accuracy depends more on lighting uniformity than on algorithmic sophistication." Universelle Hardware-Empfehlung aller Systeme. Eliminiert Richtungsschatten komplett. Single biggest improvement fuer Erkennungsqualitaet. Kostet ~20-40 EUR. |
| 16 | **Zweite/Dritte Kamera bei 120 Grad Intervall** | Tech Guide, Autodarts | Hardware+SW | SEHR HOCH | Multi-Cam-Triangulation erreicht 99%+ vs. ~95% Single-Cam. Drei OV9732 bei 120 Grad ist der Goldstandard. Unser Multi-Cam-Code ist vorbereitet (P29-P36). 3 Kameras bei 720p kosten ~30-50 EUR. |
| 17 | **Homography-Fallback bei Marker-Occlusion** | Tech Guide | Mittel | HOCH | Wenn Marker durch Hand verdeckt: letzte gueltige Homography weiternutzen, "homography age" Counter fuehren, Warnung nach N Frames ohne Marker-Re-Detektion. |
| 18 | **LAB-Farbraum statt Grayscale fuer Diff** | Tech Guide | Mittel | MITTEL | CLAHE auf L-Kanal in LAB statt auf Grayscale. LAB trennt Luminanz von Chrominanz — robuster bei farbiger Beleuchtung. |
| 19 | **HSV-basierte Flight-Color-Detection als Fallback** | Tech Guide | Mittel | MITTEL | Wenn Contour-basierte Detection versagt: HSV-Filterung auf bekannte Flight-Farben als Fallback. Setzt voraus: Dart-Farbe ist konfiguriert. |
| 20 | **Gaussian Fitting fuer Sub-Pixel Tip** | Tech Guide | Mittel | MITTEL | Statt cornerSubPix: Gaussian-Fit auf Intensitaetsprofil um den erkannten Tip. Erreicht ~0.1-0.5 Pixel Genauigkeit (~1mm am Board). |
| 21 | **Multi-Dart Discrimination: Masking bekannter Darts** | Tech Guide | Mittel | HOCH | Bekannte Dart-Positionen im Diff maskieren um Re-Detektion zu vermeiden. Robin-Hood-Detection als Spezialfall. |
| 22 | **Directional Morphological Kernels (Multi-Angle)** | Tech Guide (matherm) | Mittel | MITTEL | Rotierte Linien-Kernel bei 0-150 Grad: der Winkel mit laengstem Contour-Match = Dart-Orientierung. |

## TIER 4: Langfristig — Gamechanger, hoher Aufwand

| # | Idee | Quelle | Aufwand | Impact | Details |
|---|------|--------|---------|--------|---------|
| 23 | **YOLOv8n Dart-Tip-Detection (ONNX)** | DeepDarts CVPR 2021, Dart Sense, Tech Guide | Gross | SEHR HOCH | 6 MB Modell, ~20-40ms CPU via `cv2.dnn.readNetFromONNX()`. Braucht 16k+ annotierte Trainingsbilder. |
| 24 | **Piezoelektrischer Kontakt-Mikrofon Trigger** | Tech Guide (Patent), Flight Club | Hardware | HOCH | Piezo-Sensor auf Board-Rueckseite als Impact-Trigger. Kostet ~5 EUR. |
| 25 | **Vibrationssensor + CV Hybrid** | Tech Guide (Patent US20170307341A1) | Hardware+SW | HOCH | Kombination aus Piezo-Trigger und CV-Validierung. Beste Latenz bei niedrigstem CPU-Verbrauch. |
| 26 | **Semi-Supervised Bootstrapping fuer Trainingsdaten** | Tech Guide, DeepDarts | Gross | MITTEL | Aktuelles System nutzen um Trainingsbilder vorzulabeln. Einziger praktischer Weg zu 16k+ Trainingsbildern. |
| 27 | **Event Camera (DVS)** | Tech Guide | Sehr gross | MITTEL | Microsekunden-Aufloesung, 120+ dB Dynamik. Aber: >1000 EUR, experimentell. |

## TIER 5: Quick-Wins — kleine Aenderungen, kleiner aber spuerbarer Gewinn

| # | Idee | Quelle | Aufwand | Impact | Details |
|---|------|--------|---------|--------|---------|
| 28 | **detectShadows=False in MOG2** | Agent-Research, Tech Guide | Trivial | KLEIN | Spart ~10-15% Verarbeitungszeit. |
| 29 | **MOG2 learningRate senken** | Tech Guide | Trivial | KLEIN | `learningRate=0.002` statt Default ~0.01. |
| 30 | **Kamera-Fokus-Qualitaetscheck beim Start** | Tech Guide | Klein | MITTEL | Laplacian-Varianz beim Pipeline-Start pruefen. |
| 31 | **Helle Flights empfehlen / warnen** | Tech Guide, Scolia | Trivial | KLEIN | UI-Hinweis fuer helle, kontrastreiche Flights. |
| 32 | **cv2.setNumThreads() setzen** | Agent-Research | Trivial | KLEIN | OpenCV alle CPU-Kerne nutzen lassen. |
| 33 | **Frame-Skip im Idle** | Agent-Research, Tech Guide | Klein | MITTEL | Jeden 2./3. Frame im Idle ueberspringen. Halbiert CPU-Last im Leerlauf. |

## Empfohlene Reihenfolge fuer naechste Implementierung

1. **P37 Live-Realtest** — Ohne echte Board-Validierung sind weitere Algorithmus-Aenderungen blind
2. **#15 LED Ring Light** — Groesster Hardware-Impact, loest viele Software-Probleme
3. **#5 HoughLinesP** — Autodarts-Kernansatz, zweiter Tip-Detection-Algorithmus
4. **#7 Temporal Stability Gating** — Reduziert False Positives durch Vibration
5. **#10 Bounce-Out Detection** — Wichtig fuer korrekte Spiellogik
6. **#28-33 Quick-Wins** — Schnell umsetzbar, kumulativer Effekt
7. **#8 Camera Sharpness** — Automatische Kompensation fuer verschiedene Kameras
8. **#16 Zweite Kamera** — Sprung auf 99%+ Genauigkeit
