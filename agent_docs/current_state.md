# Current State

Stand dieser Zusammenfassung: 2026-03-23 (Welle 1-4 + Auto-Agents + Multi-Cam E2E Kalibrierung auf Hardware verifiziert, Config-Merge-Bug gefixt, Board-Pose Endpoint repariert, triangulation_possible=true)

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
- Frame-Diff-basierte Treffererkennung: Before/After-Diff statt MOG2-Centroid (P19)
- Dart-Tip-Detection: Spitze statt Centroid als Trefferposition, validiert auf 18 echten Aufnahmen (P20)
- Kalibrier-Qualitaetsmetrik (quality 0-100, Ringradien-Abweichung in mm)
- Optische-Mittelpunkt-Erkennung mit Intensity-Fallback
- Kalibrierungs-UX mit Statusanzeige und gefuehrten Schritten
- Multi-Cam-Kalibrierung nutzt pro Kamera die aktive Sub-Pipeline statt nur den Single-Cam-Pfad (Frame, Info, Board, Lens, ROI, Overlay, Optical Center)
- Multi-Cam-Kalibrierdialog fuehrt per Kamera durch den naechsten Schritt (Statuskarten, Empfehlungspanel, Button-Highlight, Weiter-CTA mit direktem Start des empfohlenen Standardpfads)
- Multi-Cam-Kalibrierung V1 trennt jetzt Handheld (`full`) und Stationaer (`provisional`) sauber; der Stationaer-Pfad nutzt geschaetzte Intrinsics nur transient und speichert Stereo-Metadaten additiv im bestehenden `pairs`-Schema
- Wizard-/Dialog-UX zeigt Modusauswahl (`Kalibrierboard bewegen` vs. `Kalibrierboard bleibt fest`), Lens-Capture-Modus (`auto`/`manual`), Schaerfe, Reject-Grund und Ergebnis-Badges (`Kalibriert`/`Provisorisch`)
- Der Multi-Cam-Setup-Guide besitzt jetzt einen expliziten Wizard-CTA; das Frontend baut daraus eine echte Task-Queue ueber fehlende Lens-/Board-/Stereo-Schritte, synchronisiert Entry-/Wizard-/Stereo-Modus und fuehrt bei `Back`/`Abbrechen` sauber in die Config-Ansicht zurueck
- ChArUco-Guidance- und Lens-Capture-Flow besitzen jetzt manuelle Frame-Aufnahme, niedrigere Manual-Diversity, explizite Reject-Gruende und Live-Status fuer Schaerfe und nutzbare Frames
- Lens- und Stereo-Kalibrierung loesen ChArUco-Layouts jetzt zur Laufzeit zwischen `7x5_40x20`, `7x5_40x28`, `5x7_40x20`, `5x7_40x28` auf; `auto` ist der empfohlene UI/API-Standard
- Guided Capture zaehlt nur noch Frames mit erfolgreicher ChArUco-Interpolation; Rohmarker alleine machen den Collector oder die Progress-API nicht mehr "bereit"
- ChArUco Auto-Capture sammelt jetzt automatisch Frames im Progress-Endpoint (zuvor nur update_detection ohne add_frame_if_diverse)
- Config-Persistenz: CalibrationManager merged jetzt pro-Kamera-Sections statt sie zu ueberschreiben — Lens- und Board-Daten bleiben beide erhalten
- Board-Pose Endpoint (`POST /api/calibration/board-pose`) funktioniert mit try/except Error-Handling und korrektem `get_config()`-Aufruf
- Multi-Cam-Kalibrierung erstmals end-to-end auf Hardware verifiziert: Lens (RMS <0.23px), Board (4/4 Marker), Pose (solvePnP), Stereo — triangulation_possible=true
- `/api/calibration/charuco-progress/{camera_id}` liefert jetzt explizit `markers_found`, `charuco_corners_found`, `interpolation_ok`, `resolved_preset`, `resolved_board`, `usable_frames`, `warning`; der normale Lens-Button startet erst Guided Capture und kalibriert erst nach genuegend nutzbaren Frames
- `/api/calibration/charuco-start/{camera_id}` akzeptiert `mode` und `capture_mode`, `POST /api/calibration/capture-frame/{camera_id}` erlaubt manuelle Aufnahmen, und `charuco-progress` liefert zusaetzlich `sharpness`, `reject_reason`, `mode` und `capture_mode`
- Laufende Multi-Cam-Guided-Capture-/Wizard-Sessions behalten ihren Kamera-Kontext jetzt auch dann, wenn das Frontend den Multi-Cam-Flag temporaer verliert; Statusmeldungen und Folge-Requests fallen waehrend der Session nicht mehr irrefuhrend auf `Single-Cam` zurueck
- `/api/multi/readiness` und `/api/multi-cam/calibration/status` sind additiv erweitert: bestehende Felder bleiben erhalten, hinzu kommen `ready_full`, `ready_provisional`, `calibration_quality` und pro Stereo-Paar `quality_level`, `calibration_method`, `intrinsics_source`, `pose_consistency_px`, `warning`
- Kalibrier-Ergebnisbilder (result_image) mit Overlay (Marker-Ecken, Scoring-Ringe, 3D-Achsen, Epipolar-Linien) in allen 4 Endpoints
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
- X01-Checkout-Vorschlaege (Scores 2-170) mit PDC/BDO-Standard-Checkouts und Backend-Lookup
- Double-In-Variante fuer X01 (`double_in=True`)
- Performance-Monitoring: TelemetryHistory mit Ring-Buffer (300 Samples), FPS/Queue-Alerts
- Telemetrie-API (`/api/telemetry/history`) mit History, Alerts, Summary
- Frontend Performance-Monitor-Panel mit Canvas-Chart und Alert-Banner
- WebSocket-Broadcast bei Telemetrie-Alert-Zustandsaenderung
- Optionales CPU-Monitoring via psutil
- Responsive Layout (Mobile 375px, Tablet 768px, Desktop)
- Loading-Spinner beim Pipeline-Start
- Keyboard-Shortcut-Hints (Enter/Del/U)
- Kamera-Feed mit korrektem Aspektverhaeltnis (object-fit:contain)
- Telemetrie-Export als JSONL (DARTVISION_TELEMETRY_FILE) und /api/telemetry/export (JSON/CSV)
- Temporal Safety Bundle: Stability Gating (3-Frame), Scoring Lock (0.5s), Cooldown (50px Zone)
- Bounce-Out Detection (Post-Frame vs Baseline Vergleich)
- HoughLinesP + fitLine als alternative Tip-Detection mit Confidence-Orchestrierung
- Downscaled Motion Detection (4x) und Frame-Skip im Idle
- Adaptive Thresholds (Otsu-Bias + Search Mode nach 90 Frames Stille)
- Contour Shape Confidence Score (gewichtet: Aspect-Ratio, Solidity, Area)
- Light Stability Monitor (automatische Threshold-Erhoehung bei instabilem Licht)
- Kalibrierung: dynamischer BOARD_CROP_MM, center_px als ROI-Mitte, cornerSubPix-Fix
- Kamera-Schaerfemetrik (Laplacian-Varianz) mit adaptiver Threshold-Anpassung pro Kamera (P26)
- Wire-Artefakt-Filter fuer scharfe Kameras (morphologisches Opening, groessenbasiert)
- Telemetrie-Export: Session-ID in Export, JSON+CSV Download-Buttons im Performance-Monitor (P22)
- Edge Cache fuer Canny-Reuse pro Frame (P41, war bereits implementiert — verifiziert)
- Cooldown Management: 50px Spatial Exclusion Zones + 30-Frame Lockout nach bestaetigtem Treffer (P42)
- cv2.absdiff Cache pro Frame in diff_detector — keine redundante Diff-Berechnung (P47)
- Telemetrie-Retention: JSONL-Rotation bei Ueberschreitung, Age-Cleanup, File-Size-Warning (P48)
- High-Contrast Theme als 3. Option, 3-Way Toggle (dark→light→high-contrast), CSS Transitions (P46)
- 16 Detection-Component Integration Tests (Cooldown-Sequenz, Bounce-Out, Shape-Reject, Overhead) (P49)
- Adaptive Thresholds verifiziert: Otsu-Bias + Search Mode bereits in Welle 3 implementiert (P40)
- Intrinsics Validation vor Stereo-Kalibrierung verifiziert (P31)
- Video-Replay Ground-Truth-Validierungstests: 3/5 Videos bestehen, 2 xfail wegen Baseline-Warmup (P39)
- CSS Theme-Variablen: 15 neue Variablen, alle hardcoded Farben ersetzt fuer Dark/Light/High-Contrast (P52)
- Camera Error Reporting: Dict-basierte Fehler, WebSocket broadcast, per-camera Status-Badges (P30)
- 11 FrameDiffDetector Integration Tests mit CooldownManager/MotionFilter (P53)
- Baseline-Warmup Fix: force-init bei erster Motion, 3/5 Videos bestehen jetzt strikt (P55)
- Homography-Fallback: gecachte Homography bei Marker-Occlusion mit Age-Counter und konfigurierbarem Timeout (P60)
- Multi-Cam Error Recovery: Auto-Reconnect mit exponentiellem Backoff, graceful Degradation, manueller Reconnect-API (P56)
- Stereo-Kalibrierung Fortschritts-Feedback: Fehleranzeige bei nicht erkanntem Board, valid_pairs Tracking (P54)
- Deduplizierung _is_already_confirmed vs CooldownManager verifiziert und dokumentiert (P51)
- Homography-Fallback in Pipeline integriert: `aruco_calibration_with_fallback()` aktiv, homography_age in Stats (P61)
- CSS Theme-Variablen: alle hardcoded Farben durch var()-Referenzen ersetzt, 15+ neue Variablen (P52)
- Telemetrie-Cleanup-Scheduler: asyncio Background-Task, GET /api/telemetry/status, POST /api/telemetry/rotate (P51-Cleanup)
- Multi-Cam Sync-Depth-Presets: tight/standard/loose validiert mit 57 Tests (P33)
- Auto-Exposure-Kompensation: Brightness-Tracking (EMA), adaptive CLAHE clipLimit, /api/camera/quality Endpoint (P50)
- Frontend Homography-Age Warnung bei >30 Frames ohne Marker + Telemetrie-Status-Widget mit Rotate-Button (P62)
- cv2.setNumThreads(0) fuer volle CPU-Nutzung, Flight-Tipp im Kalibrierungs-Modal (P63)
- 48 neue Route-Tests, routes.py Coverage 66%→74% (P64-Vorarbeit)
- Camera Preview Locking: asyncio.Lock pro Source, TTL-Cache 2.5s, Timeout 5s (P65)
- 54 weitere Route-Tests fuer Pipeline-Start/Stop, Multi-Cam, WebSocket, Telemetrie (P64)
- P64 abgeschlossen: fokussiertes Route-/Wizard-/Preview-/ChArUco-Testset bringt `src/web/routes.py` auf 81% Coverage
- Ground-Truth-Validierungsskript und 32 Tests (P11)
- Video-Replay-Testinfrastruktur: add_ground_truth.py Helper, verbessertes Fehler-Reporting, 29 Tests (P39)

