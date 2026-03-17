# Iteration Log

## 2026-03-17 12:12 - Self-improvement workflow run and memory sync

- Category: workflow
- Severity: minor
- Attempts: 1
- Problem: Memory artifacts can drift when workflow steps are executed partially.
- Root cause: No fresh end-to-end run record in this session after skill activation.
- Solution: Executed bootstrap, pattern refresh, iteration logging, and context/decision updates as one cohesive run.
- Failed approaches:
  - none
- Takeaway: Treat self-improvement execution as an atomic sync pass to keep memory artifacts aligned.

## 2026-03-17 14:10 - Composite self-improvement skill activation

- Category: workflow
- Severity: major
- Attempts: 2
- Problem: Standalone self-improvement skill was not installed.
- Root cause: Workflow existed only as separate base skills.
- Solution: Chained session-bootstrap, pattern-extractor, iteration-logger, context-keeper, and skill-generator; generated a new installable composite skill.
- Failed approaches:
  - Checked curated remote skills only
  - Checked current worktree for prebuilt SKILL.md
- Takeaway: When a meta-skill is missing, generate a deterministic composite skill from stable base skills instead of waiting for a separate package.

## 2026-03-17 13:14 - Async route blockers removed for P19

- Category: bugfix
- Severity: major
- Attempts: 2
- Problem: Async FastAPI routes still used blocking `time.sleep(...)` release and polling loops around calibration and pipeline start/stop.
- Root cause: Lifecycle waits were added ad hoc without a shared non-blocking helper for async handlers.
- Solution: Added centralized async wait helpers in `src/web/routes.py`, replaced the blocking waits with `await asyncio.sleep(...)`, and added regression tests for Single/Multi start-stop plus stereo calibration.
- Failed approaches:
  - Patched the shared `threading.Thread` module in route tests, which leaked into the app lifespan and broke thread-handle cleanup.
- Takeaway: Route-level polling belongs behind reusable async helpers; in lifespan-aware tests, patch the worker target instead of globally swapping shared threading primitives.

## 2026-03-17 13:43 - Server-side pending hit lifecycle hardened for P20

- Category: bugfix
- Severity: major
- Attempts: 2
- Problem: Pending hits relied too heavily on frontend timeout behavior and could outlive disconnected clients or grow unpredictably under continuous detections.
- Root cause: Candidate insertion, lookup, cleanup, and metrics were distributed across routes and pipeline callbacks without one authoritative server-side lifecycle policy.
- Solution: Introduced shared pending-hit helpers in `src/main.py`, enforced a `30s` TTL and max `10` live candidates, added periodic cleanup in the pipeline loops, and exposed timeout/overflow counters via `/api/stats`.
- Failed approaches:
  - Initial overflow test accidentally used timestamps old enough to trigger TTL expiry first, which validated the wrong path.
- Takeaway: Stateful runtime queues need one authoritative server-side policy for insert/pop/expire, plus tests that separate timeout and overflow timelines explicitly.

## 2026-03-17 13:58 - Runtime state initialization hardened for P23

- Category: bugfix
- Severity: major
- Attempts: 2
- Problem: Shared `app_state` lifecycle fields were mutated from multiple locations without a clear contract, and tests silently depended on pre-lifespan global state that no longer matched real startup behavior.
- Root cause: Pipeline references, thread handles, and multi-frame caches had grown through ad-hoc dict writes in `main.py`, `routes.py`, and tests, while FastAPI lifespan startup was not treated as the authoritative reset boundary.
- Solution: Added `src/utils/state.py` as the shared owner for runtime-state initialization and lifecycle mutations, switched `main.py`/`routes.py` to these helpers, and moved lifespan-sensitive test state setup inside `with TestClient(app)`.
- Failed approaches:
  - Initial targeted test repair covered only route tests; a second pass was needed when `tests/test_multi_hardening.py` showed the same pre-lifespan setup assumption.
- Takeaway: Once startup is made deterministic, tests must model that boundary explicitly instead of relying on ambient module globals set before `TestClient` begins.

## 2026-03-17 14:32 - Calibration workflows split and hardened for P21

- Category: refactor
- Severity: major
- Attempts: 1
- Problem: `src/cv/calibration.py` still bundled board calibration, YAML persistence, constants and repeated ChArUco observation logic, which made the module hard to reason about and left persistence/error paths weakly covered.
- Root cause: Calibration code had grown organically around one manager class while newer dedicated managers (`BoardCalibrationManager`, `CameraCalibrationManager`) still depended on the same monolithic internals.
- Solution: Extracted board workflow helpers, shared config store/defaults and ChArUco observation collection into dedicated modules, kept `CalibrationManager` as the stable facade, and added tests for camera-specific load, legacy migration and explicit ArUco/ChArUco error paths.
- Failed approaches:
  - none
- Takeaway: When a monolithic manager is already the public seam, split internals into pure helpers first and preserve the facade so routes, tests and dependent managers keep their contract.

## 2026-03-17 15:05 - Multi-camera burst buffer hardened for P22

- Category: bugfix
- Severity: major
- Attempts: 2
- Problem: Multi-camera fusion kept only the latest detection per camera, so closely spaced burst detections could overwrite each other before fusion and produce irreproducible timeout behavior.
- Root cause: The detection buffer modeled one slot per camera instead of a short ordered window, and fallback logic cleared whole camera state instead of only consumed entries.
- Solution: Switched the buffer to a small per-camera time window with anchor-based pairing, selective removal of consumed entries, and tests for burst ordering plus timeout preservation.
- Failed approaches:
  - Initial retention window was too short and pruned unmatched detections before they could emit as timeout fallbacks.
- Takeaway: For burst-sensitive fusion, keep ordering in the buffer and expire detections after fusion semantics, not before.

## 2026-03-17 15:18 - Generated Python artifacts removed from Git tracking for P24

- Category: maintenance
- Severity: minor
- Attempts: 1
- Problem: `__pycache__` and `.pyc` files were already tracked by Git, so local test runs kept polluting the worktree even though `.gitignore` rules existed.
- Root cause: Ignore rules prevent new untracked artifacts, but they do not retroactively stop files that are already in the Git index from appearing as modified.
- Solution: Removed the cached Python artifact paths from Git tracking with `git rm --cached -r ...` and documented the hygiene step in `agent_docs/development_workflow.md`.
- Failed approaches:
  - none
- Takeaway: When generated files are already tracked, fix the index first; ignore rules alone will not quiet the worktree.
