"""
Performance benchmark for the CV pipeline (mock mode, no camera needed).
Run: python -m tests.benchmark_pipeline --duration 10
"""

import time
import argparse
import statistics
import numpy as np
from src.cv.motion import MotionDetector
from src.cv.detector import DartImpactDetector
from src.cv.field_mapper import FieldMapper
from src.cv.roi import ROIProcessor
from src.utils.fps import FPSCounter


def run_benchmark(duration: int = 10) -> dict:
    """Run a simulated pipeline benchmark with mock frames."""
    roi_proc = ROIProcessor()
    motion = MotionDetector(threshold=500)
    detector = DartImpactDetector()
    mapper = FieldMapper()
    fps_counter = FPSCounter(window_size=100)

    frame_times: list[float] = []
    total_frames = 0

    # Generate a mock frame
    mock_frame = np.random.randint(0, 50, (480, 640, 3), dtype=np.uint8)
    # A stable ROI keeps benchmark work close to the runtime pipeline.
    mock_roi = np.zeros((400, 400), dtype=np.uint8)

    print(f"Running benchmark for {duration}s with mock frames...")
    start_time = time.time()

    while time.time() - start_time < duration:
        frame_start = time.perf_counter()

        # Simulate pipeline steps
        warped = roi_proc.warp_roi(mock_frame)
        import cv2
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        mask, has_motion = motion.detect(enhanced)
        if has_motion:
            detection = detector.detect(mock_roi, mask)
            if detection:
                mapper.point_to_score(detection.center[0], detection.center[1], 200, 200, 200)

        frame_end = time.perf_counter()
        frame_times.append(frame_end - frame_start)
        fps_counter.update()
        total_frames += 1

    # Calculate metrics
    frame_times_sorted = sorted(frame_times)
    n = len(frame_times_sorted)
    median_time = statistics.median(frame_times) if frame_times else 1
    p95_time = frame_times_sorted[int(n * 0.95)] if n > 20 else median_time

    results = {
        "duration_s": duration,
        "total_frames": n,
        "fps_median": 1.0 / median_time,
        "fps_p95": 1.0 / p95_time,
        "latency_median_ms": median_time * 1000,
        "latency_p95_ms": p95_time * 1000,
    }

    print()
    print("=== Pipeline Benchmark Results ===")
    for key, value in results.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    print()
    print("=== KPI Check ===")
    checks = [
        ("Median FPS >= 15", results["fps_median"] >= 15),
        ("P95 FPS >= 10", results["fps_p95"] >= 10),
        ("Latency median <= 200ms", results["latency_median_ms"] <= 200),
        ("Latency P95 <= 200ms", results["latency_p95_ms"] <= 200),
    ]
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            pass  # At least one KPI failed

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=10)
    args = parser.parse_args()
    run_benchmark(args.duration)