## Was heute als fortgeschritten, aber noch sensibel gilt

- Multi-Camera-Pipeline (gehaertet: Readiness-Diagnose, Config-Persistenz, Setup-Wizard)
- Stereo-Kalibrierung (Triangulations-Genauigkeit validiert: <5mm auf 8 Board-Positionen)
- Board-Pose-Kalibrierung
- Triangulation und Voting-Fallback
- Umschalten zwischen Single- und Multi-Cam (Fix: Kamera-Release-Timing)

## Verifizierte Kennzahlen

- `1348` Tests bestanden (Stand 2026-03-19, ohne e2e/scripts)
- Gesamt-Coverage ~77%
- Wichtige Module: main.py 78%, routes.py 81%, pipeline.py 68%, multi_camera.py 62%, capture.py 72%
- Zusatzverifikation 2026-03-20 (P64-Abschluss): 247 fokussierte Web/Route/Wizard/Preview/ChArUco-Tests gruen; `src/web/routes.py` 81% Coverage
- Zusatzverifikation 2026-03-20 (Live-Check/Wrap-up): Multi-Cam-Guided-Capture im Browser gegen `http://127.0.0.1:8000/` verifiziert, `tests/test_wizard_flow.py` und `tests/test_stereo_wizard_api.py` (`11` Tests) gruen; lokaler Git-Bestand auf `main` plus drei aktive Neben-Worktrees bereinigt
- Zusatzverifikation 2026-03-20 (Multi-Cam Calibration V1): `node -c static/js/app.js`, `python -m pytest tests/test_charuco_progress.py tests/test_routes_extra.py tests/test_stereo_wizard_api.py tests/test_multi_hardening.py tests/test_wizard_flow.py -q` (`52` Tests) und `python -m pytest tests/test_collector_quality.py tests/test_provisional_stereo.py tests/test_multi_cam_config.py -q` (`18` Tests) gruen
- Zusatzverifikation 2026-03-20 (Wizard Entry UX): `node -c static/js/app.js` sowie `python -m pytest tests/test_wizard_flow.py tests/test_stereo_wizard_api.py -q` (`11` Tests) gruen
- Zusatzverifikation 2026-03-19: 256 fokussierte Tests gruen (Multi-Cam-Kalibrierung, Route-Coverage, Web/Hardening, Multi-Cam-Config); kein Vollsuite-Lauf
- Zusatzverifikation 2026-03-19 (Kalibrier-UX): 35 weitere fokussierte Checks gruen (`node -c`, 30 Web/Route/WebSocket/Stereo-Tests, 5 Multi-Cam-Kalibrier-Tests)
- Zusatzverifikation 2026-03-19 (ChArUco-Haertung): 160 fokussierte Tests gruen (`tests/test_calibration.py`, `tests/test_charuco_progress.py`, `tests/test_stereo_calibration.py`, `tests/test_stereo_wizard_api.py`, `tests/test_wizard_flow.py`, `tests/test_web.py`, `tests/test_routes_extra.py`, `tests/test_routes_coverage4.py`); lokale 1080p-Kalibrierclips `testvids/1.mp4` und `testvids/2.mp4` bestaetigen `7x5_40x20` -> 14 Rohmarker / 0 ChArUco-Ecken und `auto` -> `5x7_40x20` mit 18 Ecken
- synthetische Pipeline-Benchmarks fuer `1`, `2` und `3` Kameras innerhalb der definierten KPI-Grenzen
- E2E-Replay-Tests: 90% Hit Rate, 100% Score Accuracy auf synthetischen Clips (6 Tests)
- Echte Video-Validierung: ~55% Hit Rate, 64% Sektor-Accuracy auf 2 echten Videos (rec_094311, rec_094521)
- Ground-Truth fuer 52 Wuerfe in 5 Videos annotiert (testvids/ground_truth.yaml)

