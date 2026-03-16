# Current State

Stand dieser Zusammenfassung: 2026-03-16

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

## Was heute als fortgeschritten, aber noch sensibel gilt

- Multi-Camera-Pipeline
- Stereo-Kalibrierung
- Board-Pose-Kalibrierung
- Triangulation und Voting-Fallback
- Umschalten zwischen Single- und Multi-Cam

## Verifizierte Kennzahlen

- `209` Tests bestanden
- Gesamt-Coverage `54%`
- synthetische Pipeline-Benchmarks fuer `1`, `2` und `3` Kameras innerhalb der definierten KPI-Grenzen

## Wichtige Projektfakten

- `config/calibration_config.yaml` enthaelt eine gueltige Kalibrierung fuer `default`
- `config/multi_cam.yaml` ist strukturell vorbereitet, aber aktuell weitgehend leer
- `multi_cam.yaml` startet standardmaessig im Modus `single`

## Arbeitsannahmen fuer Agents

1. Single-Cam ist der reale Hauptpfad.
2. Multi-Cam ist wichtig, aber braucht defensive Aenderungen.
3. Hardware ist begrenzt. Performance und Stabilitaet gehen vor Feature-Breite.
4. Kalibrierung ist kein Nebenthema, sondern Kernfunktion.

## Was Agents nicht annehmen sollten

- dass Multi-Cam bereits produktionsreif ist
- dass hohe Kameraauflosungen automatisch vertretbar sind
- dass synthetische Benchmarks reale USB-Last komplett abbilden
- dass ungetestete Lifecycle-Aenderungen harmlos sind

## Referenzdokument

Fuer die volle technische Einordnung siehe:

- `PROJEKTSTAND_2026-03-16.md`

