# Vision Domain Reference

## Datei-Map

| Datei | Zweck | Coverage | Status |
|-------|-------|----------|--------|
| `src/cv/pipeline.py` | Single-Camera-Orchestrierung: Frame→Detection | 68% | Stabil, Hauptpfad |
| `src/cv/diff_detector.py` | IDLE/IN_MOTION/SETTLING State-Machine, Before/After-Diff | ~70% | P19+P38 ✅, Tier-1 optimiert |
| `src/cv/tip_detection.py` | minAreaRect + cornerSubPix Sub-Pixel Tip | ~75% | P20+P38 ✅ |
| `src/cv/detector.py` | Shape-basierte Dart-Erkennung mit zeitlicher Bestätigung | 73% | P15 ✅ validiert |
| `src/cv/motion.py` | MOG2 Motion-Gate | - | Einfach, MOG2 bleibt Trigger |
| `src/cv/calibration.py` | 4-stufige ArUco-Erkennung (raw→CLAHE 3→CLAHE 6→Blur+CLAHE) | - | P6 ✅ robust |
| `src/cv/board_calibration.py` | Board-Geometrie-Fit, Homographie | - | Stabil |
| `src/cv/camera_calibration.py` | Lens-Intrinsics | - | Stabil |
| `src/cv/remapping.py` | Kombination Lens + Board Remap | - | Stabil |
| `src/cv/geometry.py` | Pixel→Score Mapping (mm-basierte Konstanten) | - | Stabil |
| `src/cv/capture.py` | ThreadedCamera mit bounded queue + Reconnect | 72% | P2 ✅ |
| `src/cv/roi.py` | Region-of-Interest Handling | - | Stabil |
| `src/cv/recorder.py` | Video-Recording-Infrastruktur | - | P39 ✅ |
| `src/cv/replay.py` | Offline-Frame-Replay für deterministische Tests | - | P1 ✅ |

## State Machine: FrameDiffDetector

```
IDLE → (motion erkannt) → IN_MOTION → (Frames stabil) → SETTLING
SETTLING → (settle_frames abgelaufen) → DART_DETECTED → IDLE
```

- **IDLE**: Baseline kontinuierlich updaten, Motion-Gate aktiv
- **IN_MOTION**: Motion-Gate passiert, Diff wird akkumuliert
- **SETTLING**: `update()` MUSS aufgerufen werden (auch wenn Motion-Gate sonst früh returned)
- **settle_frames default**: 5 bei 30fps (~167ms)

## Tip-Detection Pipeline

```
Diff-Kontur → minAreaRect (Achsenbestimmung) → Kontur-Halbierung entlang Achse
→ schmalere Hälfte = Tip-Seite → äußerster Punkt → cornerSubPix(20x20 ROI)
→ Sub-Pixel Tip-Position
```

- Fallback auf Centroid wenn Tip-Detection fehlschlägt
- `DartDetection.tip` Feld enthält Tip-Position, `.center` = primäre Trefferposition

## Tier-1 Morphologie-Pipeline (P38)

```
Diff → Opening(2x2) [Wire-Filter] → Threshold → Closing(5x5 Ellipse) [Lücken]
→ Closing(3x11 Rect) [Shaft-Fragmente bis 8px] → Kontur-Extraktion
```

## Kalibrierung: 4-stufige ArUco-Erkennung

```
1. Raw (kein Preprocessing)
2. CLAHE clip=3.0
3. CLAHE clip=6.0
4. Blur + CLAHE
```
Qualitätsmetrik: `quality` 0-100, `max_deviation_mm` aus Ringradien-Abweichung.

## Scoring: mm-basierte Konstanten

`geometry.py` nutzt `RING_BOUNDARIES` (mm-basiert), NICHT `radii_px`.
`radii_px` in `BoardGeometry` ist nur für UI-Overlays — nicht für Scoring.

## Wichtige Testdateien

| Datei | Testet |
|-------|--------|
| `tests/test_diff_detector.py` | State-Machine, Morphologie, Elongation-Filter |
| `tests/test_tip_detection.py` | Tip-Algorithmus, Sub-Pixel-Refinement |
| `tests/test_detector.py` | Shape-Erkennung, Kandidaten-Limit |
| `tests/test_pipeline_diff_integration.py` | Pipeline-Integration |
| `tests/test_tip_vs_centroid_scoring.py` | Tip vs. Centroid Scoring-Genauigkeit |
| `tests/e2e/test_replay_e2e.py` | E2E: 90% Hit Rate, 100% Score Accuracy (synthetisch) |
| `tests/benchmark_pipeline.py` | Performance-Bounds |

## Architektur-Entscheidungen

- **ADR-001**: CPU-only, keine GPU, kein YOLO ohne explizite Anfrage
- **ADR-002**: Single-Cam primär, Multi-Cam sekundär
- Single-Cam-Pipeline darf durch Multi-Cam-Änderungen nie verschlechtert werden
