# Multi-Cam Calibration — Zwei-Modi-Design (v5)

Stand: 2026-03-20

## Problemanalyse

Die ChArUco-basierte Lens-Kalibrierung sammelt keine Frames, weil der `CharucoFrameCollector` eine Mindest-Positions-Diversitaet von 15% der Bildbreite verlangt (~96px bei 640x480). Bei fest montiertem Board und fester Kamera bewegt sich der Centroid nur um 1-3% — nach dem ersten Frame wird kein weiterer akzeptiert.

Verifiziert mit echten Videos (`rec_20260320_042317.mp4`, `rec_20260320_042327.mp4`): 8-18 ChArUco-Ecken werden pro Frame erkannt, aber nur 1/15 Frames wird vom Collector akzeptiert.

## V1 Ziel

V1 loest zwei Dinge:
1. Den aktuellen Guided-Capture-Blocker im Handheld-Fall sauber beheben
2. Einen klar als eingeschraenkt markierten Stationaer-Pfad anbieten

**Kernregel:** Echte Lens-Kalibrierung und provisorische Schnellkalibrierung duerfen technisch und semantisch nicht vermischt werden.

## V1 Zuschnitt

1. **Handheld** wird der volle Qualitaetspfad: Auto- und Manual-Capture, entschaerfte Diversitaetsschwellen, saubere Reject-Gruende, echte Lens-Kalibrierung.
2. **Stationaer** wird ein Provisional-Pfad: Lens wird uebersprungen, Stereo-Extrinsics aus Board-Posen geschaetzt, Resultat sichtbar als eingeschraenkt markiert.
3. **Bestehende Flows** bleiben die Basis: Wizard, Guided-Capture-Polling, ChArUco-Presets.
4. **Kein Scope-Creep:** Nicht drin: automatischer Moduswechsel, neue Dictionaries, 3+ Kamera-Fusion, adaptive Timeout-Logik, Cleanup nebenbei.

## Wizard-Flow

```
[1. Modus waehlen]
     |
     +-- "Kalibrierboard bewegen" ---> [2. Lens]  ---> [3. Board Pose] ---> [4. Stereo]
     |   (volle Kalibrierung)          Auto+Manual      ArUco-Marker        stereoCalibrate()
     |                                 15 Frames         solvePnP            echte Intrinsics
     |                                 Diversitaet       Quality 0-100
     |
     +-- "Kalibrierboard bleibt fest" -> [2. Board Pose] ---> [3. Stereo (provisional)]
         (Schnellstart)                   ArUco-Marker        solvePnP-basiert
                                          solvePnP mit        geschaetzte Intrinsics
                                          estimate_intrinsics separat gespeichert
                                          Quality 0-100
```

Die Board-Pose wird im Board-Schritt berechnet; im Stationaer-Modus ggf. mit `estimate_intrinsics()`.

---

## Umsetzung in 5 Paketen

### Paket 1: Collector und API-Grundlage

**Dateien:** `src/cv/camera_calibration.py`, `src/web/routes.py`

Aenderungen:
- `CharucoFrameCollector` bekommt `calibration_mode`, `capture_mode`, Qualitaetsmetriken und letzten Ablehnungsgrund (`last_reject_reason`)
- `POST /api/calibration/charuco-start/{camera_id}` akzeptiert `mode` und `capture_mode`
- Neuer Endpoint `POST /api/calibration/capture-frame/{camera_id}` fuer manuelle Aufnahme
  - Response: `{"accepted": true/false, "reason": "...", "usable_frames": N, "frames_needed": M}`
- `GET /api/calibration/charuco-progress/{camera_id}` liefert zusaetzlich `sharpness`, `last_accept`, `reject_reason`, `mode`, `capture_mode`

**Regel:** Auto-Capture bleibt nur fuer `handheld + auto` aktiv.

### Paket 2: Handheld-Pfad robust machen

