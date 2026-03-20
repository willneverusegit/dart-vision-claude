---
name: agentic-os-sync-context
description: Cross-Project-Learning — synchronisiert Learnings nach Milestones in globalen Memory-Speicher
---

# Agentic OS Sync Context — Cross-Project Learning

Synchronisiert projektspezifische Learnings in den globalen Memory-Speicher
(`~/.claude-memory/global/`). Identisch mit `/agentic-os:sync`, aber
explizit fuer den Milestone-getriggerten Aufruf aus `agent_workflow.md`.

## Wann ausfuehren

- Nach groesseren Milestones (mehrere Prioritaeten erledigt)
- Wenn generelle Learnings entstanden sind die projekt-uebergreifend gelten
- Per User-Aufruf

## Verhalten

Dieser Skill delegiert an `/agentic-os:sync` mit identischer Logik.
Er existiert als separater Einstiegspunkt fuer die Referenz in `agent_workflow.md`:

> `agentic-os:sync-context` — nach groesseren Milestones ausfuehren

## Schritte

Fuehre die gleichen Schritte wie `/agentic-os:sync` aus:

1. Lokales Memory lesen
2. Globales Memory pruefen/anlegen
3. Patterns synchronisieren (nur confidence >= medium)
4. Learnings synchronisieren (nur generell nuetzliche)
5. Agent-Profil aktualisieren
6. Projekt-Registry aktualisieren
7. Rueckwaerts-Sync (Global → Lokal)
8. Abschlussmeldung
