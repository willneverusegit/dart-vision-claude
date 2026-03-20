---
name: save-session
description: Kompletter Session-Abschluss — alle 6 Protokolle in einem Aufruf. Nutze dies vor Context-Komprimierung oder am Ende einer Session.
---

# Save Session — All-in-One

Fuehre alle Session-End-Protokolle gebuendelt aus. Jeder Schritt ist Pflicht.

## Schritte

### 1. Iteration Logger
- Aktiviere `/agentic-os-iteration-logger`
- Nur wenn in dieser Session Bugs gefunden/gefixt wurden
- Wenn keine Iterationen: diesen Schritt ueberspringen

### 2. Pattern Extractor
- Aktiviere `/agentic-os-pattern-extractor` (Lightweight Mode)
- Nur wenn Schritt 1 einen neuen Eintrag erzeugt hat
- Wenn keine neuen Iterationen: diesen Schritt ueberspringen

### 3. Skill Generator
- Aktiviere `/agentic-os-skill-generator`
- Nur wenn ein Pattern `skill_candidate: true` hat
- Wenn kein Kandidat: kurz bestaetigen und ueberspringen

### 4. Context Keeper
- Aktiviere `/agentic-os-wrap-up`
- Immer ausfuehren — mindestens project-context.md Status aktualisieren

### 5. Commit
- Aktiviere `commit-commands:commit`
- Alle geaenderten Dateien committen (ausser .coverage, __pycache__, .claude/settings.local.json)

### 6. CLAUDE.md Revision
- Aktiviere `claude-md-management:revise-claude-md`
- Nur aendern wenn echte Learnings aus dieser Session vorliegen
- Keine Aenderung ist auch OK

## Wann diesen Skill nutzen

- Am Ende jeder Session
- Proaktiv wenn die Konversation lang wird (>50 Nachrichten)
- Vor bekannter Context-Komprimierung
- Wenn der User "session beenden", "save session" oder "alles speichern" sagt
