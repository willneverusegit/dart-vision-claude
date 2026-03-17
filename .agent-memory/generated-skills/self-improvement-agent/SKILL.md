---
name: self-improvement-agent
description: Use when a user asks to activate self-improvement workflow, continue work from prior sessions, extract repeated patterns, record lessons learned, update persistent context, or generate reusable skills from stable workflows.
---

# Self Improvement Agent

## Workflow

1. Bootstrap context.
   - Read `.agent-memory/context/project-context.md`, `.agent-memory/context/decisions.json`, `.agent-memory/patterns/patterns.md`, recent `.agent-memory/iterations/errors.json`, and `.agent-memory/session-summary.md`.
2. Extract patterns.
   - Cluster current or recent iteration records and refresh `.agent-memory/patterns/patterns.json` plus `.agent-memory/patterns/patterns.md`.
3. Log meaningful iteration.
   - Record trigger, problem, root cause, solution, failed approaches, changed files, and takeaway in `.agent-memory/iterations/errors.json` and `.agent-memory/iterations/iteration-log.md`.
4. Update durable context.
   - Refresh `.agent-memory/context/project-context.md`.
   - Add or supersede records in `.agent-memory/context/decisions.json`.
5. Generate reusable skill only if stable.
   - If workflow is repeatable, create `.agent-memory/generated-skills/<skill-name>/SKILL.md` and `agents/openai.yaml`.
   - Keep generated skills deterministic and installable.

## Guardrails

- Keep updates compact and concrete.
- Do not invent recurrence when evidence is weak.
- Do not create a new skill for one-off tasks.
- Keep decision records reversible unless clearly architectural.

## Example

User asks: "Activate self-improvement and start with codebase analysis."

- Bootstrap memory and summarize current state.
- Add/update priorities from analysis.
- Log the iteration and refresh patterns/context.
- If no composed skill exists, generate `self-improvement-agent`.
