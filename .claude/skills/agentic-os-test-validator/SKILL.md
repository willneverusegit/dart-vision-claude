---
name: agentic-os-test-validator
description: Validiert Test-Ergebnisse, trackt Trends und erkennt Regressionen in .agent-memory/quality/
---

# Agentic OS Test Validator

Analysiert Test-Ergebnisse, trackt Trends ueber Sessions hinweg und
erkennt Regressionen fruehzeitig.

## Wann ausfuehren

- Nach jedem Test-Run
- Automatisch durch Orchestrator wenn `auto_run_tests: true`
- Per Session-Ende-Protokoll

## Schritte

### 1. Tests ausfuehren

```bash
python -m pytest --cov=src --cov-report=term -q
```

Ergebnisse erfassen:
- Anzahl Tests (passed, failed, skipped, xfail)
- Coverage (gesamt und pro Modul)
- Laufzeit

### 2. Ergebnis dokumentieren

Fuege in `.agent-memory/quality/test-results.json` hinzu:

```json
{
  "runs": [
    {
      "date": "<datum>",
      "total": <anzahl>,
      "passed": <anzahl>,
      "failed": <anzahl>,
      "skipped": <anzahl>,
      "xfail": <anzahl>,
      "coverage_total": <prozent>,
      "coverage_modules": {
        "main.py": <prozent>,
        "routes.py": <prozent>,
        "pipeline.py": <prozent>
      },
      "duration_seconds": <sekunden>,
      "new_tests": <anzahl>,
      "session_context": "<was wurde gemacht>"
    }
  ],
  "trend": "improving|stable|declining"
}
```

### 3. Trend berechnen

Vergleiche mit den letzten 3-5 Runs:
- **Improving**: Tests steigen, Coverage steigt, keine Failures
- **Stable**: Tests gleich oder leicht steigend, Coverage stabil
- **Declining**: Tests fallen, Coverage sinkt, neue Failures

### 4. Regressionen erkennen

Pruefe:
- Sind Tests die vorher gruen waren jetzt rot?
- Ist die Coverage in einem Modul signifikant gefallen (> 5%)?
- Gibt es neue Failures die nicht xfail sind?

Bei Regression:
- Warnung ausgeben
- In `heartbeat/heartbeat-log.md` vermerken
- Betroffene Module/Tests auflisten

### 5. Quality-Score Test-Dimension aktualisieren

Aktualisiere in `.agent-memory/quality/quality-score.json`:
- `dimensions.test_coverage`: direkt aus Coverage
- Gewichtet: 100% coverage = 100, <50% = anteilig

### 6. Abschlussmeldung

```
=== Test Validation ===
Tests:      X passed, Y failed, Z skipped
Coverage:   XX% (Trend: <trend>)
Regression: keine / WARNUNG: <details>
Neue Tests: +N seit letztem Run
```
