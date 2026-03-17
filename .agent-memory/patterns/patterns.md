# Pattern Catalog

*Last updated: 2026-03-17*
*Total patterns: 5 | High confidence: 0 | Medium: 1 | Low: 4 | Skill candidates: 0*

## Architecture Rules

### pipeline.py ist Hotspot — Reihenfolge-sensitiv
**Confidence:** medium | **Occurrences:** 2x | **Clustering:** file-hotspot
src/cv/pipeline.py taucht in mehreren Fehlern auf. Aufrufreihenfolge in process_frame()
ist kritisch — Early-Returns, Detektor-Updates und Reset-Logik muessen exakt abgestimmt sein.
**Action:** Vor Pipeline-Aenderungen aktuelle Aufrufreihenfolge lesen. Integration-Tests pflegen.
**Avoid:** Blinde Ergaenzung ans Ende; Reset-Methoden ohne alle Detektoren pruefen.
**Evidence:** 2026-03-17-1400-motion-gate-blocks-settling, 2026-03-17-1500-mog2-no-reset-between-turns

---

### State-Machines VOR Early-Return aufrufen
**Confidence:** low | **Occurrences:** 1x | **Clustering:** explicit-seed
State-Machines mit Countdown/Settling muessen vor dem Motion-Gate-Early-Return stehen,
sonst erhalten sie bei has_motion=False nie einen Frame.
**Action:** update()-Aufrufe VOR Early-Return platzieren.
**Avoid:** Updates nach Motion-Gate; annehmen dass "keine Motion" = irrelevanter Frame.
**Evidence:** 2026-03-17-1400-motion-gate-blocks-settling

---

## Best Practices

### Frame-Diff-Baseline nur auf ruhigen Frames setzen
**Confidence:** low | **Occurrences:** 1x | **Clustering:** explicit-seed
Baseline nur bei has_motion=False aktualisieren. Motion-Frame als Baseline hebt den Diff auf.
**Action:** Baseline einfrieren bei has_motion=True.
**Avoid:** Bedingungsloses self._baseline = frame.
**Evidence:** 2026-03-17-1430-baseline-set-on-motion-frame

---

### MOG2 nach semantischem Reset neu initialisieren
**Confidence:** low | **Occurrences:** 1x | **Clustering:** explicit-seed
MOG2 lernt statische Objekte in den Hintergrund. Nach Turn-Reset muss MOG2 zurueckgesetzt werden.
**Action:** motion_detector.reset() in jede semantische Reset-Methode aufnehmen.
**Avoid:** Sensitivity erhoehen statt Reset.
**Evidence:** 2026-03-17-1500-mog2-no-reset-between-turns

---

## Workflow Rules

### JS-Syntax nach Agent-Einfuegungen pruefen
**Confidence:** low | **Occurrences:** 1x | **Clustering:** explicit-seed
Agent-eingefuegte Methoden koennen Klammer-Balance in JS-Klassen zerbrechen. SyntaxError verhindert Parsen — kein Console-Error sichtbar.
**Action:** Nach Agent-Edits an JS sofort `node -c <file>`. Bei undefined Klassen: Syntax vor Caching pruefen.
**Avoid:** Browser-Caching als erste Vermutung; Methoden ohne Klammer-Check einfuegen.
**Evidence:** 2026-03-17-2200-class-brace-misplacement
