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
- lies `agent_docs/pitfalls.md` wenn du in einem Bereich arbeitest der dort dokumentiert ist
- halte Aenderungen klein und pruefbar
- verschlechtere nicht aus Versehen Startpfad, Kamera-Lifecycle oder Kalibrierung
- aktualisiere Doku mit, wenn Workflows oder Prioritaeten sich aendern

## Architektur-Entscheidungen dokumentieren

- Wenn eine nicht-triviale Designentscheidung getroffen wird: als ADR in `agent_docs/decisions.md` festhalten
- Format: Entscheidung → Warum → Konsequenz
- Vor groesseren Refactorings: bestehende ADRs lesen um keine begruendeten Entscheidungen zu revertieren

## Stolpersteine pflegen

- Wenn ein Bug geloest wird: pruefen ob die Ursache als Pitfall in `agent_docs/pitfalls.md` dokumentiert werden sollte
- Wenn ein unerwartetes Verhalten auftritt: als Pitfall eintragen damit zukuenftige Sessions gewarnt sind
- Format: kurze "Wenn X dann Y"-Regel unter der passenden Kategorie

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

## Session-Start: Kontext aufbauen

Vor Beginn jeder neuen Arbeitssession:
- Lies die letzten 3-5 Session-Logs in `agent_docs/session_logs/` (neueste zuerst)
- Nimm Erkenntnisse und bekannte Probleme aus den Logs in deine Planung auf
- Wiederhole nicht Fehler die in frueheren Sessions dokumentiert wurden

## Abschlussformat

Nenne am Ende immer:

- welche Dateien du geaendert hast
- welche Tests du ausgefuehrt hast
- welche Risiken oder offenen Punkte bleiben

## Session-Ende: Protokoll und Selbstverbesserung

Am Ende jeder Arbeitssession (oder per `/session-log`):

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

## Pre-Commit Quality Gate

Vor jedem Commit MUSS der Agent `scripts/pre_commit_check.sh` ausfuehren oder die Checks manuell durchfuehren:
1. `python -m pytest -q` — Tests muessen gruen sein
2. Coverage-Stand pruefen (kein Rueckgang)
3. Wenn `src/` Dateien geaendert: pruefen ob `priorities.md` und `current_state.md` auch aktualisiert wurden

## Pflicht: Fortschritt dokumentieren nach jeder erledigten Prioritaet

Nach jeder abgeschlossenen Aufgabe MUSS der Agent folgende Schritte ausfuehren:

### 1. `agent_docs/priorities.md` aktualisieren

- Erledigte Prioritaet mit `✅ ERLEDIGT JJJJ-MM-TT` im Titel markieren
- Direkt darunter einen `**Umsetzung:**`-Block einfuegen mit:
  - was konkret gemacht wurde
  - welche Dateien geaendert wurden
- Pflege pro Prioritaet `Verknuepfte Weaknesses:` und `Verknuepfte Entscheidungen:` mit IDs oder `keine`
- Nummerierung NIEMALS aendern — bestehende Nummern bleiben unveraendert
- Neue Schwachstellen oder Follow-up-Aufgaben als neue Prioritaeten HINTEN anhangen (weiterführende Nummer, z.B. P11, P12, ...)
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

- Abschnitt "Aktueller Stand" oder aequivalenten Bereich mit neuem Datum und Aenderungen aktualisieren
- Neue Faehigkeiten, behobene Schwachstellen, geaenderte Abhaengigkeiten eintragen
- Testanzahl und Coverage-Stand aktualisieren wenn Zahlen sich geaendert haben

### 3. Neue Schwachstellen suchen und eintragen

Nach jeder Aufgabe aktiv pruefen:
- Gibt es in den geaenderten Dateien TODOs, unbehandelte Edge Cases oder fehlende Tests?
- Wurden durch die Aenderung neue Risiken eingefuehrt?
- Gibt es Folgethemen die logisch auf diese Arbeit aufbauen?
- Entscheide, ob sie nur Restrisiko der aktuellen Aufgabe sind oder eine eigene Folgeprioritaet verdienen
- Falls ja: als neue Prioritaet(en) hinten an `priorities.md` anhaengen
- Nenne in der Abschlussmeldung, welche neuen Punkte auf die Liste gekommen sind

### 4. Mindestens eine neue Prioritaet pro erledigter Prioritaet

Fuer jede als erledigt markierte Prioritaet MUSS mindestens eine neue Prioritaet am Ende von `priorities.md` ergaenzt werden. Die neue Prioritaet kann sich aus der erledigten Arbeit ergeben (Folgethema, entdeckte Schwachstelle) oder aus einer anderen Analyse des Projekts stammen. Ziel: Die Prioritaetenliste waechst und bleibt als lebendige Roadmap aktuell — sie schrumpft nie auf null offene Eintraege.

Dieser Schritt ist nicht optional — er haelt die Prioritaetenliste als lebendiges Dokument aktuell.
