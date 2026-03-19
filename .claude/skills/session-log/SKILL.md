---
name: session-log
description: Schreibt Session-Log, aktualisiert priorities.md und current_state.md, aktiviert context-keeper
---

# Session-Abschluss

Fuehre den vollstaendigen Session-Abschluss durch. Alle Schritte sind Pflicht.

## Schritte

### 1. Tests und Coverage pruefen
- `python -m pytest --cov=src --cov-report=term -q`
- Aktuelle Testanzahl und Coverage notieren

### 2. Session-Log schreiben
- Erstelle `agent_docs/session_logs/JJJJ-MM-TT_kurzthema.md`
- Format: **Erledigt**, **Probleme**, **Gelernt**, **CLAUDE.md-Anpassungen**
- Maximal 15 Zeilen, keine Code-Bloecke

### 3. priorities.md aktualisieren
- Erledigte Prioritaeten mit `✅ ERLEDIGT JJJJ-MM-TT` markieren
- `**Umsetzung:**`-Block mit konkreten Aenderungen einfuegen
- Mindestens eine neue Prioritaet pro erledigter Prioritaet hinten anhaengen
- Nummerierung NIEMALS aendern

### 4. current_state.md aktualisieren
- Testanzahl und Coverage-Stand aktualisieren
- Neue Faehigkeiten oder behobene Schwachstellen eintragen

### 5. Context-Keeper aktivieren
- Aktiviere `agentic-os:wrap-up` fuer Architektur-Entscheidungen und Statusaenderungen

### 6. Pattern-Analyse (optional)
- Wenn mindestens 3 Iterationen via `iteration-logger` erfasst wurden:
  - Aktiviere `agentic-os:pattern-extractor`

### 7. CLAUDE.md pruefen
- Waren Lesepfade oder Instruktionen unklar? → Anpassen
- Aenderungen im Session-Log vermerken
