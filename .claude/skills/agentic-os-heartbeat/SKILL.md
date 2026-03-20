---
name: agentic-os-heartbeat
description: Session-Start Health-Check — kompaktes Projekt-Briefing mit Warnungen, Statistiken und Kontext-Loading
---

# Agentic OS Heartbeat — Session-Start Briefing

Wird bei jedem Session-Start ausgefuehrt. Gibt ein kompaktes Briefing mit
dem aktuellen Projektzustand, offenen Warnungen und relevanten Statistiken.

## Wann ausfuehren

- **Automatisch** bei jedem Session-Start (hoechste Prioritaet laut CLAUDE.md)
- Per User-Aufruf wenn Kontext verloren ging

## Schritte

### 1. Memory-System Health pruefen

- Pruefe ob `.agent-memory/` existiert
- Wenn nicht: Meldung "Memory nicht initialisiert — `/agentic-os:init` empfohlen" und weiter mit reduziertem Briefing

### 2. Letzte Session laden

Lies `.agent-memory/session-summary.md`:
- Was wurde zuletzt gemacht?
- Welche offenen Punkte gibt es?
- Welche naechsten Schritte waren geplant?

### 3. Projekt-Kontext laden

Lies `.agent-memory/context/project-context.md`:
- Tech Stack
- Module Status
- Active Constraints

### 4. Warnungen sammeln

Pruefe auf Warnungen:
- **Veralteter Kontext**: `session-summary.md` aelter als 3 Tage?
- **Offene Iterationen**: Ungeloeste Fehler in `iterations/errors.json`?
- **Pattern-Stau**: Mehr als 5 Iterationen seit letzter Pattern-Extraktion?
- **Qualitaet**: `quality/quality-score.json` unter Schwellwert?
- **Test-Regression**: Fallender Trend in `quality/test-results.json`?
- **Fehlende Dateien**: Pflicht-Dateien in `.agent-memory/` fehlen?

### 5. Prioritaeten laden

Lies `agent_docs/priorities.md`:
- Oberste nicht-erledigte Prioritaet identifizieren
- Anzahl offener vs. erledigter Prioritaeten zaehlen

### 6. Aktuelle Session-Logs pruefen

Lies die letzten 2-3 Session-Logs aus `agent_docs/session_logs/` (neueste zuerst):
- Erkenntnisse und bekannte Probleme extrahieren
- In Briefing einbeziehen

### 7. Skill-Registry aktualisieren

- Scanne `.claude/skills/` auf neue oder entfernte Skills
- Aktualisiere `heartbeat/skill-registry.json`
- Melde neue oder fehlende Skills

### 8. Heartbeat-Log schreiben

Trage in `.agent-memory/heartbeat/heartbeat-log.md` ein:
```markdown
## <DATUM> <UHRZEIT>
- Status: OK / WARNUNG
- Warnungen: <liste oder "keine">
- Naechste Prioritaet: P<N> — <Titel>
- Session-Kontext geladen: ja/nein
```

### 9. Kompaktes Briefing ausgeben

Format (max 20 Zeilen):

```
=== Heartbeat ===
Projekt:      <Name> (<Tech-Stack>)
Letzte Session: <Datum> — <Thema>
Status:       OK / X Warnungen

Offene Punkte:
- <aus session-summary.md>

Naechste Prioritaet: P<N> — <Titel>
Kritikalitaet: <HOCH/MITTEL/NIEDRIG>

Warnungen:
- <warnung 1>
- <warnung 2>

Statistik:
- Tests: <anzahl> | Coverage: <prozent>
- Iterationen: <anzahl> | Patterns: <anzahl>
- Skills: <anzahl> aktiv
```

### 10. Context-Matrix aktualisieren

Aktualisiere `heartbeat/context-matrix.json` mit:
- Geschaetztem Token-Budget fuer diese Session
- Prioritaet der zu ladenden Kontexte
- Welche Dateien bereits geladen wurden
