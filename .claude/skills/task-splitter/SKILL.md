---
name: task-splitter
description: Zerlegt groessere Aufgaben in unabhaengige Teilaufgaben und dispatcht parallele Agenten
disable-model-invocation: true
---

# Task-Splitter — Parallele Agenten fuer groessere Aufgaben

Zerlege eine groessere Aufgabe in unabhaengige Teileinheiten und fuehre sie parallel mit dem Agent-Tool aus.

## Workflow

### 1. Aufgabe analysieren
- Lies die Aufgabe und identifiziere unabhaengige Teilbereiche
- Pruefe: Welche Teilaufgaben haben KEINE Abhaengigkeiten untereinander?
- Nur echt unabhaengige Aufgaben parallelisieren — sequenzielle Abhaengigkeiten erkennen und respektieren

### 2. Teilaufgaben definieren
Fuer jede Teilaufgabe:
- **Was**: konkrete Beschreibung
- **Dateien**: welche Dateien gelesen/geaendert werden
- **Tests**: welche Tests betroffen sind
- **Abhaengigkeit**: keine / haengt ab von Teilaufgabe X

### 3. Unabhaengige Aufgaben parallel dispatchen
- Nutze das `Agent`-Tool mit `isolation: "worktree"` fuer jede unabhaengige Teilaufgabe
- Gib jedem Agenten einen klaren, abgeschlossenen Auftrag mit allen noetigen Kontextinfos
- Setze `run_in_background: true` fuer parallele Ausfuehrung

### 4. Ergebnisse zusammenfuehren
- Warte auf alle Agenten
- Pruefe auf Konflikte zwischen den Aenderungen
- Merge die Worktree-Branches oder uebernimm Aenderungen manuell
- Fuehre abschliessend `python -m pytest -q` aus um sicherzustellen dass alles zusammenpasst

## Regeln
- Maximal 4 parallele Agenten gleichzeitig (Ressourcen schonen, CPU-only Constraint)
- Jeder Agent bekommt nur die fuer ihn relevanten Dateien/Module genannt
- Kein Agent darf sensible Dateien (`src/main.py`, `src/web/routes.py`) aendern ohne dass das explizit im Auftrag steht
- Bei Konflikten: manuell zusammenfuehren, nicht blind ueberschreiben

## Beispiel-Zerlegung

Aufgabe: "Coverage fuer cv-Modul erhoehen"

| # | Teilaufgabe | Dateien | Parallel? |
|---|------------|---------|-----------|
| 1 | Tests fuer `tip_detection.py` | `src/cv/tip_detection.py`, `tests/test_tip_detection.py` | ja |
| 2 | Tests fuer `geometry.py` | `src/cv/geometry.py`, `tests/test_geometry.py` | ja |
| 3 | Tests fuer `replay.py` | `src/cv/replay.py`, `tests/test_replay.py` | ja |
| 4 | Tests fuer `motion.py` | `src/cv/motion.py`, `tests/test_motion.py` | ja |
