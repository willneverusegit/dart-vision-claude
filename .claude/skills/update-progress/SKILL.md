---
name: update-progress
description: Aktualisiert Fortschrittsdokumentation nach Abschluss einer Aufgabe. Markiert erledigte Prioritaeten und sucht nach neuen Schwachstellen.
---

# Update Progress Skill

Wird aktiviert wenn eine Prioritaet abgearbeitet wurde oder eine neue Prioritaet hinzugefuegt werden soll.

## Workflow

### 1. Erledigte Prioritaet markieren

Wenn eine Prioritaet abgeschlossen wurde:

1. Lies `agent_docs/priorities.md`
2. Markiere die erledigte Prioritaet mit dem Format:
   ```
   ## Prioritaet N: Titel (✅ ERLEDIGT JJJJ-MM-TT)

   **Umsetzung:** Was konkret umgesetzt wurde. Geaenderte Dateien: `src/foo.py`.
   ```
3. NIEMALS die Nummerierung aendern
4. Erledigte Prioritaeten bleiben in der Liste

### 2. Neue Prioritaet hinzufuegen

Wenn bei der Arbeit eine neue Schwachstelle oder Verbesserungsmoeglichkeit entdeckt wurde:

1. Lies `agent_docs/priorities.md` und finde die hoechste bestehende Nummer
2. Fuege die neue Prioritaet am Ende an mit der naechsten Nummer
3. Verwende das Standard-Format:
   ```
   ## Prioritaet N: Titel (neu — entdeckt bei Arbeit an PX)

   Kritikalitaet: KRITISCH / HOCH / NIEDRIG

   Ziel:
   - ...

   Typische Arbeiten:
   - ...
   ```

### 3. current_state.md aktualisieren

- Aktualisiere `agent_docs/current_state.md` mit dem neuen Stand
- Datum aktualisieren
- Neue stabile Features in die richtige Sektion eintragen

### 4. Session-Log ausfuehren

Rufe am Ende `/session-log` auf um die Aenderungen zu dokumentieren.

## Regeln

- Nummerierung wird NIEMALS geaendert
- Erledigte Prios bleiben in der Liste
- Neue Prios kommen immer ans Ende
- Kritikalitaet angeben bei neuen Prios
- Datum bei Erledigung ist Pflicht
- Umsetzungsnotiz bei Erledigung ist Pflicht (was wurde gemacht, welche Dateien)
