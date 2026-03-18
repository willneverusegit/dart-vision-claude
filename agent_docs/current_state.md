# Current State

Stand dieser Zusammenfassung: 2026-03-18 (Welle 1-4 + Auto-Agents: P22, P26, P27, P28, P30-P31, P33, P39-P43, P46-P49, P51-P56, P60-P61, Tier-2 #5-#7, #10-#14, P32, P35 erledigt)

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

## Was heute als fortgeschritten, aber noch sensibel gilt

- Multi-Camera-Pipeline (gehaertet: Readiness-Diagnose, Config-Persistenz, Setup-Wizard)
- Stereo-Kalibrierung (Triangulations-Genauigkeit validiert: <5mm auf 8 Board-Positionen)
- Board-Pose-Kalibrierung
- Triangulation und Voting-Fallback
- Umschalten zwischen Single- und Multi-Cam (Fix: Kamera-Release-Timing)

## Verifizierte Kennzahlen

- `1102` Tests bestanden (Stand 2026-03-18, +457 neue Tests)
- Gesamt-Coverage ~77%
- Wichtige Module: main.py 78%, routes.py 66%, pipeline.py 68%, multi_camera.py 62%, capture.py 72%
- synthetische Pipeline-Benchmarks fuer `1`, `2` und `3` Kameras innerhalb der definierten KPI-Grenzen
- E2E-Replay-Tests: 90% Hit Rate, 100% Score Accuracy auf synthetischen Clips (6 Tests)
- Echte Video-Validierung: ~55% Hit Rate, 64% Sektor-Accuracy auf 2 echten Videos (rec_094311, rec_094521)
- Ground-Truth fuer 52 Wuerfe in 5 Videos annotiert (testvids/ground_truth.yaml)

## Wichtige Projektfakten

- `config/calibration_config.yaml` enthaelt eine gueltige Kalibrierung fuer `default`
- `config/multi_cam.yaml` speichert last_cameras, sync_depth Presets (tight/standard/loose), governor Config
- Telemetrie-Endpunkt `/api/stats` liefert FPS, Dropped Frames, Queue-Druck, RAM
- Telemetrie-Historie-Endpunkt `/api/telemetry/history` liefert zeitliche Verlaeufe und Alerts
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
- `.claude/plans/shimmying-knitting-corbato.md` — 9-Phasen Multi-Cam-Integrationsplan (2026-03-18)
- `.claude/plans/lovely-munching-rabin.md` — Welle 1-5 Parallelisierungsplan (2026-03-18)
