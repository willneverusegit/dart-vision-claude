---
name: meta-infra
description: App-Lifecycle, Config-Validierung, Kamera-Capture, Test-Infrastruktur, CI — aktivieren wenn an src/main.py, src/utils/config.py, src/cv/capture.py oder tests/ gearbeitet wird
type: domain
---

## Wann nutzen

- Änderungen an App-Start/Stop, Lifespan, Hintergrundthreads (main.py)
- Config-Schema-Validierung, YAML-Laden/-Speichern (config.py)
- ThreadedCamera, Reconnect-Logik (capture.py)
- Test-Infrastruktur, neue Testdateien, Coverage-Pflege
- CI (pre_commit_check.sh), Scripts (record_camera.py, test_all_videos.py)
- Windows-spezifische Konfiguration (.venv, start.bat, diagnose.py)

## Pflichtlektüre vor Arbeit

1. `agent_docs/pitfalls.md` → "Threading & Lifecycle" und "Windows-spezifisch"
2. `agent_docs/development_workflow.md` — Change-Checkliste, Testmatrix
3. `src/main.py` lesen vor jeder Lifecycle-Änderung

## Schlüsselregeln

1. **main.py ist HIGH-RISK**: Threading + App-Lifecycle + API + Runtime-Zustand. Kleine Änderungen können Start/Stop oder Eventfluss brechen.
2. **ThreadedCamera-Reconnect**: Immer `stop_event` prüfen bevor neuer Thread gestartet — kein Thread-Leak.
3. **Pipeline-Stop**: Sowohl eigenes `stop_event` als auch App-`shutdown_event` in `_run_*`-Funktionen prüfen.
4. **config/*.yaml sind Betriebsdaten**: Nie ohne Backup überschreiben, `schema_version` beachten.
5. **Rückwärtskompatibilität bei Config-Änderungen**: Gespeicherte YAML-Daten müssen weiter ladbar sein.
6. **Coverage nicht verschlechtern**: Neue Funktionalität ohne Tests senkt Coverage — immer mitschreiben.
7. **Windows-Pfade**: Forward-Slashes oder `os.path.join` — keine hartcodierten Backslashes.
8. **USB-Kameras können disconnecten**: Reconnect-Logik ist Pflicht, exponentieller Backoff 1-30s.
9. **Pre-Commit-Gate**: `scripts/pre_commit_check.sh` vor jedem Commit: Tests + Coverage-Check.
10. **testvids/ nicht committen**: Nur `ground_truth.yaml` tracken, MP4-Files sind ~676MB.

## Offene Todos (aktive P-Items)

| P-Nr | Titel | Status |
|------|-------|--------|
| P5 | Windows-Inbetriebnahme — start.bat, diagnose.py | ✅ ERLEDIGT |
| P39 | Video-Replay-Infrastruktur (Ground-Truth-Annotation noch ausstehend) | TEILWEISE |

## Risiko-Einschätzung

**SEHR HOCH** für main.py — App-Lifecycle, Threading, globaler Zustand.
**MITTEL** für config.py — Schema-Änderungen können bestehende Kalibrierungsdaten invalidieren.
**NIEDRIG** für capture.py (isoliertes Modul mit gutem Test-Coverage), tests/, scripts/.