## Wichtige Projektfakten

- `config/calibration_config.yaml` enthaelt eine gueltige Kalibrierung fuer `default`
- `config/multi_cam.yaml` speichert last_cameras, sync_depth Presets (tight/standard/loose), governor Config sowie additive Stereo-Metadaten (`calibration_method`, `quality_level`, `intrinsics_source`, `pose_consistency_px`, `warning`) unter dem bestehenden `pairs`-Schema
- Lokale Bilder/Videos sind repo-weit ignoriert; Git-/Worktree-Altlasten wurden aufgeraeumt, sodass nur aktive Neben-Worktrees erhalten bleiben
- Print-Pack und Kalibrier-Notizen verwenden wieder konsistent `430 mm` Marker-Mitte-zu-Mitte statt der veralteten `410 mm`-Angabe
- Telemetrie-Endpunkt `/api/stats` liefert FPS, Dropped Frames, Queue-Druck, RAM
- Telemetrie-Historie-Endpunkt `/api/telemetry/history` liefert zeitliche Verlaeufe und Alerts
- `/api/multi/readiness` liefert pro-Kamera-Diagnose fuer Multi-Cam-Setup und unterscheidet jetzt zwischen `ready_full` und `ready_provisional`
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

- `agent_docs/priorities.md` — offene Weiterentwicklungsziele
- `agent_docs/priorities_done.md` — abgeschlossene Prioritaeten (Archiv)
- `agent_docs/decisions.md` — Architektur-Entscheidungen
