# CLAUDE.md

Claude-Code-spezifischer Einstieg fuer dieses Repository.

## Erst lesen

1. `README.md`
2. `PROJEKTSTAND_2026-03-16.md`
3. `agent_docs/INDEX.md`
4. `agent_docs/claude_code.md`
5. `AGENTS.md`

## Wichtige Repo-Regeln

- Single-Camera ist der stabile Hauptpfad.
- Multi-Camera ist wichtig, aber noch nicht der robusteste Teil des Systems.
- CPU-only ist gewollt. Keine GPU-Pflicht oder schweren ML-Stacks ohne expliziten Userwunsch.
- Halte Hardwarelast konservativ.
- Kalibrierungsdateien nicht leichtfertig aendern.
- Tests fuer betroffene Bereiche immer mitdenken.

## Wie Claude Code hier arbeiten soll

- lies die relevanten Dokumente zuerst, bevor du groessere Refactorings vorschlaegst
- halte Antworten knapp, aber konkret
- wenn eine Aufgabe mehrere Teilsysteme beruehrt, beschreibe kurz die betroffenen Bereiche vor der Umsetzung
- aendere sensible Dateien wie `src/main.py`, `src/web/routes.py` und `src/cv/multi_camera.py` nur mit defensiver Begruendung
- behandle Multi-Cam standardmaessig als High-Risk-Bereich

## Wenn du an etwas arbeitest

- lies die betroffenen Module und vorhandenen Tests zuerst
- halte Aenderungen klein und pruefbar
- verschlechtere nicht aus Versehen Startpfad, Kamera-Lifecycle oder Kalibrierung
- aktualisiere Doku mit, wenn Workflows oder Prioritaeten sich aendern

## Claude-Code-spezifische Lesepfade

### Bei Single-Cam oder allgemeiner Runtime-Arbeit

1. `agent_docs/current_state.md`
2. `agent_docs/architecture.md`
3. `agent_docs/development_workflow.md`

### Bei Multi-Cam

1. `agent_docs/current_state.md`
2. `agent_docs/architecture.md`
3. `agent_docs/priorities.md`
4. `MULTI_CAM_INSTRUCTIONS.md`
5. `MULTI_CAM_WORKFLOW.md`

### Bei Kalibrierung

1. `agent_docs/current_state.md`
2. `agent_docs/hardware_constraints.md`
3. `agent_docs/development_workflow.md`

## Naechste sinnvolle Entwicklungsfelder

1. Pipeline-Lifecycle haerten
2. Kameraauflosung/FPS kontrollierbar machen
3. Coverage fuer betriebsnahe Pfade steigern
4. Replay- und Hardware-validierte E2E-Checks ausbauen
5. Multi-Cam robuster machen

## Abschlussformat

Nenne am Ende immer:

- welche Dateien du geaendert hast
- welche Tests du ausgefuehrt hast
- welche Risiken oder offenen Punkte bleiben
