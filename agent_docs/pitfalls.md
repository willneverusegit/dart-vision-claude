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

---

*Neue Eintraege immer unter der passenden Kategorie einfuegen. Neue Kategorie anlegen wenn noetig.*
