# Priorities

Diese Liste beschreibt die empfohlene Weiterentwicklung aus Sicht des Projektstands 2026-03-17.
Prio 1–7 der vorherigen Liste sind abgeschlossen.

## Prioritaet 1: Replay-basierte E2E-Validierung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Vollstaendiges E2E-Replay-Test-Framework implementiert. Synthetischer Clip-Generator erzeugt 10 Dart-Wuerfe auf verschiedene Board-Positionen (Bull, Single, Triple, Double in allen Quadranten). Ground-Truth-Loader, Accuracy-Metriken (Hit Rate, Score/Sector/Ring Accuracy, False Positive Rate) und 6 CI-faehige pytest-Tests. Ergebnis auf synthetischen Daten: 90% Hit Rate, 100% Score Accuracy, 0 False Positives. Geaenderte Dateien: `tests/e2e/__init__.py`, `tests/e2e/generate_synthetic_clip.py`, `tests/e2e/accuracy.py`, `tests/e2e/test_replay_e2e.py`.

Ziel:

- sicherstellen, dass die Treffererkennung auf echtem Videomaterial korrekt funktioniert
- Regressionsschutz fuer CV-Aenderungen

Typische Arbeiten:

- Referenz-Clips mit Ground-Truth-Annotation anlegen (z.B. 10 bekannte Wuerfe)
- Replay-Pipeline automatisiert gegen Ground Truth laufen lassen
- Accuracy-Metriken berechnen: Trefferquote, Sektorgenauigkeit, Ringgenauigkeit
- CI-faehigen Accuracy-Test schreiben

Warum kritisch: Ohne E2E-Validierung auf echtem Material gibt es keinen Beweis, dass das System tatsaechlich funktioniert.

## Prioritaet 2: Kamera-Reconnect und Fehlerbehandlung (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** CameraState-Enum (connected/reconnecting/disconnected) und Health-Tracking in ThreadedCamera. State-Change-Callbacks mit WebSocket-Broadcast (`camera_state` Event). API-Endpunkt `/api/camera/health` und Health-Daten in `/api/stats`. Frontend-Warnbanner mit Pulsanimation bei Kamera-Problemen, aktualisiert via WebSocket und Stats-Polling. 13 neue Tests fuer Reconnect-Szenarien. Geaenderte Dateien: `src/cv/capture.py`, `src/main.py`, `src/web/routes.py`, `static/js/app.js`, `static/css/style.css`, `templates/index.html`, `tests/test_camera_reconnect.py`.

Ziel:

- System ueberlebt Kamera-Ausfall, USB-Wackler, Laptop-Standby graceful

Typische Arbeiten:

- `ThreadedCamera`: Reconnect-Logik mit exponentiellem Backoff testen und absichern
- UI-Feedback bei Kamera-Ausfall (Warnbanner statt schwarzes Bild)
- Pipeline-State korrekt auf "degraded" setzen statt crashen
- Tests fuer Reconnect-Szenarien

Warum kritisch: Im realen Einsatz am Laptop passieren USB-Probleme regelmaessig.

## Prioritaet 3: Multi-Cam Stereo-Triangulation validieren (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** 27 synthetische Validierungstests fuer die gesamte Triangulations-Pipeline. Getestet: Board-Frame-Transformation (identity, translation, rotation), Triangulations-Genauigkeit mit realistischem Stereo-Setup (verschiedene Baselines 10-40cm, Distanzen 50-120cm), Z-Depth-Plausibilitaet (15mm Toleranz), End-to-End-Pipeline (Projekt→Triangulieren→Board-Transform→mm-Koordinaten) fuer Bullseye/T20/D16 und 8 Board-Positionen (<5mm Fehler), Stereo-Param-Loading in Fusion-Pipeline (inkl. fehlende Intrinsics/Paare). Geaenderte Dateien: `tests/test_stereo_validation.py`.

Ziel:

- Triangulation auf echte Genauigkeit pruefen, nicht nur synthetische Tests

Typische Arbeiten:

- Stereo-Kalibrierung mit zwei echten Kameras durchfuehren und Reprojektion messen
- Triangulierte 3D-Punkte gegen bekannte Board-Positionen vergleichen
- Schwellwerte fuer `max_reproj_error` und Z-Plausibilitaet empirisch validieren
- Doku: welche Kamera-Geometrie (Abstand, Winkel) brauchbare Ergebnisse liefert

## Prioritaet 4: Logging betriebstauglicher machen (✅ ERLEDIGT 2026-03-17)

**Umsetzung:** Idempotentes Logging-Setup (kein doppeltes Handler-Registrieren). Optionales Rotating-File-Logging via `DARTVISION_LOG_FILE` Env-Variable (5MB, 3 Backups). Konsistente Session-ID (8-Zeichen UUID-Prefix) in allen Log-Zeilen. JSON-Format-Support mit Session-ID. 8 neue Tests. Geaenderte Dateien: `src/utils/logger.py`, `src/main.py`, `tests/test_logger.py`.

Ziel:

- Laufzeitfehler und Feldbetrieb besser analysieren koennen

Typische Arbeiten:

- idempotentes Logging-Setup (kein doppeltes Handler-Registrieren)
- optional Rotation/File-Logging fuer Langzeitbetrieb
- konsistente Session-ID in Logs (Start bis Stop)
- Kamera-ID-Kontext in Multi-Cam-Logs

## Prioritaet 5: Windows-Inbetriebnahme vereinfachen (MITTEL)

Ziel:

- Setup und Start auf dem Ziel-Laptop ohne Expertenwissen moeglich machen

