"""
Performance benchmark for the CV pipeline (mock mode, no camera needed).
Run: python -m tests.benchmark_pipeline --duration 10
     python -m tests.benchmark_pipeline --duration 10 --cameras 2
"""

import time
import argparse
import statistics
import threading
import numpy as np
from src.cv.motion import MotionDetector
from src.cv.detector import DartImpactDetector
from src.cv.geometry import BoardGeometry, BoardPose
from src.cv.roi import ROIProcessor
from src.utils.fps import FPSCounter

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def _run_single_pipeline(duration: int, cam_id: str, results_out: dict) -> None:
    """Run a simulated pipeline benchmark for a single camera."""
    roi_proc = ROIProcessor()
    motion = MotionDetector(threshold=500)
    detector = DartImpactDetector()
    pose = BoardPose(
        homography=None,
        center_px=(200.0, 200.0),
        radii_px=(10.0, 19.0, 106.0, 116.0, 188.0, 200.0),
        rotation_deg=0.0,
        valid=True,
    )
    geometry = BoardGeometry.from_pose(pose, roi_size=(400, 400))
    fps_counter = FPSCounter(window_size=100)

    frame_times: list[float] = []
    total_frames = 0

    mock_frame = np.random.randint(0, 50, (480, 640, 3), dtype=np.uint8)
    mock_roi = np.zeros((400, 400), dtype=np.uint8)

    start_time = time.time()

    while time.time() - start_time < duration:
        frame_start = time.perf_counter()

        warped = roi_proc.warp_roi(mock_frame)
        import cv2
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        mask, has_motion = motion.detect(enhanced)
        if has_motion:
            detection = detector.detect(mock_roi, mask)
            if detection:
                geometry.point_to_score(float(detection.center[0]), float(detection.center[1]))

        frame_end = time.perf_counter()
        frame_times.append(frame_end - frame_start)
        fps_counter.update()
        total_frames += 1

    frame_times_sorted = sorted(frame_times)
    n = len(frame_times_sorted)
    median_time = statistics.median(frame_times) if frame_times else 1
    p95_time = frame_times_sorted[int(n * 0.95)] if n > 20 else median_time

    results_out[cam_id] = {
        "total_frames": n,
        "fps_median": 1.0 / median_time,
        "fps_p95": 1.0 / p95_time,
        "latency_median_ms": median_time * 1000,
        "latency_p95_ms": p95_time * 1000,
    }


def run_benchmark(duration: int = 10, cameras: int = 1) -> dict:
    """Run a simulated pipeline benchmark with mock frames.

    Args:
        duration: Benchmark duration in seconds.
        cameras: Number of parallel camera pipelines to simulate.
    """
    print(f"Running benchmark for {duration}s with {cameras} camera(s)...")

    # Capture resource usage if psutil available
    process = None
    if HAS_PSUTIL:
        process = psutil.Process()
        cpu_start = process.cpu_percent()  # prime the measurement

    per_cam_results: dict[str, dict] = {}

    if cameras == 1:
        _run_single_pipeline(duration, "cam_0", per_cam_results)
    else:
        threads: list[threading.Thread] = []
        for i in range(cameras):
            t = threading.Thread(
                target=_run_single_pipeline,
                args=(duration, f"cam_{i}", per_cam_results),
                daemon=True,
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    # Aggregate results
    all_fps_median = [r["fps_median"] for r in per_cam_results.values()]
    all_fps_p95 = [r["fps_p95"] for r in per_cam_results.values()]
    all_lat_median = [r["latency_median_ms"] for r in per_cam_results.values()]
    all_lat_p95 = [r["latency_p95_ms"] for r in per_cam_results.values()]
    total_frames = sum(r["total_frames"] for r in per_cam_results.values())

    results: dict = {
        "cameras": cameras,
        "duration_s": duration,
        "total_frames": total_frames,
    }

    # Per-camera stats
    for cam_id, r in sorted(per_cam_results.items()):
        results[f"{cam_id}_fps_median"] = r["fps_median"]
        results[f"{cam_id}_fps_p95"] = r["fps_p95"]

    # Aggregate stats
    results["fps_median_min"] = min(all_fps_median)
    results["fps_p95_min"] = min(all_fps_p95)
    results["latency_median_ms_max"] = max(all_lat_median)
    results["latency_p95_ms_max"] = max(all_lat_p95)

    # Resource usage
    if HAS_PSUTIL and process:
        results["cpu_percent"] = process.cpu_percent(interval=0.1)
        mem_info = process.memory_info()
        results["memory_mb"] = mem_info.rss / (1024 * 1024)

    # Print results
    print()
    print("=== Pipeline Benchmark Results ===")
    for key, value in results.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    # KPI checks
    print()
    print("=== KPI Check ===")

    if cameras == 1:
        checks = [
            ("Median FPS >= 15", results["fps_median_min"] >= 15),
            ("P95 FPS >= 10", results["fps_p95_min"] >= 10),
            ("Latency median <= 200ms", results["latency_median_ms_max"] <= 200),
            ("Latency P95 <= 200ms", results["latency_p95_ms_max"] <= 200),
        ]
    else:
        checks = [
            (f"Per-Camera Median FPS >= 10 ({cameras} cams)", results["fps_median_min"] >= 10),
            (f"Per-Camera P95 FPS >= 5 ({cameras} cams)", results["fps_p95_min"] >= 5),
            (f"Latency median <= 300ms ({cameras} cams)", results["latency_median_ms_max"] <= 300),
            (f"Latency P95 <= 300ms ({cameras} cams)", results["latency_p95_ms_max"] <= 300),
        ]
        if HAS_PSUTIL:
            checks.append(
                (f"CPU <= 90% ({cameras} cams)", results.get("cpu_percent", 0) <= 90),
            )
            checks.append(
                (f"Memory <= 768MB ({cameras} cams)", results.get("memory_mb", 0) <= 768),
            )

    all_passed = True
    for name, passed in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n  All KPIs passed!")
    else:
        print("\n  Some KPIs failed.")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--cameras", type=int, default=1,
                        help="Number of parallel camera pipelines to simulate")
    args = parser.parse_args()
    run_benchmark(args.duration, args.cameras)
