# Pattern Summary

## New patterns

- `run-self-improvement-as-atomic-sync`
  - Self-improvement runs should update all memory artifacts in one cohesive pass (bootstrap -> patterns -> iteration -> context/decisions).

- `compose-missing-meta-skill-from-base-skills`
  - Missing meta-skills should be composed from existing base skills and then packaged as a reusable skill.

- `centralize-non-blocking-route-waits`
  - Async FastAPI routes should reuse shared `asyncio.sleep`-based wait helpers instead of inline `time.sleep` loops; in lifespan-aware tests, patch the worker target rather than the shared threading module.

- `centralize-runtime-queue-lifecycle`
  - Shared runtime queues should have one backend owner for add/pop/expire/clear plus diagnostics counters; the frontend may mirror state, but should not own expiry semantics.

- `inject-test-state-after-lifespan-start`
  - Lifespan-aware FastAPI tests should inject mocked shared state only after `TestClient(...)` startup, otherwise deterministic startup resets will wipe the fixture state and produce misleading failures.

- `split-calibration-workflows-behind-stable-manager-api`
  - If a calibration module grows into board logic, config IO and repeated ChArUco collection, move those concerns into pure helper modules while keeping the manager facade and route-facing API unchanged.

- `buffer-multi-camera-bursts-per-camera-window`
  - For multi-camera fusion under burst conditions, keep a small per-camera time-window buffer and pair around the oldest pending anchor instead of overwriting detections with the latest hit per camera.

- `untrack-generated-python-artifacts-not-just-ignore-them`
  - If `__pycache__` or `.pyc` files already live in Git history, `.gitignore` alone is not enough; remove them from the index with `git rm --cached` and document the hygiene step.

## Updated patterns

- none

## Top recurring issues

- no recurring issue yet (only one logged occurrence)

## Skill candidates

- none yet (occurrence count below threshold)
