---
name: agentic-os-wrap-up
description: Session-Ende Context-Keeper — aktualisiert project-context.md, session-summary.md und sichert Architektur-Entscheidungen
---

# Agentic OS Wrap-Up — Context Keeper

Sichert den Session-Kontext fuer zukuenftige Sessions. Aktualisiert
Projekt-Kontext, Session-Summary und Entscheidungen.

## Wann ausfuehren

- Am Ende jeder Session (Pflicht-Bestandteil von `/session-log` und `/save-session`)
- Vor Context-Komprimierung
- Nach groesseren Architektur-Entscheidungen

## Schritte

### 1. Aenderungen der Session erfassen

Sammle aus der aktuellen Session:
- Welche Dateien wurden geaendert?
- Welche Features wurden hinzugefuegt/gefixt?
- Welche Architektur-Entscheidungen wurden getroffen?
- Welche Tests wurden geschrieben/geaendert?

### 2. project-context.md aktualisieren

Lies `.agent-memory/context/project-context.md` und aktualisiere:
- **Module Status**: Neue Module oder Statusaenderungen eintragen
- **Key Decisions**: Neue Entscheidungen als Einzeiler hinzufuegen
- **Known Limitations**: Geloeste Limitationen entfernen, neue hinzufuegen
- **Open Questions**: Beantwortete Fragen markieren, neue hinzufuegen
- **Last updated**: Datum und Kurzbeschreibung aktualisieren

### 3. decisions.json aktualisieren

Wenn Architektur-Entscheidungen getroffen wurden, fuege in `.agent-memory/context/decisions.json` hinzu:

```json
{
  "id": "<datum>-<slug>",
  "date": "<datum>",
  "decision": "<was wurde entschieden>",
  "rationale": "<warum>",
  "consequence": "<was folgt daraus>",
  "files_affected": ["<pfad>"],
  "reversible": true/false
}
```

### 4. session-summary.md schreiben

Ueberschreibe `.agent-memory/session-summary.md` mit aktuellem Stand:

```markdown
# Letzte Session

*Datum: <HEUTE>*

## Was wurde gemacht
- <stichpunkt 1>
- <stichpunkt 2>

## Offene Punkte
- <punkt 1>

## Naechste Schritte
1. <schritt 1>
2. <schritt 2>

## Statistik
- Iterationen: <anzahl>
- Fehler: <anzahl neue>
- Tests: <zusammenfassung>
- Neue Patterns: <anzahl>
```

### 5. Quality-Score aktualisieren

Aktualisiere `.agent-memory/quality/quality-score.json`:

```json
{
  "overall": <0-100>,
  "last_update": "<datum>",
  "dimensions": {
    "test_coverage": <0-100>,
    "code_quality": <0-100>,
    "documentation": <0-100>,
    "architecture": <0-100>
  }
}
```

Scoring-Regeln:
- Test-Coverage: direkt aus pytest --cov
- Code-Quality: basierend auf Ruff-Ergebnissen und Code-Reviews
- Documentation: Vollstaendigkeit von Docstrings, agent_docs, CLAUDE.md
- Architecture: Basierend auf ADR-Pflege und Modularitaet

### 6. Abschlussmeldung

```
Context gesichert:
- project-context.md: aktualisiert
- session-summary.md: geschrieben
- decisions.json: +X Entscheidungen
- quality-score: X/100
```
