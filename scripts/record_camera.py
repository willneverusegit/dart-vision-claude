"""Record video from a camera for later replay testing.

Usage:
    python scripts/record_camera.py                          # Camera 0, default settings
    python scripts/record_camera.py --source 1 --duration 60 # Camera 1, 60 seconds
    python scripts/record_camera.py --output mytest.mp4      # Custom filename
    python scripts/record_camera.py --resolution 1280x720    # Custom resolution
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.cv.recorder import VideoRecorder  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Record camera video for testing")
    parser.add_argument("--source", type=int, default=0, help="Camera index (default: 0)")
    parser.add_argument("--output", default=None, help="Output filename (auto-generated if omitted)")
    parser.add_argument("--output-dir", default="testvids", help="Output directory (default: testvids)")
    parser.add_argument("--duration", type=int, default=0,
                        help="Recording duration in seconds (0 = until Ctrl+C)")
    parser.add_argument("--fps", type=float, default=30.0, help="Target FPS (default: 30)")
    parser.add_argument("--resolution", default=None,
                        help="Camera resolution WxH, e.g. 640x480 or 1280x720")
    parser.add_argument("--show", action="store_true", help="Show live preview window")
    args = parser.parse_args()

    # Open camera
    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        print(f"Fehler: Kamera {args.source} konnte nicht geoeffnet werden")
        sys.exit(1)

    # Set resolution if specified
    if args.resolution:
        try:
            w, h = args.resolution.lower().split("x")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(w))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(h))
        except ValueError:
            print(f"Ungueltige Aufloesung: {args.resolution} (erwartet WxH, z.B. 640x480)")
            sys.exit(1)

    # Read first frame to get actual resolution
    ret, frame = cap.read()
    if not ret or frame is None:
        print("Fehler: Kein Frame von Kamera erhalten")
        cap.release()
        sys.exit(1)

    h, w = frame.shape[:2]
    print(f"Kamera {args.source}: {w}x{h}")

    # Start recording
    recorder = VideoRecorder(output_dir=args.output_dir)
    output_path = recorder.start(
        filename=args.output,
        fps=args.fps,
        frame_size=(w, h),
    )
    print(f"Aufnahme: {output_path}")
    if args.duration > 0:
        print(f"Dauer: {args.duration}s")
    else:
        print("Druecke Ctrl+C zum Beenden")
    print()

    # Write first frame
    recorder.write(frame)

    try:
        t0 = time.monotonic()
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("\nKamera-Feed unterbrochen")
                break

            recorder.write(frame)

            if args.show:
                # Show frame count overlay
                text = f"REC {recorder.frame_count} | {recorder.elapsed_s:.0f}s"
                cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 0, 255), 2)
                cv2.imshow("Recording", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            # Duration limit
            if args.duration > 0 and (time.monotonic() - t0) >= args.duration:
                print(f"\n{args.duration}s erreicht")
                break

            # Status every 5 seconds
            elapsed = time.monotonic() - t0
            if recorder.frame_count % (int(args.fps) * 5) == 0 and recorder.frame_count > 0:
                avg_fps = recorder.frame_count / elapsed if elapsed > 0 else 0
                print(f"  {recorder.frame_count} Frames | {elapsed:.0f}s | {avg_fps:.1f} fps",
                      end="\r")

    except KeyboardInterrupt:
        print("\n")

    # Stop
    summary = recorder.stop()
    cap.release()
    if args.show:
        cv2.destroyAllWindows()

    print(f"Gespeichert: {summary['output_path']}")
    print(f"  {summary['frame_count']} Frames, {summary['elapsed_s']}s, {summary['avg_fps']} fps")

    # File size
    if os.path.exists(summary["output_path"]):
        size_mb = os.path.getsize(summary["output_path"]) / (1024 * 1024)
        print(f"  Dateigroesse: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
