# Agent-Workflow: Prozess-Regeln fuer Claude Code

Diese Datei enthaelt die Prozess- und Zeremonie-Regeln fuer den Agenten.
Sie wird aus `CLAUDE.md` referenziert, um das Hauptdokument schlank zu halten.

## Iteration protokollieren

Nach jedem geloesten Bug, jeder nicht-trivialen Fehlerbehebung oder wenn ein Ansatz gescheitert ist:
- Aktiviere `agentic-os:iteration-logger`
- Das erfasst Problem, Root Cause, Loesung und gescheiterte Ansaetze automatisch in `.agent-memory/`
- Auch gescheiterte Ansaetze ohne endgueltige Loesung protokollieren — sie sind wertvoll fuer Pattern-Erkennung

## Architektur-Entscheidungen dokumentieren

- Wenn eine nicht-triviale Designentscheidung getroffen wird: als ADR in `agent_docs/decisions.md` festhalten
- Format: Entscheidung → Warum → Konsequenz
- Vor groesseren Refactorings: bestehende ADRs lesen um keine begruendeten Entscheidungen zu revertieren

## Stolpersteine pflegen

- Wenn ein Bug geloest wird: pruefen ob die Ursache als Pitfall in `agent_docs/pitfalls.md` dokumentiert werden sollte
- Wenn ein unerwartetes Verhalten auftritt: als Pitfall eintragen damit zukuenftige Sessions gewarnt sind
- Format: kurze "Wenn X dann Y"-Regel unter der passenden Kategorie

## Session-Start: Kontext aufbauen

Vor Beginn jeder neuen Arbeitssession:
- Aktiviere `agentic-os:heartbeat` fuer ein kompaktes Projekt-Briefing mit Warnungen und Statistiken
- Lies zusaetzlich die letzten 2-3 Session-Logs in `agent_docs/session_logs/` (neueste zuerst)
- Nimm Erkenntnisse und bekannte Probleme aus den Logs in deine Planung auf
- Wiederhole nicht Fehler die in frueheren Sessions dokumentiert wurden

## Nach Code-Aenderungen: Qualitaetssicherung

Optional nach groesseren Aenderungen oder vor Session-Ende:
- `agentic-os:code-reviewer` — Selbst-Review auf Lesbarkeit, Sicherheit, Projekt-Konventionen
- `agentic-os:test-validator` — nach Test-Runs fuer Trend-Tracking und Regressionserkennung

## Bei Session-Abbruch: Kontext sichern

Wenn eine Session mitten in der Arbeit abgebrochen wird (Context-Limit, User-Unterbrechung):
- Aktiviere `agentic-os:agent-handoff` um den aktuellen Arbeitsstand fuer die naechste Session zu sichern

## Session-Ende: Protokoll und Selbstverbesserung

Am Ende jeder Arbeitssession (oder per `/session-log`):

### Pattern-Analyse (wenn Iterationen geloggt wurden)

- Wenn in dieser Session mindestens 3 Iterationen via `iteration-logger` erfasst wurden:
  - Aktiviere `agentic-os:pattern-extractor` um wiederkehrende Muster zu erkennen
  - Bei gefundenen `skill_candidate`-Patterns: `agentic-os:skill-generator` vorschlagen
- Aktualisiere `.agent-memory/session-summary.md` mit Zusammenfassung der Session

### Session-Log schreiben

Erstelle `agent_docs/session_logs/JJJJ-MM-TT_kurzthema.md` mit:
- **Erledigt:** was gemacht wurde (2-4 Stichpunkte)
- **Probleme:** was schiefging oder unerwartet war
- **Gelernt:** Erkenntnisse fuer zukuenftige Sessions
- **CLAUDE.md-Anpassungen:** was geaendert wurde (falls zutreffend)

Maximal 15 Zeilen. Keine Code-Bloecke.

### CLAUDE.md selbst verbessern

Pruefe am Ende jeder Session ob CLAUDE.md angepasst werden sollte:
- Mussten wiederholt dieselben Dateien gesucht werden? → Lesepfad ergaenzen
- War eine Instruktion unklar und fuehrte zu Umwegen? → Instruktion praezisieren
- Gibt es neue Konventionen die dokumentiert werden sollten? → Regel ergaenzen
- Aenderungen an CLAUDE.md im Session-Log vermerken

## Pflicht: Fortschritt dokumentieren nach jeder erledigten Prioritaet

### 1. `agent_docs/priorities.md` aktualisieren

- Erledigte Prioritaet mit `✅ ERLEDIGT JJJJ-MM-TT` im Titel markieren
- Direkt darunter einen `**Umsetzung:**`-Block einfuegen mit:
  - was konkret gemacht wurde
  - welche Dateien geaendert wurden
- Pflege pro Prioritaet `Verknuepfte Weaknesses:` und `Verknuepfte Entscheidungen:` mit IDs oder `keine`
- Nummerierung NIEMALS aendern — bestehende Nummern bleiben unveraendert
- Neue Schwachstellen oder Follow-up-Aufgaben als neue Prioritaeten HINTEN anhaengen (P11, P12, ...)
- Pflege Rueckverlinkungen zwischen Prioritaeten, `weakness_log.md`, `decision_log.md` und Session-Reports

Format fuer erledigte Prioritaet:
```
## Prioritaet N: Titel (✅ ERLEDIGT 2026-MM-TT)

**Umsetzung:** Was konkret umgesetzt wurde. Geaenderte Dateien: `src/foo.py`, `tests/test_foo.py`.

[bisheriger Inhalt bleibt erhalten]
```

Format fuer neue Prioritaet am Ende:
```
## Prioritaet N: Neues Thema (neu — entdeckt bei Arbeit an PN)

Ziel: ...

Typische Arbeiten:
- ...
```

### 2. `agent_docs/current_state.md` aktualisieren

- Abschnitt "Aktueller Stand" mit neuem Datum und Aenderungen aktualisieren
- Neue Faehigkeiten, behobene Schwachstellen, geaenderte Abhaengigkeiten eintragen
- Testanzahl und Coverage-Stand aktualisieren wenn Zahlen sich geaendert haben

### 3. Neue Schwachstellen suchen und eintragen

Nach jeder Aufgabe aktiv pruefen:
- Gibt es in den geaenderten Dateien TODOs, unbehandelte Edge Cases oder fehlende Tests?
- Wurden durch die Aenderung neue Risiken eingefuehrt?
- Gibt es Folgethemen die logisch auf diese Arbeit aufbauen?
- Falls ja: als neue Prioritaet(en) hinten an `priorities.md` anhaengen

### 4. Neue Schwachstellen als Prioritaeten erfassen (wenn vorhanden)

Wenn bei der Arbeit neue Schwachstellen oder Folgethemen entdeckt werden, als neue Prioritaeten hinten an `priorities.md` anhaengen. Kein kuenstliches Aufblaehen — nur echte Funde eintragen.

## Periodisch: Cross-Project-Learning und Retrospektive

- `agentic-os:sync-context` — nach groesseren Milestones ausfuehren, um Learnings in `~/.claude-memory/global/` zu synchronisieren
- `agentic-os:retrospective` — alle 5-10 Sessions fuer Tiefenanalyse ueber mehrere Sessions hinweg (Metriken, Blind Spots, Verbesserungstrends)
