---
name: agentic-os-iteration-logger
description: Protokolliert Bugs, Root Causes, Loesungen und gescheiterte Ansaetze in .agent-memory/iterations/
---

# Agentic OS Iteration Logger

Erfasst jede nicht-triviale Iteration (Bug-Fix, gescheiterter Ansatz, Architektur-Erkenntnis)
strukturiert in `.agent-memory/iterations/`.

## Wann ausfuehren

- Nach jedem geloesten Bug
- Nach jeder nicht-trivialen Fehlerbehebung
- Wenn ein Ansatz gescheitert ist (auch ohne endgueltige Loesung)
- Automatisch durch Orchestrator wenn `auto_log_iterations: true`

## Schritte

### 1. Kontext erfassen

Sammle folgende Informationen:
- **Datum/Uhrzeit**
- **Kategorie**: `syntax` | `logic` | `architecture` | `environment` | `config` | `test` | `performance`
- **Severity**: `critical` | `major` | `minor`
- **Problem**: Was war das beobachtete Verhalten?
- **Root Cause**: Warum trat das Problem auf?
- **Solution**: Was wurde gemacht um es zu loesen?
- **Failed Approaches**: Welche Ansaetze wurden vorher versucht und warum scheiterten sie?
- **Takeaway**: Welche generelle Erkenntnis laesst sich ableiten?
- **Files Changed**: Welche Dateien wurden geaendert?
- **Attempts**: Wie viele Versuche bis zur Loesung?

### 2. iteration-log.md erweitern

Fuege einen neuen Eintrag in `.agent-memory/iterations/iteration-log.md` hinzu:

```markdown
---

## [<DATUM> <UHRZEIT>] <Kurzbeschreibung>

**Category:** <kategorie> | **Severity:** <severity> | **Attempts:** <anzahl>

**Problem:** <beschreibung>

**Root Cause:** <ursache>

**Solution:** <loesung>

**Failed Approaches:**
- <ansatz 1 und warum gescheitert>

**Takeaway:** <generelle erkenntnis>
```

### 3. errors.json erweitern

Fuege strukturierten Eintrag in `.agent-memory/iterations/errors.json` hinzu:

```json
{
  "id": "<datum>-<uhrzeit>-<slug>",
  "timestamp": "<iso-datum>",
  "category": "<kategorie>",
  "severity": "<severity>",
  "problem": "<kurz>",
  "root_cause": "<kurz>",
  "solution": "<kurz>",
  "failed_approaches": ["<ansatz>"],
  "takeaway": "<kurz>",
  "files": ["<pfad>"],
  "attempts": <zahl>,
  "pattern_extracted": false
}
```

### 4. Pattern-Check triggern

- Zaehle nicht-extrahierte Iterationen (pattern_extracted: false)
- Wenn >= `pattern_check_interval` (default 5):
  - Empfehlung: "Pattern-Extraktion empfohlen — `/agentic-os:pattern-extractor`"
- Ansonsten: Zaehler anzeigen

### 5. Abschlussmeldung

```
Iteration geloggt: <kurzbeschreibung>
Severity: <severity> | Kategorie: <kategorie>
Iterationen seit letzter Pattern-Extraktion: X/<interval>
```
