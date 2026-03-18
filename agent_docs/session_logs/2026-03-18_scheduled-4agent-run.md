# Session: Scheduled 4-Agent Parallel Run (2026-03-18)

## Erledigt
- **P64:** 54 neue Route-Tests (routes.py Coverage-Ziel 80%+, Messung blockiert durch Python 3.14/numpy Bug)
- **P65:** Camera Preview Locking (asyncio.Lock pro Source, 2.5s TTL Cache, 5s Timeout) + 8 Tests
- **P39:** Video-Replay-Testinfrastruktur verbessert (add_ground_truth.py Helper, besseres Fehler-Reporting) + 29 Tests
- **P11:** Ground-Truth-Validierung (validate_ground_truth.py Script) + 32 Tests
- 4 neue Prioritaeten: P67 (Router Factory), P68 (Timestamp Matching), P69 (Ring Naming), P70 (async sleep)
- Alle Branches in main gemerged und gepusht. Teststand: 1203 passed.

## Probleme
- Python 3.14 + numpy 2.4.2 verursacht "cannot load module more than once" bei coverage-Messung
- Agent 1 (P64) brauchte ~46min wegen numpy-Import-Fehler in Worktree
- priorities.md Merge-Konflikte bei 3 von 3 nachfolgenden Merges (alle Agents schrieben ans Ende)

## Gelernt
- Ring-Naming inkonsistent: GT nutzt `bull_inner`/`bull_outer`, Backend `inner_bull`/`outer_bull` (P69)
- Synchrone `time.sleep()` in async Handlern blockiert Event-Loop bis zu 4s (P70)
- Module-level Router in routes.py erschwert Test-Isolation (P67)

## CLAUDE.md-Anpassungen
- Keine noetig
