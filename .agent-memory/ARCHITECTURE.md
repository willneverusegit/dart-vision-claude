# Agentic OS v3 — Modulares Skill-System

## Overview

Ein System von 13 Skills in 6 Layern, das einen Coding-Agenten (Claude Code)
systematisch aus jeder Iteration lernen laesst. Skills kommunizieren ausschliesslich
ueber Dateien in `.agent-memory/`.

**Plugin:** `agentic-os-plugin` v3.0.0

## Architektur-Layer

| Layer | Skills | Aufgabe |
|-------|--------|---------|
| 1. Identity | soul-and-identity | Agent-Persoenlichkeit, User-Praeferenzen |
| 2. Orchestration | heartbeat, session-bootstrap, agent-orchestrator | Systemstart, Health-Check, Auto-Steuerung |
| 3. Core | init-memory, sync-context, iteration-logger, pattern-extractor, wrap-up | Memory-Init, Cross-Project-Sync, Logging, Patterns, Session-Ende |
| 4. Quality | code-reviewer, test-validator | Code-Qualitaet, Test-Health |
| 5. Evolution | skill-generator, mutation-engine, retrospective | Skill-Erzeugung, Optimierung, Langzeit-Analyse |
| 6. Transfer | agent-handoff | Context-Sicherung fuer Session-Wechsel |

## Data Flow

```
Session Start
     |
     v
[heartbeat] --> System-Health-Check, Token-Budget, Skill-Registry
     |
     v
[session-bootstrap] --> Liest .agent-memory/, gibt kompaktes Briefing
     |
     v
--- Coding Loop ---
     |
     v
[iteration-logger]     Nach jedem Fix: errors.json, iteration-log.md
[agent-orchestrator]   Erkennt Signale, triggert passende Skills
[code-reviewer]        Nach Code-Aenderungen: Quality-Score
[test-validator]       Nach Tests: Health-Score, Regressionen
     |
     v (alle 5-10 Iterationen)
[pattern-extractor]    errors.json → patterns.json + patterns.md
     |
     v (bei skill_candidate)
[skill-generator]      patterns → generated-skills/
     |
     v
--- Session Ende ---
     |
     v
[wrap-up]              Zusammenfassung, Patterns pushen, Commit-Vorschlag
[agent-handoff]        Context fuer naechste Session sichern
```

## Directory Structure

```
.agent-memory/
├── identity/           # soul.md, user.md
├── heartbeat/          # skill-registry.json, context-matrix.json
├── orchestrator/       # trigger-rules.json, orchestrator-log.md
├── iterations/         # iteration-log.md, errors.json
├── patterns/           # patterns.md, patterns.json
├── context/            # project-context.md, decisions.json
├── quality/            # test-results.json, code-reviews.json, quality-score.json
├── retrospectives/     # retro-<date>.md, metrics.json
├── evolution/          # evals/, mutations/, benchmarks.json
├── generated-skills/   # Auto-erzeugte Skills
├── learnings/          # learnings.md, skill-feedback.json
├── transfer/           # agent-profiles/, handoff-briefing.md
└── session-summary.md

~/.claude-memory/global/ # Cross-Project Memory
├── patterns.json
├── learnings.json
├── agent-profile.json
└── projects.json
```

## Commands

| Command | Funktion |
|---------|----------|
| `/agentic-os:init` | Bootstrap .agent-memory/ im Projekt |
| `/agentic-os:sync` | Lokale/globale Memory synchronisieren |
| `/agentic-os:status` | Memory-System Health anzeigen |

## Agents

| Agent | Model | Aufgabe |
|-------|-------|---------|
| memory-keeper | Haiku | Background: Iteration-Logging, Pattern-Extraktion |
| context-detective | Haiku | Auto-Erkennung von Tech-Stack und Architektur |

## Version

- System version: 3.0
- Basiert auf: agentic-os v3.0 Plugin
- Requires: Persistent local filesystem, text file read/write capability
