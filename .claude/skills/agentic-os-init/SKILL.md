---
name: agentic-os-init
description: Bootstrap .agent-memory/ im Projekt — initialisiert das Memory-System mit allen Verzeichnissen, Dateien und Identity-Defaults
---

# Agentic OS Init — Memory-System Bootstrap

Initialisiert das komplette `.agent-memory/`-Verzeichnis fuer ein Projekt.
Nur ausfuehren wenn `.agent-memory/` noch nicht existiert oder ein Reset gewuenscht ist.

## Schritte

### 1. Pruefen ob .agent-memory/ existiert

- Wenn `.agent-memory/ARCHITECTURE.md` existiert und kein Reset gewuenscht:
  - Meldung: "Memory-System bereits initialisiert. Verwende `/agentic-os:status` fuer Health-Check."
  - Abbruch

### 2. Verzeichnisstruktur anlegen

Erstelle folgende Struktur unter `.agent-memory/`:

```
.agent-memory/
├── ARCHITECTURE.md          # System-Dokumentation (Kopie der v3-Architektur)
├── session-summary.md       # Letzte Session-Zusammenfassung
├── identity/
│   ├── soul.md              # Agent-Persoenlichkeit und Arbeitsregeln
│   └── user.md              # User-Praeferenzen
├── heartbeat/
│   ├── skill-registry.json  # Registrierte Skills mit Status
│   └── context-matrix.json  # Token-Budget und Kontext-Prioritaeten
├── orchestrator/
│   ├── trigger-rules.json   # Auto-Trigger-Konfiguration
│   └── orchestrator-log.md  # Orchestrator-Aktivitaeten
├── iterations/
│   ├── iteration-log.md     # Bug/Fix-Protokoll
│   └── errors.json          # Strukturierte Fehler-Daten
├── patterns/
│   ├── patterns.md          # Erkannte Muster (lesbar)
│   └── patterns.json        # Muster (strukturiert)
├── context/
│   ├── project-context.md   # Projekt-Kontext und Tech-Stack
│   └── decisions.json       # Architektur-Entscheidungen
├── quality/
│   ├── test-results.json    # Test-Ergebnisse und Trends
│   ├── code-reviews.json    # Code-Review-Ergebnisse
│   └── quality-score.json   # Aggregierter Qualitaets-Score
├── retrospectives/
│   └── metrics.json         # Langzeit-Metriken
├── evolution/
│   └── benchmarks.json      # Performance-Benchmarks
└── learnings/
    ├── learnings.md          # Cross-Session Learnings
    └── skill-feedback.json   # Skill-Effektivitaet
```

### 3. Identity initialisieren

Erstelle `identity/soul.md` mit folgenden Defaults (anpassbar):

```markdown
# Soul — Agenten-Identitaet

*Initialisiert: <HEUTE>*

## Kernidentitaet
- **Rolle**: Senior Developer und Architektur-Berater
- **Expertise-Level**: Production-Grade
- **Sprache**: Deutsch fuer Kommunikation, Englisch fuer Code

## Kommunikationsstil
- **Kuerze**: 3/5 (kompakt, aber mit Kontext)
- **Proaktivitaet**: Ja, eigenstaendige Vorschlaege erwuenscht
- **Rueckfragen**: Bei Architektur-Entscheidungen und unklaren Requirements
- **Ton**: Sachlich-technisch, direkte Empfehlungen

## Arbeitsverhalten
- **Aenderungsgroesse**: Max 1 Feature / 1 Bug-Fix pro Iteration
- **Tests**: Immer. "Fertig" = "Tests gruen"
- **Git-Stil**: Conventional Commits

## Prioritaeten
1. Korrektheit vor Performance
2. Lesbarkeit vor Cleverness
3. Tests vor Features

## Verbotene Aktionen
- Nie Dateien loeschen ohne Bestaetigung
- Nie Dependencies hinzufuegen ohne Begruendung
- Nie Architektur-Entscheidungen ohne Rueckfrage
- Nie mehr als 3 Dateien gleichzeitig aendern ohne Plan
```

Erstelle `identity/user.md` mit Platzhaltern fuer User-Praeferenzen.

### 4. Context initialisieren

- Lies `CLAUDE.md`, `agent_docs/current_state.md` und `agent_docs/architecture.md` (wenn vorhanden)
- Generiere `context/project-context.md` mit:
  - Projektziel
  - Tech Stack
  - Architektur-Ueberblick
  - Module Status
  - Active Constraints
  - Known Limitations

### 5. Orchestrator konfigurieren

Erstelle `orchestrator/trigger-rules.json`:
```json
{
  "auto_log_iterations": true,
  "auto_review_code": true,
  "auto_run_tests": true,
  "pattern_check_interval": 5,
  "min_severity_for_log": "minor",
  "auto_context_on_decisions": true,
  "retrospective_interval_sessions": 5,
  "verbose_orchestrator_log": false
}
```

### 6. Heartbeat konfigurieren

Erstelle `heartbeat/skill-registry.json` mit allen verfuegbaren Skills aus `.claude/skills/`.
Erstelle `heartbeat/context-matrix.json` mit Token-Budget-Schaetzungen.

### 7. Leere Datenstrukturen anlegen

Alle JSON-Dateien mit leeren/initialen Strukturen befuellen:
- `iterations/errors.json`: `[]`
- `patterns/patterns.json`: `{"patterns": [], "last_extraction": null}`
- `context/decisions.json`: `[]`
- `quality/test-results.json`: `{"runs": [], "trend": "unknown"}`
- `quality/code-reviews.json`: `{"reviews": []}`
- `quality/quality-score.json`: `{"overall": null, "last_update": null}`
- `retrospectives/metrics.json`: `{"sessions": [], "cumulative": {}}`
- `evolution/benchmarks.json`: `{"benchmarks": []}`
- `learnings/skill-feedback.json`: `{"feedback": []}`

### 8. .gitignore pruefen

- Stelle sicher dass `.agent-memory/` NICHT in `.gitignore` steht (Memory soll versioniert werden)
- Stelle sicher dass `~/.claude-memory/` ignoriert wird (global, privat)

### 9. Abschlussmeldung

Zeige:
- Anzahl erstellter Verzeichnisse und Dateien
- Initialisierte Identity-Daten
- Naechster Schritt: `/agentic-os:heartbeat` fuer den ersten Health-Check
