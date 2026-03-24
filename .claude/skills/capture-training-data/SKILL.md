---
name: capture-training-data
description: Systematically capture dart hit videos and annotate with ground truth data. Trigger when user says: "capture training data", "record new video", "annotate ground truth", "run batch validation", "test hit rate", "improve detection", "new test video", "Trainingsdaten aufnehmen", "neues Video aufnehmen", "Ground Truth annotieren", "Batch-Validierung laufen".
---

# Skill: capture-training-data

Systematisch Dart-Treffer-Videos und Ground-Truth-Daten aufnehmen, um die Single-Cam Dart-Erkennung zu verbessern.

## Wann verwenden

- User will neue Trainings-/Testvideos für die Detection aufnehmen
- Ground-Truth-Annotation eines neuen Videos ist nötig
- Batch-Validierung: wie gut erkennt die aktuelle Pipeline die neuen Videos?
- Schwachstellen der Detection identifizieren (Sektor X funktioniert schlecht)

## Workflow

### Schritt 1: Video aufnehmen

```bash
# Einzelwurf-Clip (empfohlen: 5-10 Sekunden, zeigt Vorbereitungs- + Einschlagsmoment)
python scripts/record_camera.py --duration 10 --show

# Mit expliziter Auflösung (Standardempfehlung für CPU-Budget: 640x480)
python scripts/record_camera.py --duration 10 --resolution 640x480 --show

# Längere Session (mehrere Würfe in einem Clip)
python scripts/record_camera.py --duration 60 --show
```

**Namenskonvention**: Das Script erzeugt automatisch `testvids/rec_YYYYMMDD_HHMMSS.mp4`.

**Aufnahme-Checkliste:**
- [ ] Kamera fest montiert, kein Wackeln
- [ ] Beleuchtung gleichmäßig, keine harten Schatten auf Dartboard
- [ ] ArUco-Marker sichtbar (alle 4 Ecken im Frame)
- [ ] Dart startet außerhalb des Boards, landet dann
- [ ] Nach dem Einschlag kurz (2-3s) stillhalten

### Schritt 2: Ground Truth annotieren

```bash
# Interaktiv — öffnet Video, zeigt Frames, fragt nach Treffer-Info
python scripts/add_ground_truth.py testvids/rec_YYYYMMDD_HHMMSS.mp4

# Einzelwurf direkt angeben (Segment Ring Timestamp)
python scripts/add_ground_truth.py testvids/rec_YYYYMMDD_HHMMSS.mp4 --throw "20 triple 3.2"

# Zusammenfassung aller annotierten Videos anzeigen
python scripts/add_ground_truth.py --summary

# Bestehende Einträge validieren
python scripts/add_ground_truth.py --validate
```

**Annotationsformat** (gespeichert in `testvids/ground_truth.yaml`):
```yaml
rec_YYYYMMDD_HHMMSS.mp4:
  throws:
    - sector: 20
      ring: triple
      timestamp: 3.2   # Sekunden im Video
    - sector: 5
      ring: single
      timestamp: 7.8
```

Gültige `ring`-Werte: `single`, `double`, `triple`, `bull_inner`, `bull_outer`, `miss`
Gültige `sector`-Werte: 1-20, 25 (Bull), 0 (Miss)

### Schritt 3: Qualitätskontrolle

Vor der Batch-Validierung: kurze manuelle Prüfung des Videos.

```bash
# Frame-Diff-Diagnose: zeigt wo Pipeline Motion detektiert
python -m src.diagnose
```

**Qualitätskriterien (manuell prüfen):**
| Kriterium | Gut | Problematisch |
|-----------|-----|---------------|
| Schärfe | Dart-Spitze erkennbar | Verwackelt/unscharf |
| Belichtung | Gleichmäßig, keine Überbelichtung | Harte Schatten, Glare |
| ArUco-Marker | Alle 4 im Frame | Marker teilweise abgeschnitten |
| Kamerawinkel | Frontal oder leicht seitlich | Sehr schräg (>45°) |
| Bewegungsartefakte | Nur Dart bewegt sich | Hintergrund-Bewegung (Personen etc.) |

### Schritt 4: Batch-Validierung

