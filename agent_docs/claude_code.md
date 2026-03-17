# Claude Code Guide

Diese Datei richtet sich an Claude Code als Coding Agent in diesem Repo.

## Rolle in diesem Repo

Claude Code soll hier besonders stark sein in:

- strukturierter Voranalyse
- sauberer Aufteilung groesserer Aufgaben
- defensiver Aenderung sensibler Pfade
- klarer Kommunikation von Annahmen und Risiken

## Erwartetes Verhalten

### 1. Erst Struktur, dann Eingriff

Bevor du Code aenderst:

- benenne kurz die betroffenen Teilsysteme
- lies die dazugehoerigen Agent-Dokumente
- identifiziere den wahrscheinlichsten Impact auf:
  - Single-Cam
  - Multi-Cam
  - Kalibrierung
  - UI/API

### 2. Sensible Pfade defensiv behandeln

Wenn die Aufgabe `src/main.py`, `src/web/routes.py` oder `src/cv/multi_camera.py` betrifft:

- gehe von hoeherem Risiko aus
- aendere moeglichst wenig auf einmal
- begruende den Eingriff klar

### 3. Reale Nutzbarkeit im Blick behalten

Claude Code soll dieses Repo nicht nur "sauberer" machen, sondern praktisch weiterentwickeln:

- Single-Cam darf nicht schlechter werden
- Zielhardware bleibt ein CPU-only-Laptop
- Multi-Cam muss robuster werden, nicht nur komplexer

## Was Claude Code bevorzugt tun soll

- Zusammenhaenge zwischen Modulen explizit machen
- Refactorings nur dann vornehmen, wenn sie reale Wartbarkeit verbessern
- Dokumentation mitpflegen, wenn Arbeitsweise oder Architektur beruehrt wird

## Was Claude Code vermeiden soll

- vorschnelle Generalisierung
- abstrakte Architekturarbeit ohne klaren Nutzen fuer das aktuelle Repo
- neue Prozesskomplexitaet ohne Tests oder betriebliche Vorteile

## Pflicht zur Fortschrittsdokumentation

Nach jeder erledigten Aufgabe oder Prioritaet aktualisiere direkt im selben Arbeitsgang:

- `agent_docs/priorities.md` — Umsetzung beschreiben, als erledigt markieren, Verknuepfte Weaknesses/Entscheidungen pflegen
- `agent_docs/current_state.md` — Ist-Stand, Kennzahlen, neue Faehigkeiten aktualisieren

Zusaetzlich:

- Pflege Rueckverlinkungen zwischen Prioritaeten, `weakness_log.md`, `decision_log.md` und Session-Reports
- Fuer jede erledigte Prioritaet MUSS mindestens eine neue Prioritaet am Ende von `priorities.md` ergaenzt werden
- Nenne in der Abschlussmeldung, welche neuen Punkte auf die Liste gekommen sind

## Gute Abschlussform fuer Claude Code

Ein guter Abschluss in diesem Repo nennt:

- betroffene Bereiche
- umgesetzte Aenderungen
- ausgefuehrte Verifikation
- Aktualisierung von `priorities.md` und `current_state.md`
- offene Risiken oder bewusst nicht angefasste Folgepunkte
- welche neuen Prioritaeten oder Schwachstellen entdeckt wurden