**Dateien:** `src/cv/camera_calibration.py`, `src/web/routes.py`

Aenderungen:
- Qualitaets-Gate **vor** dem Diversitaets-Check:
  1. `interpolation_ok` — mindestens 6 ChArUco-Ecken
  2. Schaerfe — Laplacian-Varianz ueber Schwelle
  3. Dann Diversitaets-Check
- V1 Diversitaet: Centroid-Abstand plus Corner-Count-Streuung (Pose-basierte Auswahl wird V1.1)
- Gesenkte Schwellen:
  - `min_position_diff`: 0.15 -> 0.05 (~32px bei 640px)
  - Manual-Capture: `min_position_diff=0.02`
- `min_rotation_diff_deg` wird aus dem Collector entfernt — der Parameter existiert zwar als Feld in `CharucoFrameCollector.__init__()`, wird aber in `add_frame_if_diverse()` nie geprueft. Statt toten Code zu beleben, wird Rotation erst in V1.1 mit der Pose-basierten Auswahl eingefuehrt.
- Manual-Capture senkt nur die Diversitaetsschwelle, nicht das Qualitaets-Gate

### Paket 3: Stationaer-Pfad als provisorischer Modus

**Dateien:** `src/cv/stereo_calibration.py`, `src/web/routes.py`

Aenderungen:
- Neue Hilfsfunktion `estimate_intrinsics(width, height)` — nur als transienter Seed, wird **nicht** als `lens_valid`-Kalibrierung gespeichert
- **Board-Pose im Stationaer-Modus:** Der bestehende `/api/calibration/board-pose` Endpoint verlangt echte Intrinsics (`routes.py:1348`). Im Stationaer-Modus muss `estimate_intrinsics()` dort als Fallback eingesetzt werden, wenn keine echte Lens-Kalibrierung vorliegt. Konkret: `intr = pipeline.camera_calibration.get_intrinsics() or estimate_intrinsics(frame.shape[1], frame.shape[0])`. Die `solvePnP`-Ergebnisse mit geschaetzten Intrinsics sind weniger genau, aber fuer die provisorische relative Pose ausreichend.
- Neue Funktion `stereo_from_board_poses(pose_a, pose_b)` — relative Extrinsics aus zwei `solvePnP`-Ergebnissen:
  - Kamera A: R_a, T_a (Kamera-zu-Board)
  - Kamera B: R_b, T_b
  - Relative Pose: `R_stereo = R_b @ R_a^-1`, `T_stereo = T_b - R_stereo @ T_a`
- `POST /api/calibration/stereo` bekommt `mode: "handheld" | "stationary"`

**Regeln:**
- `handheld` nutzt weiter `stereoCalibrate()`
- `stationary` sammelt 3-5 gute Paare, berechnet Board-Pose pro Kamera und daraus R/T
- Geschaetzte Intrinsics nicht als normale `lens_valid`-Kalibrierung speichern

**Geschaetzte Intrinsics (nur transienter Seed):**
```
fx = fy = image_width  (640 fuer 640x480)
cx = image_width / 2
cy = image_height / 2
dist_coeffs = [0, 0, 0, 0, 0]
```

**Quality-Metrik fuer den provisorischen Pfad:**
`stereoCalibrate()` liefert einen echten `reprojection_error` (RMS). Beim provisorischen Pfad ueber `stereo_from_board_poses()` gibt es keinen direkten Reprojektionsfehler. Stattdessen wird eine eigene Metrik berechnet:
- `pose_consistency`: Mittlere Reproj-Fehler der einzelnen `solvePnP`-Aufrufe beider Kameras
- Gespeichert als `pose_consistency_px` statt `reprojection_error`
- UI zeigt "Pose-Konsistenz: X.Xpx" statt "Reprojektionsfehler"

### Paket 4: Persistenz und Readiness sauber trennen

**Dateien:** `src/web/routes.py`, `src/utils/config.py`

