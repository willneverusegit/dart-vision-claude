# Session Log - 2026-03-17 - P23 App-State-Concurrency

## Ziel

- gemeinsamen Runtime-State zwischen Lifespan, Pipeline-Threads und Web-Routen expliziter kapseln
- implizite Abhaengigkeit von vorinitialisiertem Global-State abbauen

## Umsetzung

- `src/utils/state.py` neu angelegt mit Helpern fuer:
  - deterministische Runtime-State-Initialisierung pro Lifespan-Start
  - Single-/Multi-Pipeline-Referenzen
  - Thread-Handle-Set/Clear
  - Multi-Frame-Cache und `latest_frame`
- `src/main.py` auf diese Helper umgestellt fuer:
  - Lifespan-Reset
  - Start/Stop der Single- und Multi-Pipeline
  - Multi-Frame-Update im Runtime-Loop
- `src/web/routes.py` fuer Single/Multi-Start-Stop auf die gleichen Helper gezogen, um redundante Dict-Mutationen zu reduzieren
- Tests gehaertet:
  - `tests/test_main_coverage.py` erweitert um direkte State-Helper-Tests
  - `tests/test_routes_extra.py`, `tests/test_routes_coverage2.py` und `tests/test_multi_hardening.py` auf explizites Mock-State-Setup nach `TestClient`-Startup umgestellt

## Verifikation

- `python -m pytest tests/test_main_coverage.py tests/test_routes_extra.py tests/test_routes_coverage2.py -q`
- `python -m pytest tests/test_web.py tests/test_input_validation.py -q`
- `python -m pytest tests/test_multi_hardening.py tests/test_main_coverage.py tests/test_routes_extra.py tests/test_routes_coverage2.py -q`
- `python -m pytest -q`

Ergebnis: `508 passed` am 2026-03-17.

## Restrisiken

- `src/web/routes.py` und `src/main.py` bleiben trotz gekapselter State-Mutation strukturell grosse Module.
- Generierte Python-Artefakte (`__pycache__`, `.pyc`) liegen weiterhin im Worktree und sind als P24 aufgenommen.
