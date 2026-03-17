# Self-Improving Agent — Modular Skill System

## Overview

A system of 5 cooperating skills that enables a coding agent (Claude Code, Codex,
or similar) to systematically learn from every iteration. Each skill has a single
responsibility and communicates with others only through shared files in `.agent-memory/`.

**Target environment:** Claude Code with persistent local filesystem (git-tracked project).

## Data Flow

```
Session Start
     │
     ▼
┌──────────────────┐
│ session-bootstrap │  Reads all .md + .json from .agent-memory/
│                   │  Produces compact briefing
│                   │  Identifies active warnings
└────────┬─────────┘
         │
         ▼
   ┌─ Coding Loop ──────────────────────────────────┐
   │                                                  │
   │  User Prompt → Agent works → Result              │
   │       │                            │             │
   │       ▼                            ▼             │
   │  ┌──────────────┐    ┌──────────────────┐       │
   │  │iteration-     │    │ context-keeper    │       │
   │  │logger         │    │                   │       │
   │  │               │    │ Writes:           │       │
   │  │ Writes:       │    │  context.md       │       │
   │  │  errors.json  │    │  decisions.json   │       │
   │  │  iteration-   │    └──────────────────┘       │
   │  │  log.md       │                               │
   │  └──────┬───────┘                                │
   │         │                                        │
   │         ▼ (every 5-10 iterations or on request)  │
   │  ┌──────────────────┐                            │
   │  │ pattern-extractor │                           │
   │  │                   │                           │
   │  │ Reads: errors.json│                           │
   │  │ Writes:           │                           │
   │  │  patterns.json    │                           │
   │  │  patterns.md      │                           │
   │  └──────┬───────────┘                            │
   │         │                                        │
   │         ▼ (when skill_candidate: true)           │
   │  ┌──────────────────┐                            │
   │  │ skill-generator   │                           │
   │  │                   │                           │
   │  │ Reads: patterns   │                           │
   │  │ Writes:           │                           │
   │  │  generated-skills/│                           │
   │  └──────────────────┘                            │
   │                                                  │
   └──────────────────────────────────────────────────┘
         │
         ▼ (on explicit "session beenden")
┌──────────────────┐
│ session-bootstrap │  Writes session-summary.md
│ (end mode)       │
└──────────────────┘
```

## Directory Structure

```
.agent-memory/
├── iterations/
│   ├── iteration-log.md            # Append-only narrative log
│   ├── errors.json                 # Structured error database
│   └── archive/                    # Archived old entries (>200)
│       └── errors-YYYY-Q.json
├── patterns/
│   ├── patterns.md                 # Human-readable pattern overview
│   └── patterns.json               # Structured pattern database
├── context/
│   ├── project-context.md          # Living project overview (overwritten)
│   └── decisions.json              # Append-only decision history
├── generated-skills/               # Skills produced by skill-generator
│   └── <skill-name>/
│       └── SKILL.md
└── session-summary.md              # Written at session end, read at session start
```

## Skill Responsibilities

| Skill | Reads | Writes | Trigger |
|-------|-------|--------|---------|
| session-bootstrap | Everything | session-summary.md (end only) | Session start / end |
| iteration-logger | errors.json (dedup check) | errors.json, iteration-log.md | After each fix cycle |
| context-keeper | decisions.json (consistency) | project-context.md, decisions.json | Architecture/stack decisions |
| pattern-extractor | errors.json, patterns.json | patterns.json, patterns.md | Every 5-10 iterations |
| skill-generator | patterns.json, errors.json | generated-skills/ | When skill_candidate found |

## Storage Strategy

| Data type | Format | Purpose | Growth model |
|-----------|--------|---------|-------------|
| Narrative context | `.md` | Agent reads at session start | Overwritten (context) or append (log) |
| Error database | `.json` | Searchable, filterable, dedup | Append-only, archive at 200 entries |
| Pattern catalog | `.json` + `.md` | Machine-queryable + human-readable | Updated in-place, max ~30 patterns |
| Decision history | `.json` | "Why did we choose X?" | Append-only, status-managed |
| Generated skills | `.md` | Reusable agent instructions | Created once, versioned if updated |

## Scaling Limits

| File | Soft limit | Action when exceeded |
|------|-----------|---------------------|
| errors.json | 200 entries | Archive entries >90 days old |
| patterns.json | 30 patterns | Review and consolidate low-confidence |
| decisions.json | 50 active entries | Review for superseded decisions |
| iteration-log.md | 500 lines | Start new monthly file |

## Interaction Rules

1. **No circular dependencies**: Skills communicate only through files, never call each other
2. **Read before write**: Always read existing data before modifying (dedup, consistency)
3. **Single writer**: Each file has at most one skill that writes to it (see table above)
4. **Git-friendly**: All files are text-based and diff-friendly. Recommend committing
   `.agent-memory/` changes with descriptive messages.

## Agent Compatibility

| Agent | File access | Skill loading | Notes |
|-------|-----------|---------------|-------|
| Claude Code | `cat`, `Read` tool | CLAUDE.md reference | Primary target |
| Codex | Workspace files | System prompt / reference | Tested |
| Other agents | Varies | Manual integration | Requires file read capability |

## Version

- System version: 2.0
- Requires: Persistent local filesystem, text file read/write capability
- Recommended: Git-tracked project directory
