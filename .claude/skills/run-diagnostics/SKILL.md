---
name: run-diagnostics
description: Fuehrt Kamera-Diagnostik durch — vergleicht Bildqualitaet, Diff-Schaerfe und Detection-Ergebnisse zwischen Kameras
disable-model-invocation: true
---

# Kamera-Diagnostik

Fuehre eine standardisierte Kamera-Diagnostik durch:

## Schritte

1. **Diagnostik-Bilder laden**: Lies alle Bilder aus `diagnostics/cam_left/` und `diagnostics/cam_right/` (falls vorhanden)
2. **Diff-Qualitaet pruefen**: Fuehre `python -m src.diagnose` aus und analysiere die Ausgabe
3. **Vergleich erstellen**: Vergleiche Schaerfe, Kontrast und Diff-Qualitaet zwischen den Kameras
4. **Tip-Detection validieren**: Wenn `scripts/validate_tip_detection.py` existiert, fuehre es aus
5. **Ergebnis zusammenfassen**: Erstelle einen kurzen Bericht mit:
   - Kamera-Qualitaetsvergleich (welche Kamera liefert schaerfere Diffs)
   - Detection-Ergebnisse pro Kamera
   - Empfehlungen (Threshold-Anpassung, Fokus-Korrektur, etc.)

## Hinweise

- Nutze `.venv/Scripts/python.exe` falls `.venv` existiert, sonst `python`
- Diagnostik-Bilder liegen typischerweise in `diagnostics/<cam_name>/`
- Ergebnisse NICHT committen — nur als Report ausgeben
