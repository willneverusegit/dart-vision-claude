# Multi-Cam Safety & Visibility (P30 + P31 + P33)

Design-Spec fuer Cluster 1 der Multi-Cam-Hardening-Initiative.

## Kontext

Multi-Cam ist funktional, aber hat drei Luecken:
- Kamera-Fehler sind im UI unsichtbar
- Stereo-Kalibrierung laesst sich ohne gueltige Intrinsics starten (stille Fehler)
- Stale Detections im Buffer werden nicht aufgeraeumt; keine Frame-Drop-Sichtbarkeit

Ziel: robusterer Multi-Cam-Betrieb auf 2-Kamera-Setup (i5-Laptop, Windows).

## P31: Intrinsics Validation

### Backend

**Neue Funktion in `src/cv/stereo_calibration.py`:**

```python
def validate_intrinsics(camera_id: str, config_path: str = "config/calibration_config.yaml") -> tuple[bool, str]:
    """Laedt Kamera-Config und prueft ob camera_matrix (3x3) und dist_coeffs (Nx1)
    vorhanden und gueltig sind. Nutzt gleichen Config-Pfad wie load_config().
    Returns (valid, error_message)."""
```

Liest direkt aus der YAML-Config (gleicher Pfad wie `_load_extrinsics()`). Kein eigener CalibrationManager noetig.

**Integration:**
- `/api/calibration/stereo`: Pre-Flight-Check vor Frame-Capture. Bei Fehler: HTTP 400 mit deutscher Meldung ("Bitte Linsen-Kalibrierung fuer {cam_id} zuerst durchfuehren").
- `/api/multi/readiness`: Neues Feld `intrinsics_valid: bool` pro Kamera im Response.

### Frontend

- Stereo-Calibrate-Button im Multi-Cam-Modal: `disabled` + Tooltip wenn Intrinsics fehlen.
- Info kommt aus bestehendem Readiness-Polling (`_fetchReadiness()`).

### Tests

- validate_intrinsics mit gueltigen/ungueltigen/fehlenden Matrizen
- API-Test: /api/calibration/stereo ohne Intrinsics → 400
- Readiness-Response enthaelt intrinsics_valid Feld

### Dateien

- `src/cv/stereo_calibration.py` — validate_intrinsics()
- `src/web/routes.py` — Pre-Flight in stereo-Endpunkt, Readiness-Erweiterung
- `static/js/app.js` — Button-Disable-Logik
- `tests/test_intrinsics_validation.py`

---

## P30: Camera Error Reporting to UI

### Backend

**MultiCameraPipeline Erweiterungen in `src/cv/multi_camera.py`:**

- `_error_log: collections.deque(maxlen=50)` — Thread-safe Ring-Buffer
- `_error_callback: Optional[Callable]` — wird von routes.py gesetzt (Dependency Injection), ruft WebSocket-Broadcast auf
- `log_camera_error(camera_id, error_type, message)` — fuegt Eintrag in deque hinzu (thread-safe), ruft `_error_callback` auf falls gesetzt
- In `_run_pipeline_loop`: Exception-Handler ruft `log_camera_error()` auf

**Error-Types (definiert als Enum oder Konstanten):**
- `capture_failed` — Frame konnte nicht gelesen werden
- `pipeline_error` — Exception in Pipeline-Verarbeitung
- `reconnecting` — Kamera versucht Reconnect
- `disconnected` — Kamera nicht erreichbar

**Threading-Bridge:** `_error_callback` wird in `setup_routes()` als Lambda gesetzt, das `broadcast()` aufruft. Da `broadcast()` async ist, nutzt der Callback `asyncio.run_coroutine_threadsafe(broadcast(...), loop)` mit dem Event-Loop aus main.py.

**WebSocket-Event:**
```json
{
  "type": "camera_error",
  "camera_id": "cam_left",
  "error_type": "capture_failed",
  "message": "Frame konnte nicht gelesen werden",
  "timestamp": "2026-03-17T14:30:00Z"
}
```

**Neuer Endpunkt:**
- `GET /api/multi/errors` — gibt letzte 50 Fehler zurueck (fuer initiales Laden beim Modal-Oeffnen)

**Status-Erweiterung:**
- `/api/multi/status` bekommt pro Kamera ein `state` Feld: "ok" | "warning" | "error"

### Frontend

- **Status-Badges** pro Kamera im Multi-Cam-Modal: gruen (ok), gelb (warning/reconnecting), rot (error/disconnected)
- **Toast-Notification** via `_showError()` bei neuem `camera_error` WebSocket-Event
- **Error-Liste** im Modal unterhalb der Kamera-Eintraege (letzte 10, scrollbar, neueste oben)

### Tests

