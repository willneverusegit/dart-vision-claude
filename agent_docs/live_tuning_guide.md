# Live-Tuning-Guide (P37)

Anleitung zum Tunen der CV-Parameter am echten Dartboard.

## Vorbereitung

1. `python -m src.main` starten
2. Browser oeffnen (http://localhost:8000)
3. **"Tune"-Button** klicken → CV Tuning Panel oeffnet sich
4. **Diagnostics-Checkbox** aktivieren → speichert Diff-Masken als PNG + JSON in `./diagnostics/`

## Die 5 Tuning-Parameter

Alle live per Slider aenderbar, Wirkung sofort.

| Parameter | Default | Range | Wirkung |
|-----------|---------|-------|---------|
| `diff_threshold` | 50 | 10–150 | Mindest-Helligkeitsunterschied (0–255) zwischen Baseline und Post-Wurf-Frame. Hoeher = weniger sensitiv. |
| `settle_frames` | 5 | 1–15 | Anzahl ruhiger Frames bevor Diff berechnet wird. Bei 30 FPS: 5 Frames = ~167ms Wartezeit nach letzter Bewegung. |
| `min_diff_area` | 50 | 10–500 | Mindest-Blobgroesse in px² — filtert kleine Rausch-Artefakte. |
| `max_diff_area` | 8000 | 1000–20000 | Maximale Blobgroesse in px² — filtert globale Lichtaenderungen (Fenster, Lampe an/aus). |
| `min_elongation` | 1.5 | 1.0–5.0 | Mindest-Seitenverhaeltnis des Blobs. Darts sind laenglich (>2.0), Schatten eher rund (~1.0). |
| `motion_threshold` | 200 | 50–2000 | Anzahl weisser Pixel in der Motion-Maske um Bewegung zu erkennen. **Kritisch:** Zu hoch = Wuerfe werden gar nicht erst registriert. |

## Szenarien-Matrix

### Gute Beleuchtung, stabil (Idealfall)

Defaults sollten funktionieren. Starte hier und pruefe mit 5 Testwuerfen.

```
diff_threshold = 50
settle_frames  = 5
min_diff_area  = 50
max_diff_area  = 8000
min_elongation = 1.5
```

### Schwache Beleuchtung

**Problem:** Diff zwischen Baseline und Post-Wurf-Frame ist zu gering, Darts werden verpasst.
**Loesung:** `diff_threshold` runter auf **25–35**. Eventuell `min_diff_area` auf **30–40** senken.

### Wechselndes Licht (Fenster, Wolken)

**Problem:** Globale Helligkeitsaenderungen erzeugen grosse Diff-Blobs → Fehldetektionen.
**Loesung:**
- `diff_threshold` hoch auf **70–90**
- `max_diff_area` runter auf **4000–5000** (grosse Blobs = Licht, nicht Dart)
- `min_elongation` auf **2.0** (Lichtaenderungen sind eher flaechig/rund)

### Kamera nah am Board (<40cm)

**Problem:** Darts erscheinen gross im Bild, ueberschreiten `max_diff_area`.
**Loesung:** `max_diff_area` hoch auf **12000–15000**.

### Kamera weit vom Board (>80cm)

**Problem:** Darts erscheinen klein, unterschreiten `min_diff_area`.
**Loesung:** `min_diff_area` runter auf **20–30**.

### Schnelle Fehldetektionen (Erkennung triggert waehrend Wurf)

**Problem:** `settle_frames` zu niedrig — System erkennt Dart bevor er steckt.
**Loesung:** `settle_frames` hoch auf **7–10**.
**Nachteil:** Laengerer Delay zwischen Wurf und Erkennung.

### Erkennung zu langsam (langer Delay)

**Problem:** `settle_frames` zu hoch — zu viel Wartezeit.
**Loesung:** `settle_frames` runter auf **3**.
**Risiko:** Mehr Fehldetektionen moeglich.

### Schatten-Artefakte

**Problem:** Schatten des Darts oder der Hand wird als separater Dart erkannt.
**Loesung:** `min_elongation` hoch auf **2.0–2.5** (Schatten sind runder als Darts).

### Darts von vorne / schraeg (wenig elongiert)

**Problem:** Dart-Silhouette erscheint fast rund, wird wegen `min_elongation` abgelehnt.
**Loesung:** `min_elongation` runter auf **1.2**.

### Wuerfe werden gar nicht erkannt (kein Hit-Candidate)

**Problem:** `motion_threshold` zu hoch — MOG2 erkennt die Wurfbewegung nicht, Baseline wird staendig aktualisiert (inkl. Dart), Diff findet nichts.
**Loesung:** `motion_threshold` runter auf **100–150**. Bei kleinen/weit entfernten Kameras sogar auf **50–80**.
**Zu niedrig:** Jede kleine Bewegung (Hand, Koerper) triggert den Erkennungszyklus → mehr False Positives.

## Latenz-Problem loesen (haeufigster Fall)

Das System wartet nach einem Wurf bis **keine Bewegung mehr erkannt wird** (MOG2 motion < motion_threshold), zaehlt dann `settle_frames` ruhige Frames, und macht erst dann den Diff.

**Wenn Erkennung zu spaet kommt (>1s nach Wurf):**

1. **motion_threshold senken** (z.B. 80–120) → System erkennt "Ruhe" frueher
2. **settle_frames auf 1–2** → kuerzere Wartezeit nach erkannter Ruhe
3. Beides zusammen kann Latenz von >1s auf ~200ms bringen

**Wenn Erkennung gar nicht kommt:**
- motion_threshold zu hoch → System sieht nie genug Bewegung um ueberhaupt zu triggern
- Oder: Kamera-Qualitaet zu schlecht → Bild zu verrauscht, MOG2 reagiert nicht sinnvoll

**Achtung:** Zu niedrige motion_threshold fuehrt zu Fehldetektionen waehrend der Arm noch im Bild ist!

### Deine Diagnostik-Analyse (17.03.2026)

Ergebnisse mit Kamera ID 0 (schlechtere Kamera), settle_frames=2, diff_threshold=50:
- **Erkennung funktioniert** wenn sie triggert — Konturen sind sauber, Tip wird gefunden
- **Area:** 346–861 px² (gut im Bereich min/max)
- **Confidence:** 0.69–1.0 (gut)
- **Problem:** Latenz — die Erkennung kommt zu spaet

→ **Empfehlung:** Bessere Kamera verwenden UND motion_threshold anpassen.

## Tuning-Workflow (Schritt fuer Schritt)

1. **Defaults laden** — App starten, nichts aendern
2. **Diagnostics aktivieren** — Checkbox im Tune-Panel
3. **5 Testwuerfe** auf verschiedene Board-Bereiche (Bull, Triple, Rand)
4. **Ergebnis pruefen:**
   - Alle 5 erkannt? → Defaults OK
   - Fehldetektionen? → Diagnostics-Ordner pruefen
   - Wuerfe verpasst? → Diagnostics zeigt ob kein Blob oder zu kleiner Blob
5. **Einen Parameter aendern**, 3 Wuerfe wiederholen
6. **Iterieren** bis zufrieden
7. **Gute Werte notieren** (Screenshot vom Tune-Panel oder Werte aufschreiben)
8. **Diagnostics deaktivieren** wenn fertig (spart I/O)

## Diagnostics-Dateien lesen

Im `./diagnostics/` Ordner nach jeder Erkennung:

| Datei | Inhalt |
|-------|--------|
| `baseline_*.png` | Referenzbild ohne Dart (vor dem Wurf) |
| `diff_mask_*.png` | Differenzbild (weiss = Aenderung zum Baseline) |
| `contour_*.png` | Erkannte Konturen mit Elongation-Wert und Flaeche |
| `metadata_*.json` | Alle Parameter, Messwerte, Blob-Details |

### Diagnostics interpretieren

- **Diff-Maske komplett schwarz:** diff_threshold zu hoch oder kein sichtbarer Unterschied → Beleuchtung/Kameraposition pruefen
- **Diff-Maske grossflaechig weiss:** Globale Lichtaenderung → diff_threshold erhoehen, max_diff_area senken
- **Kleiner weisser Blob, aber kein Treffer:** min_diff_area zu hoch oder min_elongation zu streng
- **Mehrere Blobs:** Schatten oder Reflexion → min_elongation erhoehen

## Empfohlene Startwerte nach Umgebung

| Umgebung | diff_threshold | settle_frames | min_diff_area | max_diff_area | min_elongation |
|----------|---------------|---------------|---------------|---------------|----------------|
| Ideal (LED-Ring, stabil) | 50 | 5 | 50 | 8000 | 1.5 |
| Schwach beleuchtet | 30 | 5 | 30 | 8000 | 1.5 |
| Tageslicht (wechselnd) | 80 | 6 | 50 | 4000 | 2.0 |
| Kamera nah (<40cm) | 50 | 5 | 80 | 15000 | 1.5 |
| Kamera fern (>80cm) | 40 | 5 | 20 | 5000 | 1.3 |

## Nach dem Tuning

Wenn gute Werte gefunden: in `src/cv/diff_detector.py` als neue Defaults uebernehmen (oder mir die Werte mitteilen, dann mache ich das).
