

# Priorities

Diese Liste beschreibt die empfohlene Weiterentwicklung aus Sicht des Projektstands 2026-03-17.
Prio 1–7 der vorherigen Liste sind abgeschlossen.

## Prioritaet 9: Multi-Cam UX weiter verbessern (NIEDRIG — teilweise erledigt)

**Teilfortschritt 2026-03-18:** Kamera-Vorschau-Thumbnails im Multi-Cam-Setup-Modal implementiert. Neuer Endpunkt `GET /api/camera/preview/{source}` liefert einzelnes JPEG-Bild von beliebiger Kamera-Quelle. Jede Kamera-Zeile zeigt 200x150px Vorschau mit Refresh-Button. Funktioniert unabhaengig von laufender Pipeline. Geaenderte Dateien: `src/web/routes.py`, `templates/index.html`, `static/js/app.js`, `static/css/style.css`.

**Teilfortschritt 2026-03-19:** Multi-Cam-Kalibriermodus repariert. Ursache war, dass fast alle Kalibrier-Endpunkte nur `app_state["pipeline"]` verwendeten, obwohl im Multi-Cam-Betrieb die aktiven Live-Pipelines unter `app_state["multi_pipeline"]` liegen. `src/web/routes.py` loest jetzt fuer Kalibrier-Frames, Status, Board-Alignment, Lens-Setup, ROI/Overlay, Ring-Check und optischen Mittelpunkt die gewaehlte Sub-Pipeline pro `camera_id` auf. Das Kalibrier-Modal erhielt in `templates/index.html` und `static/js/app.js` eine explizite Kamera-Auswahl, zielbezogene Status-/Fehlertexte und per-Kamera-Requests. Regression: `tests/test_routes_coverage4.py` um 5 Multi-Cam-Kalibrier-Tests erweitert; zusaetzlich 20 fokussierte Kalibrier-/Stereo-Tests und 163 Route-Coverage-Tests gruen. Geaenderte Dateien: `src/web/routes.py`, `static/js/app.js`, `templates/index.html`, `static/css/style.css`, `tests/test_routes_coverage4.py`.

**Teilfortschritt 2026-03-19:** Multi-Cam-Kalibrierdialog weiter gefuehrt. `static/js/app.js` nutzt jetzt den vorhandenen Multi-Status fuer klickbare Per-Kamera-Karten, eine dynamische Empfehlung der naechsten Aktion, visuelles Highlight des empfohlenen Buttons und einen "Weiter"-CTA nach erfolgreichem Schritt. Der CTA startet den empfohlenen Standardpfad jetzt direkt: gleiche Kamera fuehrt unmittelbar in Lens Setup bzw. Board-ArUco, Kamerawechsel schaltet zuerst auf die Zielkamera um und startet dann den naechsten Schritt. `templates/index.html` erhielt Guide- und Next-Step-Panels, `static/css/style.css` die dazugehoerigen Karten-/Guide-Stile. Verifikation: `node -c static/js/app.js`, `python -m pytest tests/test_web.py tests/test_routes_extra.py tests/test_websocket.py tests/test_stereo_wizard_api.py -q`, `python -m pytest tests/test_routes_coverage4.py::TestCalibrationEndpointsWithMultiCam -q`. Geaenderte Dateien: `static/js/app.js`, `templates/index.html`, `static/css/style.css`.

Verknuepfte Weaknesses: keine

Verknuepfte Entscheidungen: 2026-03-18-multi-cam-9-phase-plan

Ziel:

- Multi-Cam-Setup fuer Nicht-Experten bedienbar machen

Verbleibende Arbeiten:

- Drag-and-Drop Kamera-Anordnung
- Board-Pose: visuelles Feedback (erkannte Marker im Bild einblenden)
- Setup-Wizard: automatisch zum naechsten Schritt wechseln wenn ein Schritt erledigt ist

## Arbeitsregel fuer Agents

Wenn der User nur allgemein nach "weiterentwickeln" fragt und keine andere Richtung vorgibt, beginne oben in der Liste und arbeite nach unten.

## Format fuer erledigte Prioritaeten