**Config-Schema:** Das bestehende Runtime-Schema in `config.py` wird beibehalten. Neue Metadaten werden **additiv** ergaenzt:

```yaml
# config/multi_cam.yaml — bestehendes Schema beibehalten
pairs:
  cam_left--cam_right:          # Bestehender Key-Konvention (doppelter Bindestrich)
    R: [[...]]                  # Bestehende Feldnamen
    T: [[...]]                  # Bestehende Feldnamen
    reprojection_error: 0.845   # Bestehend, nur bei stereoCalibrate()
    calibrated_utc: "..."       # Bestehend
    # NEU: Metadaten additiv
    calibration_method: "stereoCalibrate"  # oder "board_pose_provisional"
    quality_level: "full"                  # oder "provisional"
    intrinsics_source: "lens_calibration"  # oder "estimated"
    pose_consistency_px: null              # Nur bei provisional, statt reprojection_error
    warning: null                          # oder "Provisorisch — Verfeinerung empfohlen"
```

**Aenderungen an `save_stereo_pair()`:** Neue optionale Parameter `calibration_method`, `quality_level`, `intrinsics_source`, `pose_consistency_px`, `warning`. Bestehende Aufrufe ohne diese Parameter funktionieren unveraendert (Default: `calibration_method="stereoCalibrate"`, `quality_level="full"`).

**Aenderungen an `get_stereo_pair()`:** Gibt die neuen Felder mit zurueck wenn vorhanden. Bestehender Code der nur `R`, `T`, `reprojection_error` liest, bricht nicht.

**Readiness-API:** Bestehende Endpoints behalten ihre Felder. Neue Felder werden **additiv** ergaenzt:
- `/api/multi/readiness` (routes.py): bestehendes `ready`-Feld bleibt, neue Felder `ready_full` und `ready_provisional` werden ergaenzt
- `/api/multi-cam/calibration/status` (routes.py): bestehendes `ready_for_multi`-Feld bleibt, neues `calibration_quality: "full" | "provisional" | "none"` wird ergaenzt

**Regel:** Der Stationaer-Pfad darf nicht so aussehen, als waere er gleichwertig zur echten Lens+Stereo-Kalibrierung.

### Paket 5: Wizard und UI

**Dateien:** `static/js/app.js`, `templates/index.html`, `static/css/style.css`

Aenderungen:
- Neuer Modus-Schritt vor Lens/Board/Stereo mit zwei Karten:
  - "Kalibrierboard bewegen" — "Volle Kalibrierung, bessere Genauigkeit"
  - "Kalibrierboard bleibt fest" — "Schnellstart, spaeter verfeinerbar"
- Handheld-Stepper: Modus -> Lens -> Board -> Stereo
- Stationaer-Stepper: Modus -> Board -> Stereo (Lens uebersprungen)
- Toggle Auto/Manuell im Guidance-Panel
- Button "Frame aufnehmen" (sichtbar wenn Manuell aktiv)
- Flash-Overlay: Gruen bei Accept, Rot bei Reject
- Reject-Grund als Einblendung: "Zu unscharf" / "Position zu aehnlich" / "Board nicht erkannt"
- Schaerfe-Balken (gruen/gelb/rot) neben Frame-Counter
- Ergebnisbanner fuer Provisional mit klarem Hinweis auf spaetere Verfeinerung
- "Verfeinern"-Button nach provisorischer Kalibrierung -> leitet in Handheld-Modus
- "Modus aendern"-Link im Stepper (Collector-Reset, Neustart)
- Provisorische Kalibrierung: Gelbes Badge "Provisorisch" im Status
- Volle Kalibrierung: Gruenes Badge "Kalibriert"

---

## Harte Entscheidungen fuer V1

