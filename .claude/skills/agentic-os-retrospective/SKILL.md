---
name: agentic-os-retrospective
description: Tiefenanalyse ueber mehrere Sessions — Metriken, Blind Spots, Verbesserungstrends
---

# Agentic OS Retrospective — Langzeit-Analyse

Fuehrt eine Tiefenanalyse ueber die letzten 5-10 Sessions durch.
Erkennt Trends, Blind Spots und Verbesserungsbereiche.

## Wann ausfuehren

- Alle 5-10 Sessions (konfigurierbar via `retrospective_interval_sessions`)
- Per User-Aufruf
- Nach groesseren Milestones

## Schritte

### 1. Daten sammeln

Lade und analysiere:
- `.agent-memory/iterations/errors.json` — alle Iterationen
- `.agent-memory/patterns/patterns.json` — alle Patterns
- `.agent-memory/quality/test-results.json` — Test-Trends
- `.agent-memory/quality/code-reviews.json` — Review-Ergebnisse
- `.agent-memory/quality/quality-score.json` — Score-Verlauf
- `agent_docs/session_logs/` — letzte 5-10 Session-Logs
- `agent_docs/priorities.md` — erledigte vs. offene Prioritaeten

### 2. Metriken berechnen

```
Zeitraum:                <erste session> bis <letzte session>
Sessions analysiert:     X
Iterationen gesamt:      Y
  davon critical:        Z
  davon ungeloest:       W
Patterns erkannt:        A
  davon high confidence: B
Skills generiert:        C
Tests:                   D → E (Trend)
Coverage:                F% → G% (Trend)
Prioritaeten erledigt:   H / I
```

### 3. Trend-Analyse

Fuer jede Dimension:
- **Fehlerrate**: Steigend/Fallend/Stabil?
- **Fehler-Kategorien**: Verschieben sich die Schwerpunkte?
- **Fix-Geschwindigkeit**: Werden Fehler schneller geloest?
- **Test-Qualitaet**: Steigen Tests und Coverage?
- **Pattern-Reife**: Steigen Confidence-Level?

### 4. Blind Spots identifizieren

Suche nach:
- **Ungetestete Bereiche**: Module mit < 50% Coverage
- **Wiederkehrende Fehler**: Gleiche Kategorie > 3x
- **Ignorierte Patterns**: Patterns die nie in Actions umgesetzt wurden
- **Verwaiste Prioritaeten**: Seit > 5 Sessions offen ohne Fortschritt
- **Fehlende Reviews**: Geaenderte Dateien ohne Review

### 5. Verbesserungsvorschlaege ableiten

Basierend auf der Analyse:
- Top-3 Verbesserungsbereiche identifizieren
- Konkrete Massnahmen vorschlagen
- Neue Prioritaeten fuer `priorities.md` empfehlen

### 6. Retrospektive dokumentieren

Schreibe `.agent-memory/retrospectives/retro-<datum>.md`:

```markdown
# Retrospektive <DATUM>

## Zeitraum
<erste session> — <letzte session> (X Sessions)

## Metriken
<tabelle>

## Trends
<analyse>

## Blind Spots
- <spot 1>

## Empfehlungen
1. <empfehlung>

## Action Items
- [ ] <action>
```

### 7. metrics.json aktualisieren

Fuege Snapshot in `.agent-memory/retrospectives/metrics.json` hinzu:

```json
{
  "sessions": [
    {
      "date": "<datum>",
      "sessions_analyzed": <anzahl>,
      "iterations": <anzahl>,
      "patterns": <anzahl>,
      "test_count": <anzahl>,
      "coverage": <prozent>,
      "quality_score": <score>,
      "priorities_done": <anzahl>
    }
  ]
}
```

### 8. Abschlussmeldung

```
=== Retrospektive ===
Zeitraum:       <range>
Top-Trends:     <3 wichtigste>
Blind Spots:    <anzahl>
Empfehlungen:   <anzahl>
Action Items:   <anzahl>
```
