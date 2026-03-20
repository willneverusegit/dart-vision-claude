---
name: agentic-os-status
description: System-Health und Memory-Status anzeigen — prueft alle .agent-memory/ Dateien und Skills auf Vollstaendigkeit und Aktualitaet
---

# Agentic OS Status — System Health Check

Zeigt den aktuellen Zustand des Memory-Systems und aller Skills an.

## Schritte

### 1. Memory-System pruefen

- Pruefe ob `.agent-memory/` existiert
- Wenn nicht: Meldung "Memory nicht initialisiert. Fuehre `/agentic-os:init` aus." und Abbruch

### 2. Verzeichnisstruktur validieren

Pruefe ob alle erwarteten Verzeichnisse und Dateien existieren:

| Pfad | Pflicht | Zweck |
|------|---------|-------|
| `identity/soul.md` | ja | Agent-Identitaet |
| `identity/user.md` | ja | User-Praeferenzen |
| `heartbeat/skill-registry.json` | ja | Skill-Registry |
| `heartbeat/context-matrix.json` | ja | Token-Budget |
| `orchestrator/trigger-rules.json` | ja | Trigger-Regeln |
| `orchestrator/orchestrator-log.md` | nein | Orchestrator-Log |
| `iterations/iteration-log.md` | ja | Iteration-Protokoll |
| `iterations/errors.json` | ja | Fehler-Daten |
| `patterns/patterns.md` | ja | Pattern-Katalog |
| `patterns/patterns.json` | ja | Pattern-Daten |
| `context/project-context.md` | ja | Projekt-Kontext |
| `context/decisions.json` | ja | Entscheidungen |
| `quality/test-results.json` | ja | Test-Ergebnisse |
| `quality/code-reviews.json` | ja | Code-Reviews |
| `quality/quality-score.json` | ja | Qualitaets-Score |
| `retrospectives/metrics.json` | ja | Langzeit-Metriken |
| `evolution/benchmarks.json` | ja | Benchmarks |
| `learnings/learnings.md` | ja | Learnings |
| `learnings/skill-feedback.json` | ja | Skill-Feedback |
| `session-summary.md` | ja | Session-Zusammenfassung |
| `ARCHITECTURE.md` | ja | System-Doku |

Fehlende Pflicht-Dateien als Warnung anzeigen.

### 3. Aktualitaet pruefen

Fuer jede Datei das Aenderungsdatum auslesen und anzeigen:
- **Aktuell** (< 1 Tag): gruen
- **Veraltet** (1-7 Tage): gelb
- **Stark veraltet** (> 7 Tage): rot

### 4. Skill-Registry validieren

- Lies `heartbeat/skill-registry.json`
- Vergleiche mit tatsaechlich vorhandenen Skills in `.claude/skills/`
- Melde fehlende, ueberzaehlige oder deaktivierte Skills

### 5. Daten-Integritaet pruefen

- JSON-Dateien auf valides JSON pruefen
- Leere Dateien markieren
- `iterations/errors.json`: Anzahl Eintraege anzeigen
- `patterns/patterns.json`: Anzahl Patterns und Confidence-Verteilung
- `quality/test-results.json`: Letzter Test-Run und Trend
- `quality/quality-score.json`: Aktueller Score

### 6. Statistiken berechnen

Zeige kompakte Zusammenfassung:

```
=== Agentic OS Status ===
Memory:       initialisiert (v3.0)
Dateien:      X/Y vorhanden (Z veraltet)
Skills:       X registriert, Y aktiv
Iterationen:  X geloggt (letzte: DATUM)
Patterns:     X erkannt (Y high confidence)
Qualitaet:    Score X/100
Tests:        Trend: stabil/steigend/fallend
Session:      Letzte: DATUM — THEMA
```

### 7. Empfehlungen

Basierend auf dem Status, gib Empfehlungen:
- Fehlende Dateien → `/agentic-os:init` vorschlagen
- Veralteter Kontext → Aktualisierung vorschlagen
- Keine Iterationen geloggt → Hinweis auf Workflow
- Keine Patterns → Hinweis auf Pattern-Extraktion nach 5+ Iterationen
- Kein Heartbeat heute → `/agentic-os:heartbeat` vorschlagen