1. `lens_valid` bleibt fuer echte Lens-Kalibrierung reserviert. Geschaetzte Intrinsics bekommen einen eigenen Status.
2. `stationary` darf Multi-Cam vorbereiten, aber nicht stillschweigend als Vollkalibrierung gelten.
3. Den bestehenden Auto-Capture-Hook im MJPEG-Feed in `routes.py` nur erweitern, nicht neu erfinden.
4. Den bestehenden Wizard-/Polling-Kontext in `app.js` weiterverwenden, statt einen zweiten Kalibrier-Flow daneben zu bauen.
5. Config-Schema (`pairs`, `cam_a--cam_b`, `R`/`T`) wird beibehalten. Neue Metadaten sind additiv.
6. Bestehende Readiness-APIs behalten ihre Felder. Neue Felder sind additiv.

## Edge Cases

| Szenario | Verhalten |
|----------|-----------|
| Modus-Wechsel mitten im Wizard | Zurueck zum Modus-Schritt, Collector-Reset, Neustart |
| Kamera-Ausfall waehrend Capture | Reconnect-Mechanismus greift, Collector behaelt Frames |
| Multi-Cam-Flag-Verlust | Bestehender Fix mit `_charucoPollingContext` bleibt aktiv |
| Stationaer + schlechte Marker | Board-Pose schlaegt fehl, Handlungsempfehlung |
| Handheld + alles unscharf | Qualitaets-Gate lehnt ab, spezifischer Grund angezeigt |
| Provisional -> Refine | Provisorische Daten werden durch echte ueberschrieben |
| Alter Code liest neue Config | Neue Felder werden ignoriert, R/T/reprojection_error bleiben |

## Zukunftsideen (nicht in V1)

- **V1.1:** Pose-basierte Frame-Auswahl (Tilt/Scale/Rotation) statt Centroid-Diversitaet
- **V1.1:** `min_rotation_diff_deg` als echte Diversitaets-Metrik implementieren
- **V1.1:** Manual Best-of-N (User nimmt viele Frames auf, Backend waehlt beste)
- **Spaeter:** Camera-Move statt Board-Move
- **Spaeter:** Factory-Seeded Intrinsics fuer haeufige Webcam-Modelle
- **Spaeter:** Offline-Clip-Kalibrierung (10-15s Video, asynchrone Frame-Selektion)
- **Spaeter:** Selbstverfeinerung aus bestaetigten Dart-Treffern

## Nicht im Scope (YAGNI)

- Keine automatische Kamera-Erkennung oder -Anordnung
- Kein neuer ChArUco-Dictionary-Support (DICT_6X6_250 bleibt)
- Keine neuen Board-Presets
- Keine 3+ Kamera-Fusion-Aenderungen
- Kein adaptives Timeout / automatischer Moduswechsel

## Testplan

1. Unit-Tests fuer Collector-Gate, Manual-Capture und Reject-Gruende
2. Unit-Tests fuer `estimate_intrinsics()` und `stereo_from_board_poses()`
3. Unit-Tests fuer `pose_consistency_px` Metrik
4. Route-Tests fuer `charuco-start`, `capture-frame`, `charuco-progress`, `stereo mode=stationary`
5. Route-Tests fuer Board-Pose mit `estimate_intrinsics()` Fallback
6. Config-Tests: neue Metadaten additiv, alter Code bricht nicht
7. Wizard-/Frontend-Tests fuer Moduswechsel und Schrittfolge
8. Syntaxcheck `node -c static/js/app.js`
9. Fokussierte Pytests rund um Kalibrierung, Stereo und Wizard
10. Validierung mit echten Videos (`rec_20260320_042317.mp4`, `rec_20260320_042327.mp4`)

## Empfohlene Umsetzungsreihenfolge (Sessions)

1. Backend Collector/API (Paket 1)
2. Handheld-Flow stabil (Paket 2)
3. Stationaer-Backend (Paket 3 + 4)
4. Wizard/UI (Paket 5)
5. Tests, Live-Check, Doku-Update (`agent_docs/current_state.md`, `agent_docs/priorities.md`)
