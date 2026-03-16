# Codex Guide

Diese Datei richtet sich an Codex als ausfuehrenden Coding Agent.

## Rolle in diesem Repo

Codex soll hier nicht nur analysieren, sondern in der Regel:

- den Code lesen
- die betroffenen Stellen identifizieren
- die Aenderung direkt umsetzen
- die relevanten Tests ausfuehren
- die Ergebnisse knapp und belastbar berichten

## Erwartetes Verhalten

### 1. Erst Kontext, dann Aenderung

Vor einer Aenderung:

- lies die relevanten Dateien
- lies die zugehoerigen Tests
- suche nach schon vorhandenen Mustern statt Parallelstrukturen einzufuehren

### 2. Klein anfangen

Wenn eine Aufgabe gross ist:

- beginne mit der kleinsten Aenderung, die das Hauptrisiko adressiert
- liefere erst dann Folgeverbesserungen

### 3. Risikoorientiert arbeiten

In diesem Repo gelten als besonders riskant:

- `src/main.py`
- `src/web/routes.py`
- `src/cv/pipeline.py`
- `src/cv/multi_camera.py`
- Aenderungen an `config/*.yaml`

Wenn du dort arbeitest:

- aendere gezielt
- teste gezielt
- dokumentiere Restrisiken explizit

## Was Codex bevorzugt tun soll

- Runtime-Stabilitaet vor Feature-Ausbau
- API- und Workflow-Brueche vermeiden
- CPU- und Speicherlast konservativ halten
- bestehende Testdateien erweitern statt neue Testinseln zu bauen

## Was Codex vermeiden soll

- grosse Umbauten ohne schrittweise Verifikation
- neue Abhaengigkeiten fuer Probleme, die lokal loesbar sind
- schwergewichtige Features im Hot Path
- "cleanup" in sensiblen Dateien ohne klaren funktionalen Gewinn

## Gute Abschlussform fuer Codex

Ein guter Abschluss in diesem Repo nennt:

- die Kernuebersicht der Aenderung
- die ausgefuehrten Tests
- verbleibende Risiken
- eventuelle naechste sinnvolle Schritte, wenn sie direkt anschliessen

