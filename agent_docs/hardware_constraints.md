# Hardware Constraints For Agents

Diese Zusammenfassung leitet sich aus:

- `C:/Users/domes/OneDrive/Desktop/Laptop_hardware/hardware_constraints.md`

ab und uebersetzt die Vorgaben in konkrete Designregeln fuer Coding Agents.

## Zielhardware

- CPU: Intel Core i5-1035G1
- 4 Cores / 8 Threads
- Mobile-U-CPU, thermisch begrenzt
- GPU: integrierte Intel-Grafik, keine CUDA/ROCm
- RAM: konservativ als 8 GB zu behandeln
- Storage frei: etwa 116 GB

## Was das fuer dieses Repo bedeutet

### CPU

- Standardpfad bleibt CPU-only.
- Per-Frame-Arbeit muss begrenzt bleiben.
- Mehrkamera ist teuer und braucht konservative Defaults.
- Dauerlast ist wichtiger als kurzer Peak.

### RAM

- Prozessziel grob: deutlich unter 4 GB bleiben.
- Keine grossen In-Memory-Datensaetze ohne ausdruecklichen Grund.
- Keine ungebremsten Frame-Puffer.

### GPU

- keine Annahme von CUDA, ROCm oder dediziertem VRAM
- keine Features einfuehren, die nur mit GPU sinnvoll laufen

### Storage

- Tempdateien sauber begrenzen und aufraeumen
- keine grossen lokalen Artefakte stillschweigend erzeugen

## Konkrete Designregeln

1. Behalte bounded queues und Streaming-Ansatz bei.
2. Fuehre keine schweren ML-Abhaengigkeiten ein.
3. Verwende konservative Kamera-Defaults.
4. Plane 1 Kamera als Standard, 2 Kameras als realistisches Ausbauziel, 3 Kameras nur mit Vorsicht.
5. Neue Diagnostik sollte leichtgewichtig sein.
6. Wenn du pro Frame neue Berechnungen hinzufuegst, miss zumindest den synthetischen Benchmark erneut.

## Gute Defaults fuer neue Features

- Aufloesung: lieber `640x480` oder `720p` als unkontrollierte Kamera-Defaults
- Queue-Groessen klein halten
- Hintergrundarbeit nur, wenn sie bounded und stoppbar ist
- Logging standardmaessig nach stdout

## Aenderungen, die besonders kritisch zu pruefen sind

- neue Threads
- groessere Kamera-Buffer
- hoehere Default-Aufloesungen
- aufwendige Kalibrierungsroutinen im hot path
- Polling- oder Stream-Loops ohne klare Rate-Limits

## Was Agents vermeiden sollten

- "just add a model" als schnelle Loesung
- uebergrosse Debug-Artefakte
- unbegrenzte Retries ohne Backoff
- API- oder UI-Features, die implizit teurere Runtime-Pfade aktivieren