- log_camera_error fuegt korrekt ein und begrenzt auf 50
- /api/multi/errors liefert Fehler-Liste
- /api/multi/status enthaelt state pro Kamera
- WebSocket-Event wird bei Fehler gesendet

### Dateien

- `src/cv/multi_camera.py` — Error-Log, log_camera_error()
- `src/web/routes.py` — /api/multi/errors Endpunkt, Status-Erweiterung
- `static/js/app.js` — Badges, Toast, Error-Liste
- `static/css/style.css` — Badge-Styles
- `tests/test_camera_error_reporting.py`

---

## P33: FPS/Buffer Governors

### Korrektur gegenueber erstem Entwurf

`_detection_buffer` ist ein `dict[str, dict]` — 1 Eintrag pro Kamera, kein Queue.
Es gibt kein "unbounded growth"-Problem. Der tatsaechliche Bedarf:

1. **Stale-Detection-Cleanup:** Detections aelter als `MAX_DETECTION_TIME_DIFF_S` bleiben im Buffer und werden bei jedem `_try_fuse()` Zyklus mitgeschleppt. Explizites Aufraeeumen fehlt.
2. **Frame-Drop-Sichtbarkeit:** Wenn die Pipeline Frames nicht schnell genug verarbeitet, gibt es keinen Zaehler.
3. **Konfigurierbare FPS-Vorbereitung:** `_TARGET_FPS = 30` ist hardcoded.

### Backend

**Stale-Detection-Cleanup in `_try_fuse()`:**
- Vor dem Fusions-Versuch: Detections aelter als 500ms aus `_detection_buffer` entfernen
- Entfernte Stale-Detections zaehlen als `_stale_drops[camera_id] += 1`

**Frame-Drop-Tracking:**
- `_frame_drops: dict[str, int]` — Zaehler pro Kamera (Frames die in `_run_pipeline_loop` nicht verarbeitet werden konnten)
- `_stale_drops: dict[str, int]` — Zaehler fuer Stale-Detection-Cleanups
- Exponiert ueber `/api/multi/status` Response:
  ```json
  {
    "cameras": {
      "cam_left": {"fps": 28.5, "frame_drops": 0, "stale_drops": 2}
    }
  }
  ```
- Zaehler werden bei Pipeline-Restart zurueckgesetzt

**Config in `config/multi_cam.yaml`:**
```yaml
governors:
  target_fps: 30           # vorbereitet fuer 3+ Kameras, aktuell nicht aktiv genutzt
  stale_detection_ms: 500  # Detections aelter als dies werden verworfen
```

### Kein aggressives FPS-Limiting

`_TARGET_FPS = 30` bleibt als Konstante. `target_fps` Config-Feld wird nur vorbereitet, nicht aktiv genutzt. Bei CPU-Problemen spaeter aktivierbar.

### Tests

- Stale-Detection wird nach 500ms aus Buffer entfernt
- stale_drops Zaehler inkrementiert korrekt
- /api/multi/status enthaelt frame_drops und stale_drops
- Config-Loading fuer governors-Sektion
- Zaehler-Reset bei Pipeline-Restart

### Dateien

- `src/cv/multi_camera.py` — Stale-Cleanup, Drop-Tracking
- `src/web/routes.py` — Status-Erweiterung
- `config/multi_cam.yaml` — governors-Sektion
- `tests/test_buffer_governors.py`

---

## Unified `/api/multi/status` Response Schema

Nach P30 + P33 sieht die kombinierte Response so aus:

```json
{
  "cameras": {
    "cam_left": {
      "fps": 28.5,
      "state": "ok",
      "frame_drops": 0,
      "stale_drops": 2,
      "calibration": {"lens": true, "board": true, "pose": true}
    },
    "cam_right": {
      "fps": 25.1,
      "state": "warning",
      "frame_drops": 1,
      "stale_drops": 0,
      "calibration": {"lens": true, "board": false, "pose": false}
    }
  },
  "errors": []
}
```

**State-Ableitung:**
- `"ok"` — keine Fehler, FPS > 10
- `"warning"` — Reconnecting, oder stale_drops > 5 in letzter Minute, oder FPS < 10
- `"error"` — disconnected oder wiederholte capture_failed

## Implementierungsreihenfolge

1. **P31** (Intrinsics Validation) — keine Abhaengigkeiten, isoliert
2. **P33** (Buffer Governors) — keine Abhaengigkeiten, isoliert
3. **P30** (Error Reporting) — baut auf stabilem Buffer auf, nutzt Status-Erweiterung

P31 und P33 sind parallelisierbar.

## Nicht im Scope

- Stereo-Wizard (P29) — naechster Cluster
- Triangulation-Telemetrie (P32) — naechster Cluster
- 3+ Camera Fusion (P34) — naechster Cluster
- FPS-Limiting/Throttling — nur bei Bedarf spaeter
