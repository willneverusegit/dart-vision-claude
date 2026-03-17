"""Dart-Vision Systemdiagnose — prueft Abhaengigkeiten, Kameras und Konfiguration.

Aufruf: python -m src.diagnose
"""

import os
import sys


def check_python_version() -> tuple[bool, str]:
    """Pruefe Python-Version (mind. 3.10)."""
    v = sys.version_info
    ok = v >= (3, 10)
    msg = f"Python {v.major}.{v.minor}.{v.micro}"
    if not ok:
        msg += " — FEHLER: Mindestens Python 3.10 erforderlich"
    return ok, msg


def check_dependencies() -> list[tuple[bool, str]]:
    """Pruefe ob alle kritischen Abhaengigkeiten importierbar sind."""
    deps = [
        ("cv2", "opencv-contrib-python"),
        ("numpy", "numpy"),
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("yaml", "pyyaml"),
        ("jinja2", "jinja2"),
        ("websockets", "websockets"),
    ]
    results = []
    for module, pip_name in deps:
        try:
            m = __import__(module)
            version = getattr(m, "__version__", "?")
            results.append((True, f"{pip_name} ({version})"))
        except ImportError:
            results.append((False, f"{pip_name} — FEHLT (pip install {pip_name})"))
    return results


def check_cameras(max_index: int = 5) -> list[tuple[int, bool, str]]:
    """Pruefe verfuegbare Kameras (Index 0 bis max_index-1)."""
    try:
        import cv2
    except ImportError:
        return [(-1, False, "OpenCV nicht verfuegbar — Kamera-Check uebersprungen")]

    results = []
    for idx in range(max_index):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            results.append((idx, True, f"{w}x{h} @ {fps:.0f}fps"))
        else:
            cap.release()
    return results


def check_config_files() -> list[tuple[bool, str]]:
    """Pruefe ob wichtige Konfigurationsdateien vorhanden sind."""
    files = [
        ("config/calibration_config.yaml", "Board-Kalibrierung"),
        ("config/multi_cam.yaml", "Multi-Cam-Konfiguration"),
    ]
    results = []
    for path, label in files:
        exists = os.path.isfile(path)
        if exists:
            size = os.path.getsize(path)
            results.append((True, f"{label}: {path} ({size} Bytes)"))
        else:
            results.append((False, f"{label}: {path} — nicht vorhanden"))
    return results


def check_calibration_valid() -> tuple[bool, str]:
    """Pruefe ob eine gueltige Board-Kalibrierung geladen werden kann."""
    try:
        from src.cv.board_calibration import BoardCalibrationManager
        bcm = BoardCalibrationManager()
        if bcm.is_valid():
            return True, "Board-Kalibrierung gueltig"
        return False, "Board-Kalibrierung nicht gueltig — bitte im Browser kalibrieren"
    except Exception as e:
        return False, f"Kalibrierungs-Check fehlgeschlagen: {e}"


def run_diagnostics() -> dict:
    """Fuehre alle Diagnose-Checks aus und gib strukturiertes Ergebnis zurueck."""
    results = {"ok": True, "checks": []}

    # Python
    ok, msg = check_python_version()
    results["checks"].append({"name": "Python", "ok": ok, "detail": msg})
    if not ok:
        results["ok"] = False

    # Dependencies
    for ok, msg in check_dependencies():
        results["checks"].append({"name": "Abhaengigkeit", "ok": ok, "detail": msg})
        if not ok:
            results["ok"] = False

    # Cameras
    cameras = check_cameras()
    if cameras and cameras[0][0] == -1:
        results["checks"].append({"name": "Kameras", "ok": False, "detail": cameras[0][2]})
    elif not cameras:
        results["checks"].append({"name": "Kameras", "ok": False, "detail": "Keine Kamera gefunden (Index 0-4)"})
        results["ok"] = False
    else:
        for idx, ok, detail in cameras:
            results["checks"].append({"name": f"Kamera {idx}", "ok": ok, "detail": detail})

    # Config files
    for ok, msg in check_config_files():
        results["checks"].append({"name": "Konfiguration", "ok": ok, "detail": msg})

    # Calibration
    ok, msg = check_calibration_valid()
    results["checks"].append({"name": "Kalibrierung", "ok": ok, "detail": msg})

    return results


def print_diagnostics(results: dict) -> None:
    """Gib Diagnose-Ergebnis formatiert auf der Konsole aus."""
    print()
    print("=" * 50)
    print("  Dart-Vision Systemdiagnose")
    print("=" * 50)
    print()

    for check in results["checks"]:
        icon = "[OK]" if check["ok"] else "[!!]"
        print(f"  {icon} {check['name']}: {check['detail']}")

    print()
    if results["ok"]:
        print("  Ergebnis: System bereit!")
    else:
        print("  Ergebnis: Probleme gefunden — siehe oben.")
    print()


def main():
    results = run_diagnostics()
    print_diagnostics(results)
    sys.exit(0 if results["ok"] else 1)


if __name__ == "__main__":
    main()
