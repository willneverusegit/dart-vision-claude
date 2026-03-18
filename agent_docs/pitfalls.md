# Bekannte Stolpersteine (Pitfalls)

Konkrete "Wenn X dann Y"-Regeln, gesammelt aus geloesten Bugs und Session-Erfahrungen.
Waechst organisch — jeder Agent fuegt neue Erkenntnisse hinzu.

---

## Threading & Lifecycle

- **ThreadedCamera-Reconnect:** Immer `stop_event` pruefen bevor ein neuer Thread gestartet wird — sonst Thread-Leak
- **Pipeline-Stop:** Sowohl eigenes `stop_event` als auch App-`shutdown_event` pruefen in `_run_*` Funktionen
- **Single↔Multi-Wechsel:** Alten Pipeline-Thread sauber stoppen (Signal + Join) bevor neuer gestartet wird

### Mode-Switch State Cleanup (KRITISCH)

Jeder Moduswechsel (Single→Multi, Multi→Single, Restart) MUSS `_full_state_reset(state)` aus `src/main.py` aufrufen. Ohne diesen Reset bleiben folgende Zustaende stehen und vergiften die naechste Pipeline:

1. **pending_hits** — Hit-Kandidaten aus dem alten Modus bleiben sichtbar, Scoring trifft falsche Pipeline
2. **latest_frame / multi_latest_frames** — Alte Frames aus anderem Kameramodus
3. **recent_detections / detection_timestamps** — Ring-Buffer mit veralteten Daten

**Regeln:**
- `_full_state_reset()` ist die einzige Quelle der Wahrheit fuer transiente State-Bereinigung
- Niemals `multi_pipeline_running = True` setzen BEVOR `multi.start()` erfolgreich war (verhindert Race Condition mit Polling-Loop)
- `MultiCameraPipeline.start()` ist atomar: bei Fehler werden alle bereits gestarteten Kameras zurueckgerollt
- `_wait_for_camera_release()` statt blindem `sleep(0.5)` verwenden — prueft ob Kamera wirklich frei ist
- `stop_pipeline_thread()` versucht Force-Release wenn Thread-Join timeoutet

**Wo wird `_full_state_reset()` aufgerufen:**
- `routes.py: single_start` — nach Stop aller Pipelines, vor Start
- `routes.py: multi_start` — nach Stop der Single-Pipeline, vor Multi-Start
- `routes.py: multi_stop` — nach Stop der Multi-Pipeline, vor optionalem Single-Restart
- `main.py: _run_multi_pipeline finally` — bei Multi-Exit (normal oder Fehler)

## Konfiguration

- **Kalibrierungsdateien:** Niemals ueberschreiben ohne Backup — sind echte Betriebsdaten
- **multi_cam.yaml:** Speichert `last_cameras` — beim Testen nicht mit Dummy-Werten ueberschreiben

## Tests

- **Coverage-Rueckgang:** Wenn neue Funktionalitaet ohne Tests hinzugefuegt wird, sinkt die Coverage — immer Tests mitschreiben
- **Multi-Cam-Tests:** Sind fragiler als Single-Cam — bei Aenderungen immer separat laufen lassen
- **E2E-Replay-Tests:** Pipeline laedt automatisch die echte Kalibrierung aus config/ — fuer synthetische Tests muss Remapper und Geometry explizit auf Identity/Default ueberschrieben werden nach pipeline.start()
- **MOG2 Background Model:** Braucht ~15-20 Frames Warmup auf schwarzem Hintergrund bevor Motion zuverlaessig erkannt wird

## Windows-spezifisch

- **Pfade:** Immer mit Forward-Slashes oder `os.path.join` arbeiten, nie hartcodierte Backslashes
- **USB-Kameras:** Koennen beim Standby disconnecten — Reconnect-Logik ist Pflicht

## CV / Frame-Diff-Detektor

- **Motion-Gate vor frame_diff_detector.update():** SETTLING-State braucht bewegungsfreie Frames zum Herunterzaehlen. update() MUSS vor dem Motion-Gate-Early-Return aufgerufen werden.
- **settle_frames zu niedrig:** Dart wackelt noch wenn Diff berechnet wird → falsche Position. Empfehlung: 5 Frames bei 30fps (~167ms Wartezeit).
- **diff_threshold zu niedrig (<30):** Beleuchtungsrauschen erzeugt False Positives. Empfehlung: 50 als Startwert, bei dunkler Umgebung auf 30 senken.
- **Baseline nach Kalibrierungswechsel veraltet:** Nach Homographie-Aenderung muss frame_diff_detector.reset() aufgerufen werden. reset_turn() deckt das ab solange pipeline.refresh_remapper() danach auch reset_turn() triggert.
- **Nur Grayscale-Frames:** FrameDiffDetector erwartet 2D-Arrays (Grayscale). Farb-Frames loesen einen ValueError aus. Die Pipeline uebergibt bereits den CLAHE-enhanced Grayscale-Frame.

---

*Neue Eintraege immer unter der passenden Kategorie einfuegen. Neue Kategorie anlegen wenn noetig.*