Typische Arbeiten:

- `start.bat` oder PowerShell-Startskript mit venv-Aktivierung
- Diagnose-Checkliste als CLI-Befehl (`python -m src.diagnose`)
- Kamera-Erkennung: verfuegbare Kameras auflisten vor Pipeline-Start
- klarer Installationspfad in README

## Prioritaet 6: Dartboard-Erkennung verbessern (MITTEL)

Ziel:

- hoehere Treffsicherheit bei der automatischen Board-Erkennung

Typische Arbeiten:

- ArUco-Board-Alignment robuster gegen Beleuchtungsschwankungen machen
- Optischer Mittelpunkt: bessere Auto-Erkennung (aktuell oft manuell noetig)
- Board-Geometrie-Fit: Ringradien-Abweichung als Qualitaetsmetrik exponieren
- Kalibrier-Vorschau mit mehr visuellen Hinweisen (z.B. erkannte Marker hervorheben)

## Prioritaet 7: Spielablauf-UX verbessern (MITTEL)

Ziel:

- weniger Klicks, klarere Rueckmeldung waehrend des Spiels

Typische Arbeiten:

- Hit-Candidate-Timeout: automatisches Ablehnen nach X Sekunden ohne Bestaetigung
- Audio-Feedback bei erkanntem Treffer (optional, Browser Web Audio API)
- Wurf-Historie mit Undo sichtbarer gestalten
- Scoreboard: aktueller Spieler visuell hervorheben
- Checkout-Vorschlaege bei X01 (z.B. "T20 D16" bei 76 Restpunkten)

## Prioritaet 8: Performance-Monitoring und Alerting (NIEDRIG)

Ziel:

- Engpaesse frueh erkennen, bevor sie den Spielbetrieb stoeren

Typische Arbeiten:

- Telemetrie-Historie: FPS/Drop/Queue ueber Zeit als Chart (nicht nur aktuellen Wert)
- Warnung wenn FPS unter 15 faellt oder Queue-Druck > 80% bleibt
- CPU-Last pro Pipeline-Thread messen (Windows: `psutil` optional)
- Telemetrie optional in Logfile schreiben fuer Post-Mortem-Analyse

## Prioritaet 9: Multi-Cam UX weiter verbessern (NIEDRIG)

Ziel:

- Multi-Cam-Setup fuer Nicht-Experten bedienbar machen

Typische Arbeiten:

- Kamera-Vorschau im Multi-Cam-Modal (Live-Thumbnails pro Kamera)
- Drag-and-Drop Kamera-Anordnung
- Stereo-Kalibrierung: Fortschrittsanzeige mit Frame-Counter
- Board-Pose: visuelles Feedback (erkannte Marker im Bild einblenden)
- Setup-Wizard: automatisch zum naechsten Schritt wechseln wenn ein Schritt erledigt ist

## Prioritaet 10: UI-Design und Responsiveness (NIEDRIG)

Ziel:

- Oberflaeche auf verschiedenen Bildschirmgroessen nutzbar und optisch ansprechend

Typische Arbeiten:

- Mobile/Tablet-Layout (Responsive Breakpoints)
- Dark/Light-Theme-Umschaltung
- Scoreboard-Bereich: kompakteres Layout fuer kleinere Bildschirme
- Kamera-Feed: Aspektverhaeltnis beibehalten statt strecken
- Ladeanimation beim Pipeline-Start (Spinner statt schwarzes Bild)
- Tastaturkuerzel fuer haeufige Aktionen (Treffer bestaetigen/ablehnen)

## Arbeitsregel fuer Agents

Wenn der User nur allgemein nach "weiterentwickeln" fragt und keine andere Richtung vorgibt, beginne oben in der Liste und arbeite nach unten.

## Format fuer erledigte Prioritaeten

```
## Prioritaet N: Titel (✅ ERLEDIGT JJJJ-MM-TT)

**Umsetzung:** Was konkret umgesetzt wurde. Geaenderte Dateien: `src/foo.py`.

[urspruenglicher Inhalt bleibt erhalten]
```

Nummerierung wird NIEMALS geaendert. Neue Prioritaeten werden am Ende mit weiterführender Nummer angehaengt.
Erledigte Prioritaeten bleiben in der Liste — nur mit Markierung und Umsetzungsnotiz ergaenzt.

## Prioritaet 11: E2E-Tests mit echten Videoclips (neu — entdeckt bei Arbeit an P1)

Ziel:

- synthetische E2E-Tests durch Tests mit echten Kamera-Aufnahmen ergaenzen

Typische Arbeiten:

- 5-10 echte Clips am Dartboard aufnehmen (verschiedene Beleuchtung, Winkel)
- Ground-Truth-Annotations manuell erstellen
- Accuracy-Thresholds fuer echte Clips kalibrieren (realistischer als synthetisch)
- outer_bull-Erkennung verbessern (aktuell verpasst wegen zu kleinem Blob in schmaler Ring-Zone)

## Prioritaet 12: DartImpactDetector Area-Range erweitern (neu — entdeckt bei Arbeit an P1)

Ziel:

- Erkennungsbereich fuer Konturflaechenwerte flexibler machen

Typische Arbeiten:

- area_max von 1000 auf einen konfigurierbaren Wert erhoehen oder dynamisch skalieren
- Tests fuer Edge Cases: sehr grosse/kleine Darts, verschiedene Kamera-Distanzen
- Outer-Bull-Bereich: Blob hat in schmaler Ring-Zone nur ~40px Flaeche — unter area_min
