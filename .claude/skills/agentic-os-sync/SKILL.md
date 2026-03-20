---
name: agentic-os-sync
description: Learnings zwischen Projekt (.agent-memory/) und Global (~/.claude-memory/global/) synchronisieren
---

# Agentic OS Sync — Cross-Project Memory Sync

Synchronisiert Learnings, Patterns und Agent-Profil zwischen dem lokalen
Projekt-Memory (`.agent-memory/`) und dem globalen Memory (`~/.claude-memory/global/`).

## Wann ausfuehren

- Nach groesseren Milestones
- Am Ende einer produktiven Session mit neuen Patterns
- Wenn Learnings auch fuer andere Projekte nuetzlich sein koennten
- Per User-Aufruf `/agentic-os:sync`

## Schritte

### 1. Lokales Memory lesen

Lies und analysiere:
- `.agent-memory/patterns/patterns.json` — erkannte Patterns
- `.agent-memory/learnings/learnings.md` — Session-Learnings
- `.agent-memory/identity/soul.md` — Agent-Profil-Entwicklung
- `.agent-memory/iterations/errors.json` — Fehler-Daten

### 2. Globales Memory pruefen/anlegen

Pruefe ob `~/.claude-memory/global/` existiert.
Wenn nicht, erstelle:
```
~/.claude-memory/global/
├── patterns.json      # Projekt-uebergreifende Patterns
├── learnings.json     # Generelle Learnings
├── agent-profile.json # Aggregiertes Agent-Profil
└── projects.json      # Projekt-Registry
```

### 3. Patterns synchronisieren

Fuer jedes lokale Pattern mit confidence >= medium:
- Pruefe ob ein aehnliches Pattern global existiert (gleiche Kategorie + aehnliche Action)
- Wenn ja: `occurrences` global hochzaehlen, Confidence anpassen
- Wenn nein: neues Pattern global anlegen mit `source: "<project-name>"`

### 4. Learnings synchronisieren

Fuer jedes lokale Learning:
- Pruefe ob es projekt-spezifisch ist (z.B. "pipeline.py Reihenfolge") → nicht syncen
- Pruefe ob es generell nuetzlich ist (z.B. "State-Machines VOR Early-Return") → syncen
- Generelle Learnings in `~/.claude-memory/global/learnings.json` aufnehmen mit Quelle und Datum

### 5. Agent-Profil aktualisieren

- Aktuelle Staerken/Schwaechen aus Quality-Score ableiten
- In `~/.claude-memory/global/agent-profile.json` zusammenfuehren
- Felder: `strengths`, `growth_areas`, `preferred_patterns`, `last_sync`

### 6. Projekt-Registry aktualisieren

In `~/.claude-memory/global/projects.json`:
```json
{
  "projects": [
    {
      "name": "<project-name>",
      "path": "<absolute-path>",
      "last_sync": "<datum>",
      "patterns_contributed": <anzahl>,
      "learnings_contributed": <anzahl>,
      "tech_stack": ["python", "fastapi", "opencv"]
    }
  ]
}
```

### 7. Rueckwaerts-Sync (Global → Lokal)

Pruefe ob globale Patterns fuer dieses Projekt relevant sein koennten:
- Gleicher Tech-Stack?
- Aehnliche Architektur-Patterns?
- Wenn ja: in `.agent-memory/learnings/learnings.md` als "Imported from global" aufnehmen

### 8. Abschlussmeldung

```
=== Sync Ergebnis ===
Richtung:           Lokal → Global
Patterns gesynct:   X (Y neu, Z aktualisiert)
Learnings gesynct:  X (Y generell, Z projekt-spezifisch uebersprungen)
Global → Lokal:     X relevante Patterns importiert
Naechster Sync:     nach naechstem Milestone
```