```bash
# Alle Videos in testvids/ gegen aktuelle Detection testen
python scripts/test_all_videos.py --marker-size 100 --marker-spacing 365

# Nur ein bestimmtes Video
python scripts/test_all_videos.py --source-dir testvids --marker-size 100 \
  --max-frames 5000

# Schnell-Test mit weniger Frames (für iteratives Debugging)
python scripts/test_all_videos.py --marker-size 100 --marker-spacing 365 --max-frames 1000
```

**Ausgabe interpretieren:**
- `Hit Rate`: Wie viele annotierte Würfe wurden überhaupt detektiert? Ziel: >80%
- `Score Accuracy`: Wie viele detektierte Treffer haben den richtigen Sektor? Ziel: >70%
- Videos mit <50% Hit Rate → Aufnahmeproblem (Belichtung, Winkel, ArUco)
- Videos mit >80% Hit Rate aber <60% Score Accuracy → Kalibrierproblem

### Schritt 5: Schwachstellen identifizieren

Nach der Batch-Validierung systematisch schauen:
```bash
# Validierungs-Script für detailliertere Fehleranalyse
python scripts/validate_ground_truth.py

# Tip-Detection gegen Diagnostik-Captures prüfen
python scripts/validate_tip_detection.py
```

**Typische Schwachstellen:**
- Bestimmte Sektoren (z.B. 1, 5, 20 oben) → Kalibrierung verfeinern
- Nur Triple-Ring schlägt fehl → Tip-Detection-Threshold anpassen
- Alle Würfe auf einer Seite falsch → Board-Geometrie-Kalibrierung wiederholen

## Vollständiger Beispiel-Workflow

```bash
# 1. Aufnahme: 3 Würfe in 30 Sekunden
python scripts/record_camera.py --duration 30 --show
# → erzeugt testvids/rec_20260324_140000.mp4

# 2. Annotieren
python scripts/add_ground_truth.py testvids/rec_20260324_140000.mp4
# → interaktiv Sektor/Ring/Timestamp eingeben

# 3. Annotierungen validieren
python scripts/add_ground_truth.py --validate

# 4. Batch-Test laufen lassen
python scripts/test_all_videos.py --marker-size 100 --marker-spacing 365

# 5. Ergebnisse analysieren und ggf. Kalibrierung verfeinern
```

## Häufige Probleme

**ArUco nicht erkannt:**
- Marker-Größe prüfen: Standard `100mm`, Abstand `365mm`
- Beleuchtung verbessern
- Auflösung erhöhen: `--resolution 1280x720`

**Dart wird nicht detektiert (Hit Rate = 0%):**
- Pipeline läuft? App muss nicht laufen — `test_all_videos.py` ist standalone
- Kalibrierung fehlt? `config/calibration_config.yaml` prüfen
- Frame-Diff-Threshold zu hoch? Adaptive Thresholds in `config/app_config.yaml` anpassen

**Hohe Hit Rate, falscher Sektor:**
- Board-Geometrie-Kalibrierung wiederholen (Web-UI → Kalibrierung)
- Kalibrierungs-Kette beachten: Lens → Board Pose → Stereo (Reihenfolge!)

**Video zu groß / Storage-Problem:**
- Kurze Clips bevorzugen (5-15s pro Wurf)
- Videos in `testvids/` werden nicht committed (`.gitignore`)
- Nur `ground_truth.yaml` landet im Repo

## Referenzen

- `scripts/record_camera.py` — Kamera-Aufnahme
- `scripts/add_ground_truth.py` — Ground-Truth-Annotation
- `scripts/test_all_videos.py` — Batch-Validierung
- `scripts/validate_ground_truth.py` — Annotations-Validierung
- `scripts/validate_tip_detection.py` — Tip-Detection-Check
- `src/cv/frame_diff_pipeline.py` — Detection-Pipeline
- `src/cv/tip_detection.py` — Dart-Spitzen-Erkennung
- `testvids/ground_truth.yaml` — Ground-Truth-Daten
- `agent_docs/current_state.md` → Abschnitt "Verifizierte Kennzahlen" für aktuelle Hit Rate Baseline
