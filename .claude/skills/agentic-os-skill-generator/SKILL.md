---
name: agentic-os-skill-generator
description: Generiert neue Skills aus erkannten Patterns mit skill_candidate-Flag
---

# Agentic OS Skill Generator

Erzeugt automatisch neue Claude Code Skills aus Patterns die als
`skill_candidate: true` markiert sind.

## Wann ausfuehren

- Wenn Pattern-Extraktion einen `skill_candidate` findet
- Per `/save-session` wenn Kandidaten vorhanden
- Per User-Aufruf

## Schritte

### 1. Skill-Kandidaten laden

Lies `.agent-memory/patterns/patterns.json` und filtere auf `skill_candidate: true`.

### 2. Fuer jeden Kandidaten pruefen

- Gibt es bereits einen Skill der dieses Pattern abdeckt?
  - Ja → ueberspringen
  - Nein → weiter

### 3. Skill-Spezifikation ableiten

Aus dem Pattern ableiten:
- **Name**: kurzer, sprechender Skill-Name
- **Trigger**: Wann soll der Skill aktiviert werden?
- **Schritte**: Was soll der Skill tun?
- **Input**: Welche Dateien/Daten braucht er?
- **Output**: Was produziert er?

### 4. SKILL.md generieren

Erstelle `.claude/skills/<name>/SKILL.md`:

```markdown
---
name: <name>
description: <beschreibung — generiert aus Pattern "<pattern-titel>">
---

# <Name>

*Auto-generiert aus Pattern: <pattern-titel>*
*Confidence: <confidence> | Occurrences: <anzahl>*

## Trigger
<wann aktivieren>

## Schritte
### 1. <schritt>
...
```

### 5. Skill-Registry aktualisieren

Fuege den neuen Skill in `.agent-memory/heartbeat/skill-registry.json` hinzu
mit `status: "generated"`.

### 6. Pattern als verarbeitet markieren

Setze `skill_generated: true` im Pattern in `patterns.json`.

### 7. Feedback-Loop vorbereiten

Erstelle Eintrag in `.agent-memory/learnings/skill-feedback.json`:

```json
{
  "skill": "<name>",
  "generated_from": "<pattern-id>",
  "date": "<datum>",
  "activations": 0,
  "effectiveness": null,
  "user_feedback": null
}
```

### 8. Abschlussmeldung

```
=== Skill Generator ===
Kandidaten geprueft:  X
Skills generiert:     Y
- <skill-name-1>: <beschreibung>
Bereits abgedeckt:    Z (uebersprungen)
```
