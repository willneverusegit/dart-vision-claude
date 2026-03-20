---
name: agentic-os-agent-handoff
description: Sichert den aktuellen Arbeitsstand fuer die naechste Session bei Abbruch oder Context-Limit
---

# Agentic OS Agent Handoff — Context-Sicherung

Wird aktiviert wenn eine Session mitten in der Arbeit abgebrochen wird.
Sichert den Arbeitsstand so, dass die naechste Session nahtlos anknuepfen kann.

## Wann ausfuehren

- Bei Context-Limit-Warnung
- Bei User-Unterbrechung mitten in der Arbeit
- Vor geplantem Session-Wechsel
- Automatisch durch `/save-session`

## Schritte

### 1. Aktuellen Arbeitsstand erfassen

Dokumentiere:
- **Aktive Aufgabe**: Woran wurde gerade gearbeitet?
- **Fortschritt**: Wie weit ist die Aufgabe? (z.B. "3/5 Dateien geaendert")
- **Offene Aenderungen**: Welche Dateien sind modifiziert aber nicht committet?
- **Naechster Schritt**: Was waere der naechste konkrete Schritt gewesen?
- **Blockierende Probleme**: Was blockiert ggf. den Fortschritt?

### 2. Git-Status erfassen

```bash
git status --short
git diff --stat
git log --oneline -3
```

Dokumentiere:
- Ungestagete Aenderungen
- Nicht committete Dateien
- Letzter Commit

### 3. Handoff-Briefing schreiben

Erstelle/ueberschreibe `.agent-memory/session-summary.md` mit erweitertem Format:

```markdown
# Letzte Session — HANDOFF

*Datum: <HEUTE>*
*Status: UNTERBROCHEN — Handoff aktiv*

## Aktive Aufgabe
<Was wurde gerade gemacht>

## Fortschritt
- Erledigt: <was schon fertig ist>
- Offen: <was noch fehlt>
- Naechster Schritt: <konkreter naechster Schritt>

## Offene Aenderungen
<git status output>

## Kontext fuer naechste Session
- Relevante Dateien: <liste>
- Zu lesende Doku: <liste>
- Bekannte Risiken: <liste>

## Offene Punkte
- <punkt>

## Statistik
- Iterationen: <anzahl>
- Fehler: <offen/geloest>
```

### 4. Warnung in Heartbeat-Log

Trage in `.agent-memory/heartbeat/heartbeat-log.md` ein:
```markdown
## <DATUM> — HANDOFF
- Status: UNTERBROCHEN
- Aktive Aufgabe: <beschreibung>
- Naechster Schritt: <beschreibung>
```

### 5. Abschlussmeldung

```
Handoff gesichert:
- Arbeitsstand dokumentiert in session-summary.md
- Naechste Session beginnt mit: <naechster schritt>
- Git: <X> ungestagete Aenderungen
```
