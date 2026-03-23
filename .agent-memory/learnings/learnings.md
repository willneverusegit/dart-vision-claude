# Learnings

## 2026-03-23

- CalibrationManager-Instanzen (Board vs Lens) haben separate `_config` Dicts. Wenn beide unter derselben `camera_id` speichern, ueberschreibt die zweite die erste — `_atomic_save` muss die bestehende Camera-Section mergen statt ersetzen.
- Progress/Status-Endpoints die bei Auto-Modi Seiteneffekte brauchen (z.B. Frame-Sammlung) sind ein wiederkehrendes Pattern. Beim Review von GET-Endpoints auf fehlende Schreiblogik achten.
- Uvicorn mit `--reload` zeigt keine Tracebacks bei 500-Errors wenn der Worker-Prozess nicht korrekt startet — try/except im Endpoint-Body ist noetig fuer Debugging.
