---
name: agentic-os-code-reviewer
description: Selbst-Review auf Lesbarkeit, Sicherheit, Projekt-Konventionen und Code-Qualitaet
---

# Agentic OS Code Reviewer

Fuehrt ein systematisches Selbst-Review der geaenderten Dateien durch.
Prueft auf Lesbarkeit, Sicherheit, Konventionen und haeufige Fehler.

## Wann ausfuehren

- Nach groesseren Code-Aenderungen (optional)
- Vor Session-Ende
- Automatisch durch Orchestrator wenn `auto_review_code: true`

## Schritte

### 1. Geaenderte Dateien identifizieren

```bash
git diff --name-only HEAD~1   # letzte Aenderungen
git diff --name-only           # ungestagete Aenderungen
```

### 2. Review-Checkliste durchgehen

Fuer jede geaenderte Datei pruefen:

**Korrektheit:**
- [ ] Logik korrekt? Edge Cases beruecksichtigt?
- [ ] Error Handling vorhanden wo noetig?
- [ ] Return Types konsistent?

**Sicherheit:**
- [ ] Keine Command Injection (subprocess, os.system)?
- [ ] Keine SQL Injection?
- [ ] Keine unsanitisierten User-Inputs in Templates?
- [ ] Keine hartcodierten Secrets/Credentials?

**Projekt-Konventionen (aus CLAUDE.md):**
- [ ] CPU-only? Keine GPU/ML Dependencies?
- [ ] Deutsche Fehlermeldungen in API-Endpunkten?
- [ ] Frontend: `_showError()` statt `_showToast`?
- [ ] Sensible Dateien (main.py, routes.py, multi_camera.py) defensiv geaendert?
- [ ] testvids/*.mp4 nicht committet?

**Lesbarkeit:**
- [ ] Variablennamen sprechend?
- [ ] Funktionen nicht zu lang (< 50 Zeilen)?
- [ ] Keine unnoetige Komplexitaet?

**Tests:**
- [ ] Neue Funktionalitaet getestet?
- [ ] Bestehende Tests noch gruen?

### 3. Review-Ergebnis dokumentieren

Schreibe in `.agent-memory/quality/code-reviews.json`:

```json
{
  "date": "<datum>",
  "files_reviewed": ["<pfad>"],
  "issues_found": [
    {
      "file": "<pfad>",
      "line": <nummer>,
      "severity": "critical|major|minor|style",
      "category": "security|logic|convention|readability",
      "description": "<beschreibung>",
      "suggestion": "<vorschlag>",
      "fixed": false
    }
  ],
  "score": <0-100>
}
```

### 4. Issues fixen

Fuer jedes gefundene Issue:
- **Critical/Major**: Sofort fixen
- **Minor**: Fixen wenn sinnvoll
- **Style**: Notieren, nicht unbedingt fixen

### 5. Abschlussmeldung

```
=== Code Review ===
Dateien reviewed:    X
Issues gefunden:     Y (Z critical, W major)
Issues gefixt:       A
Review-Score:        B/100
```