```

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

## Prioritaet 64: routes.py Test-Coverage auf 80%+ heben

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

## Prioritaet 65: Camera Preview Endpoint absichern gegen gleichzeitige Zugriffe (neu — entdeckt bei P9)

Kritikalitaet: NIEDRIG

Ziel:

- Der neue `/api/camera/preview/{source}` Endpunkt oeffnet und schliesst eine Kamera fuer jedes Vorschaubild. Bei schnellem Mehrfachklick oder mehreren Browsern koennte das zu Race Conditions fuehren (gleiche Kamera-Quelle gleichzeitig geoeffnet).

Typische Arbeiten:

- Lock pro Kamera-Source einbauen, damit maximal ein Preview-Request gleichzeitig die Kamera oeffnet
- Optionalen kurzen Cache (2-3 Sekunden) fuer wiederholte Requests auf gleiche Source
- Timeout falls Kamera-Open haengt (aktuell blockiert der Endpunkt unbegrenzt)

Warum sinnvoll: Verhindert Ressourcen-Konflikte und haengende Requests im Multi-User-Szenario.

**Status: ✅ ERLEDIGT 2026-03-18**

**Umsetzung:** Per-Source `asyncio.Lock` verhindert gleichzeitige Kamera-Oeffnung fuer dieselbe Quelle. TTL-Cache (2.5s) liefert wiederholte Requests aus dem Speicher. `asyncio.timeout(5s)` verhindert endloses Blockieren bei haengendem Kamera-Open. 504-Response bei Timeout. 8 neue Tests. Geaenderte Dateien: `src/web/routes.py`, `tests/test_camera_preview_lock.py`.

## Prioritaet 66: Telemetrie-Dashboard Langzeit-Trends

(reserviert)

## Prioritaet 73: Jinja2Templates-Instanz in setup_routes Factory verschieben (neu — entdeckt bei P67)

Kritikalitaet: NIEDRIG

Ziel:

- `templates = Jinja2Templates(directory="templates")` ist noch module-level in `routes.py`. Beim Import wird das Template-Verzeichnis relativ zum aktuellen Working Directory aufgeloest. Falls Tests oder andere Aufrufer ein anderes CWD haben, schlaegt das Template-Rendering fehl. Ausserdem verhindert die module-level Instanz, dass Tests eigene Template-Verzeichnisse injizieren koennen.

Typische Arbeiten:

- `templates` innerhalb `setup_routes()` erzeugen oder als Parameter uebergeben
- Optional: Template-Verzeichnis aus app_state oder Konfiguration beziehen
- Template-bezogene Tests isolierbar machen
- Dateien: src/web/routes.py

Warum sinnvoll: Bei P67 entdeckt — nach der Router-Factory-Umstellung ist `templates` das letzte verbliebene module-level Objekt mit Seiteneffekten in routes.py.

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

## Prioritaet 76: Blocking stop_pipeline_thread/start_single_pipeline in run_in_executor wrappen (neu — entdeckt bei P70)

Kritikalitaet: MITTEL

Ziel:

- P70 hat die `_time.sleep()` Aufrufe durch `await asyncio.sleep()` ersetzt, aber die synchronen Funktionen `stop_pipeline_thread()` (bis zu 5s Timeout) und `start_single_pipeline()` blockieren weiterhin den Event-Loop. Diese Aufrufe sollten in `asyncio.get_event_loop().run_in_executor(None, ...)` gewrappt werden.

Typische Arbeiten:

- `stop_pipeline_thread(app_state, "single", timeout=5.0)` in `await loop.run_in_executor(None, stop_pipeline_thread, ...)` wrappen
- `start_single_pipeline(app_state, camera_src=...)` ebenso
- Pipeline-Lock-Handling (`with _pl`) muss im gleichen Thread bleiben — ganzen Lock-Block in Executor verschieben
- Tests fuer korrekte async Ausfuehrung schreiben
- Dateien: src/web/routes.py

Warum sinnvoll: Die Sleep-Phasen sind jetzt non-blocking (P70), aber die eigentlichen Pipeline-Operationen (Thread-Join mit 5s Timeout, Kamera-Open) blockieren den Event-Loop weiterhin. Komplettiert die async-Umstellung der Pipeline-Management-Endpunkte.