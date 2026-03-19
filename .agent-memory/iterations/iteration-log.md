# Iteration Log

---

## [2026-03-19 13:15] Multi-Cam-Kalibrierung war auf Single-Cam-Routen verdrahtet

**Category:** logic | **Severity:** major | **Attempts:** 2

**Problem:** Im Multi-Cam-Kalibriermodus funktionierte nur der manuelle Board-Pfad. ArUco, Lens, Status, ROI/Overlay und Optical-Center liefen in eine generische Meldung "Pipeline nicht aktiv".

**Root Cause:** Die betroffenen Kalibrier-Endpunkte verwendeten nur `app_state["pipeline"]`. Im Multi-Cam-Betrieb lebt die aktive Live-Pipeline aber in `app_state["multi_pipeline"]`, und das Frontend uebergab keinen expliziten Kamera-Kontext.

**Solution:** In `src/web/routes.py` eine Multi-Cam-faehige Aufloesung der aktiven Kalibrierpipeline pro `camera_id` eingebaut und das Kalibriermodal in `static/js/app.js`/`templates/index.html` um Kamera-Auswahl sowie zielbezogene Statusmeldungen erweitert. Dazu 5 neue Regressionstests fuer die Auswahl der richtigen Sub-Pipeline.

**Failed Approaches:**
- Nur implizit auf die erste Multi-Cam-Sub-Pipeline fallen lassen - funktional, aber fuer Nutzer und gespeicherte per-Kamera-Kalibrierungen zu intransparent

**Takeaway:** Live-Kalibrierung ist im Multi-Cam-Modus immer kamera-spezifisch. Backend und Frontend muessen denselben Kamera-Kontext explizit tragen; ein stiller Single-Cam-Fallback ist hier ein Designfehler.

---

## [2026-03-17 14:00] Motion-Gate blockiert SETTLING-State

**Category:** architecture | **Severity:** major | **Attempts:** 1

**Problem:** frame_diff_detector.update() war im Plan nach dem Motion-Gate-Early-Return platziert — SETTLING-State bekam keine bewegungsfreien Frames.

**Root Cause:** pipeline.process_frame() gab bei has_motion=False fruehzeitig zurueck. Der neue Detektor wurde danach eingebaut und blieb dauerhaft in SETTLING haengen.

**Solution:** update() vor den Early-Return verschoben. Jeder Frame erreicht den Detektor.

**Failed Approaches:** keine (im Plan-Review erkannt, vor Implementierung behoben)

**Takeaway:** State-Machines mit Countdown-Logik muessen VOR jedem Gate-Early-Return aufgerufen werden — nicht danach.

---

## [2026-03-17 14:30] Baseline wird auf Motion-Frame gesetzt

**Category:** logic | **Severity:** major | **Attempts:** 1

**Problem:** _handle_idle() setzte Baseline bedingungslos — auch auf den Dart-in-Flight-Frame. Diff gegen eigene Baseline = kein Unterschied.

**Root Cause:** self._baseline = frame.copy() stand vor der has_motion-Pruefung.

**Solution:** Baseline nur aktualisieren wenn has_motion=False. Bei Motion: Baseline einfrieren.

**Failed Approaches:** keine (vom Implementer beim Schreiben erkannt)

**Takeaway:** Bei Frame-Diff-Detektoren immer: Baseline = letzter ruhiger Frame. Jede Bewegung friert die Baseline ein.

---

## [2026-03-17 15:00] MOG2 kein Reset zwischen Turns

**Category:** logic | **Severity:** major | **Attempts:** 1

**Problem:** Nach reset_turn() wurde kein has_motion=True mehr erzeugt. Zweiter Wurf blieb unerkannt.

**Root Cause:** MOG2 adaptiert den Hintergrund fortlaufend. Der erste Dart wurde Teil des Hintergrundmodells. Naechster Wurf erzeugte kein Signal mehr.

**Solution:** motion_detector.reset() in reset_turn() aufgenommen.

**Failed Approaches:** keine (vom Implementer beim Testen erkannt)

**Takeaway:** MOG2 muss nach jedem semantischen Turn-Reset neu initialisiert werden, sonst sind neue Darts "unsichtbar".

---

## [2026-03-17 19:00] Centroid ≠ Dartspitze — Tip-Detection noetig

**Category:** architecture | **Severity:** minor | **Attempts:** 1

**Problem:** Centroid liegt ~28px von der Spitze entfernt (Richtung Flights). Bei Segmentgrenzen fuehrt das zu falschem Scoring.

**Root Cause:** Flaechenschwerpunkt einer Dart-Silhouette liegt naturgemaess zur Mitte, weil Flights viel mehr Flaeche haben als die Spitze.

**Solution:** minAreaRect → Achse bestimmen → Kontur halbieren → schmalere Haelfte = Tip-Seite → aeusserster Punkt = Tip. Validiert auf 18 echten Aufnahmen.

**Failed Approaches:** keine (datengetriebener Ansatz — erst Aufnahmen, dann Algorithmus)

**Takeaway:** Daten-zuerst-Ansatz spart Iterationen. Erst echte Aufnahmen sammeln, dann Algorithmus auf realen Daten designen statt blind synthetisch zu entwickeln.

---

## [2026-03-17 19:10] Kamera-Qualitaet variiert stark

**Category:** environment | **Severity:** minor | **Attempts:** 1

**Problem:** cam_left deutlich schaerfer als cam_right. Board-Draehte als Diff-Artefakte bei scharfer Kamera.

**Root Cause:** Unterschiedliche Kameramodelle/Fokus.

**Solution:** Dokumentiert als P26. Algorithmus funktioniert auf beiden Qualitaetsstufen (18/18).

**Failed Approaches:** keine

**Takeaway:** Bei Multi-Cam-Setups: frueh Diagnostics einbauen um Kamera-Unterschiede zu erkennen. Algorithmen muessen auf verschiedenen Qualitaetsstufen robust sein.

---

## [2026-03-17 22:00] Ueberzaehlige Klammer bricht DartApp-Klasse ab

**Category:** syntax | **Severity:** critical | **Attempts:** 3

**Problem:** CV-Tuning-Methoden standen ausserhalb der DartApp-Klasse — SyntaxError verhinderte das Laden der gesamten JS-Datei. Tune-Button nicht funktional.

**Root Cause:** Agent-generierter Code hatte eine ueberzaehlige schliessende Klammer } vor den neuen Methoden. Die Klasse endete zu frueh.

**Solution:** Ueberzaehlige } entfernt. Verifiziert mit node -c.

**Failed Approaches:**
- Browser-Caching vermutet — ?v=2 Cache-Busting half nicht
- Preview-Tool-Limitation vermutet — tatsaechlich war der Code fehlerhaft

**Takeaway:** Nach dem Einfuegen von Methoden in JS-Klassen immer `node -c <file>` ausfuehren. Nicht sofort Browser-Caching verdaechtigen — erst Syntax pruefen.

---
