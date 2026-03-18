# Session-Log: Parallel-Agents P27, P55, P57/P59

Datum: 2026-03-18

## Erledigt
- P59: Diff-Cache-Bug in FrameDiffDetector gefixt (_quick_centroid cacht absdiff)
- P27: marker_spacing_mm folgt jetzt Config-Chain statt hardcoded
- P55: Baseline-Warmup-Fix (Motion-Timeout + set_baseline fuer Video-Replay)

## Probleme
- Worktree-Agenten erzeugten Merge-Konflikte bei shared files (diff_detector.py)
- 3+ pre-existing Test-Failures (e2e replay, charuco, routes_coverage2)

## Gelernt
- Parallele Agenten auf geteilten Dateien brauchen Konflikt-Resolution
- _cached_diff-Bug: fehlender Cache-Eintrag beim IN_MOTION→SETTLING Uebergang

## Neue Tasks entdeckt (5 neue Priorities)
- P60: StereoProgressTracker API-Mismatch (valid_pairs kwarg)
- P61: _stability_centroids unbegrenztes Wachstum
- P62: Konsistenz-Check marker_spacing_mm vs frame_inner_mm
- P63: BOARD_CROP_MM Fallback-Mismatch (420mm vs 380mm)
