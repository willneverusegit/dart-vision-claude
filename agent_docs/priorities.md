# Priorities

Diese Liste beschreibt die bevorzugte Weiterentwicklung aus Sicht des aktuellen Projektstands.

## Prioritaet 1: Pipeline-Lifecycle stabilisieren

Ziel:

- Single- und Multi-Camera sauber start- und stoppbar machen
- keine halbaktiven Hintergrundthreads beim Umschalten

Typische Arbeiten:

- Thread-Handles sauber verwalten
- getrennte Stop-Signale
- Tests fuer wiederholtes Start/Stop

## Prioritaet 2: Kamera-Input kontrollierbar machen

Ziel:

- Laufzeit auf Zielhardware vorhersagbar halten

Typische Arbeiten:

- Default-Aufloesung/FPS konfigurierbar machen
- konservative Defaults setzen
- Fehlermeldungen fuer ungeeignete Kamera-Setups verbessern

## Prioritaet 3: Testabdeckung fuer betriebsnahe Pfade erhoehen

Ziel:

- Lifecycle-, API-, Kalibrierungs- und Multi-Cam-Pfade besser absichern

Typische Arbeiten:

- neue Tests fuer `main.py`, `routes.py`, `pipeline.py`, `multi_camera.py`
- Fehlerpfade und Reconnect-Pfade abdecken

## Prioritaet 4: End-to-End-Verifikation mit Replay verbessern

Ziel:

- echte Nutzbarkeit auf Referenzmaterial absichern

Typische Arbeiten:

- Replay-Clips strukturieren
- Ground Truth erweitern
- Accuracy-Checks fuer Trefferbewertung hinzufuegen

## Prioritaet 5: Multi-Camera haerten

Ziel:

- Multi-Cam von "funktional vorhanden" zu "robust nutzbar" bringen

Typische Arbeiten:

- Setup-Flow fuehren
- Konfigurationspersistenz verbessern
- bessere Diagnose bei fehlender Stereo-/Board-Pose

## Prioritaet 6: Telemetrie und Diagnose ausbauen

Ziel:

- Laufzeitprobleme auf echter Hardware sichtbar machen

Typische Arbeiten:

- Dropped Frames zaehlen und exponieren
- CPU/RAM/Queue-Druck sichtbar machen
- Status-Endpunkte erweitern

## Prioritaet 7: Kalibrierungs-UX verbessern

Ziel:

- Kalibrierung fuer reale Nutzer reproduzierbarer machen

Typische Arbeiten:

- gefuehrte Schrittfolgen
- bessere Fehlermeldungen
- klarere Erfolgskriterien

## Prioritaet 8: Logging betriebstauglicher machen

Ziel:

- Laufzeitfehler und Feldbetrieb besser analysieren koennen

Typische Arbeiten:

- idempotentes Logging-Setup
- optional Rotation/File-Logging
- konsistentere Session- und Kamera-Kontexte in Logs

## Prioritaet 9: Windows-Inbetriebnahme glatter machen

Ziel:

- Setup und Start auf dem Ziel-Laptop vereinfachen

Typische Arbeiten:

- Startskripte
- Diagnose-Checkliste
- klarer Installationspfad

## Prioritaet 10: Bedienbarkeit feinpolieren

Ziel:

- weniger Expertenwissen in der UI voraussetzen

Typische Arbeiten:

- klarere Texte
- bessere Defaults
- gefuehrte Problemloesung in Modal-Dialogen

## Arbeitsregel fuer Agents

Wenn der User nur allgemein nach "weiterentwickeln" fragt und keine andere Richtung vorgibt, beginne oben in der Liste und arbeite nach unten.

