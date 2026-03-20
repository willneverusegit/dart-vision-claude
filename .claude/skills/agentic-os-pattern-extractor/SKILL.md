---
name: agentic-os-pattern-extractor
description: Erkennt wiederkehrende Muster aus Iterationen und erstellt einen Pattern-Katalog in .agent-memory/patterns/
---

# Agentic OS Pattern Extractor

Analysiert geloggte Iterationen auf wiederkehrende Muster und erstellt
einen aktualisierten Pattern-Katalog.

## Wann ausfuehren

- Wenn mindestens 3-5 Iterationen seit letzter Extraktion geloggt wurden
- Per Session-Ende-Protokoll wenn Iterationen vorhanden
- Per User-Aufruf

## Modi

- **Full Mode**: Alle Iterationen analysieren, kompletten Katalog neu erstellen
- **Lightweight Mode**: Nur neue Iterationen (pattern_extracted: false) analysieren

## Schritte

### 1. Iterationen laden

- Lies `.agent-memory/iterations/errors.json`
- Im Lightweight Mode: filtere auf `pattern_extracted: false`
- Im Full Mode: alle Eintraege

### 2. Clustering durchfuehren

Gruppiere Iterationen nach:
- **File-Hotspot**: Gleiche Datei taucht in mehreren Fehlern auf
- **Category-Cluster**: Gleiche Kategorie (logic, syntax, etc.)
- **Root-Cause-Similarity**: Aehnliche Root Causes
- **Explicit-Seed**: Einzelne Iterationen mit klarem generellem Takeaway

### 3. Patterns ableiten

Fuer jedes Cluster/Seed erstelle ein Pattern:

```markdown
### <Pattern-Titel>
**Confidence:** high/medium/low | **Occurrences:** Nx | **Clustering:** <methode>
<Beschreibung des Musters>
**Action:** Was tun um das Problem zu vermeiden
**Avoid:** Was vermeiden
**Evidence:** <iteration-ids>
```

Confidence-Regeln:
- `high`: >= 3 Vorkommen mit gleichem Root-Cause-Cluster
- `medium`: 2 Vorkommen oder starker Explicit-Seed
- `low`: 1 Vorkommen, aber klarer genereller Takeaway

### 4. Bestehende Patterns aktualisieren

- Lies `.agent-memory/patterns/patterns.json`
- Merge neue Patterns mit bestehenden:
  - Gleiches Pattern gefunden → Occurrences erhoehen, Confidence ggf. hochstufen
  - Neues Pattern → hinzufuegen
  - Kein Duplikat erzeugen

### 5. Skill-Kandidaten markieren

Wenn ein Pattern:
- `confidence: high` hat UND
- eine klare, automatisierbare Action beschreibt UND
- in mindestens 2 verschiedenen Kontexten aufgetreten ist

→ Markiere als `skill_candidate: true` in patterns.json

### 6. patterns.md aktualisieren

Schreibe den kompletten Pattern-Katalog in `.agent-memory/patterns/patterns.md`:
- Gruppiert nach Kategorie (Architecture Rules, Best Practices, Workflow Rules)
- Mit Statistik-Header (Total, High/Medium/Low, Skill Candidates)

### 7. Iterationen als extrahiert markieren

Setze `pattern_extracted: true` fuer alle verarbeiteten Eintraege in errors.json.

### 8. Abschlussmeldung

```
=== Pattern-Extraktion ===
Analysierte Iterationen:  X
Neue Patterns:            Y
Aktualisierte Patterns:   Z
Skill-Kandidaten:         W
Gesamt-Katalog:           N Patterns (H high, M medium, L low)
```
