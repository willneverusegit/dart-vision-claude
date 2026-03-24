---
name: ground-truth-pipeline
description: Orchestriert den kompletten Ground-Truth-Workflow — von Kamera-Aufnahme ueber interaktive Annotation bis zur Validierung und Batch-Test. Fuehrt die 4 Schritte in der richtigen Reihenfolge aus.
disable-model-invocation: true
---

# Ground Truth Pipeline

Orchestriert den 4-Schritt Ground-Truth-Workflow fuer Dart-Detection-Validierung.

## Schritte

### 1. Video aufnehmen (optional — ueberspringe wenn Video schon vorhanden)

```bash
python scripts/record_camera.py --duration 30 --show
```

Ergebnis: Neues Video in `testvids/` Verzeichnis.

### 2. Ground-Truth annotieren

```bash
python scripts/add_ground_truth.py testvids/<video>.mp4
```

Interaktiver Modus: Fuer jeden Dart-Wurf im Video die tatsaechliche Position markieren.
Ergebnis: Eintraege in `testvids/ground_truth.yaml`.

### 3. Ground-Truth validieren

```bash
python scripts/validate_ground_truth.py
```

Prueft ob alle Eintraege in `ground_truth.yaml` konsistent sind (gueltige Segmente, korrekte Formate).

### 4. Batch-Test gegen Detection

```bash
python scripts/test_all_videos.py --marker-size 100 --marker-spacing 365
```

Vergleicht Detection-Ergebnisse mit Ground-Truth. Gibt Accuracy-Report aus.

## Workflow-Hinweise

- Schritt 1 braucht eine angeschlossene Kamera
- Schritt 2 ist interaktiv (User muss Dart-Positionen klicken)
- Schritte 3-4 sind automatisiert
- Videos (`*.mp4`) NICHT committen — nur `ground_truth.yaml`
- Bei fehlenden Codecs (Linux-VM) schlagen Video-Tests fehl — das ist bekannt und kein Code-Bug
