# Bekannte Stolpersteine (Pitfalls)

Konkrete "Wenn X dann Y"-Regeln, gesammelt aus geloesten Bugs und Session-Erfahrungen.
Waechst organisch — jeder Agent fuegt neue Erkenntnisse hinzu.

---

## Threading & Lifecycle

- **ThreadedCamera-Reconnect:** Immer `stop_event` pruefen bevor ein neuer Thread gestartet wird — sonst Thread-Leak
- **Pipeline-Stop:** Sowohl eigenes `stop_event` als auch App-`shutdown_event` pruefen in `_run_*` Funktionen
- **Single↔Multi-Wechsel:** Alten Pipeline-Thread sauber stoppen (Signal + Join) bevor neuer gestartet wird

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
