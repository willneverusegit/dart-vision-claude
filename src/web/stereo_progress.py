"""Stereo calibration progress tracker with quality assessment."""
import logging

logger = logging.getLogger(__name__)


class StereoProgressTracker:
    @staticmethod
    def quality_assessment(rms: float) -> dict:
        if rms < 0.5:
            return {"quality": "excellent", "label": "Exzellent", "recommendation": "Kalibrierung ist sehr genau."}
        elif rms < 1.0:
            return {"quality": "good", "label": "Gut", "recommendation": "Kalibrierung ist genuegend genau fuer Triangulation."}
        elif rms < 2.0:
            return {"quality": "acceptable", "label": "Akzeptabel", "recommendation": "Kalibrierung nutzbar, Wiederholung mit besserer Board-Sichtbarkeit empfohlen."}
        else:
            return {"quality": "poor", "label": "Schlecht", "recommendation": "Kalibrierung wiederholen. Board muss in beiden Kameras gut sichtbar sein."}

    @staticmethod
    def frame_progress(
        frame_idx: int,
        total: int,
        detected_a: bool,
        detected_b: bool,
        *,
        valid_pairs: int = 0,
        phase: str = "capture",
    ) -> dict:
        """Build a progress event dict for stereo calibration frame capture.

        Args:
            frame_idx: Current frame index (0-based).
            total: Total frames to capture.
            detected_a: Whether ChArUco board was detected in camera A.
            detected_b: Whether ChArUco board was detected in camera B.
            valid_pairs: Number of frame pairs where both cameras detected the board.
            phase: Current phase ('capture' or 'computing').
        """
        both_detected = detected_a and detected_b
        if not detected_a and not detected_b:
            error = "Board in keiner Kamera erkannt"
        elif not detected_a:
            error = "Board nicht in Kamera A erkannt"
        elif not detected_b:
            error = "Board nicht in Kamera B erkannt"
        else:
            error = None

        return {
            "type": "stereo_progress",
            "frame_idx": frame_idx,
            "total": total,
            "detected_a": detected_a,
            "detected_b": detected_b,
            "both_detected": both_detected,
            "valid_pairs": valid_pairs,
            "phase": phase,
            "error": error,
            "percent": round((frame_idx + 1) / total * 100),
        }

    @staticmethod
    def calibration_result(rms: float, pairs_used: int, cam_a: str, cam_b: str) -> dict:
        assessment = StereoProgressTracker.quality_assessment(rms)
        return {"type": "stereo_result", "rms": round(rms, 4), "pairs_used": pairs_used, "camera_a": cam_a, "camera_b": cam_b, **assessment}
