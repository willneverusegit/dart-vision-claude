"""Unit tests for DartImpactDetector."""

import pytest
import numpy as np
import cv2
from src.cv.detector import DartImpactDetector, DartDetection


@pytest.fixture
def detector():
    return DartImpactDetector(confirmation_frames=3, position_tolerance_px=20)


class TestDartImpactDetector:
    def _make_mask_with_blob(self, center: tuple[int, int], radius: int = 15,
                              size: tuple[int, int] = (400, 400)) -> np.ndarray:
        """Create a motion mask with a white blob (simulated dart)."""
        mask = np.zeros(size, dtype=np.uint8)
        cv2.circle(mask, center, radius, 255, -1)
        return mask

    def test_no_detection_without_motion(self, detector):
        """Empty motion mask should return None."""
        empty_mask = np.zeros((400, 400), dtype=np.uint8)
        roi = np.zeros((400, 400), dtype=np.uint8)
        result = detector.detect(roi, empty_mask)
        assert result is None

    def test_single_frame_no_confirmation(self, detector):
        """Single frame with dart should not confirm (need 3 frames)."""
        mask = self._make_mask_with_blob((200, 200))
        roi = np.zeros((400, 400), dtype=np.uint8)
        result = detector.detect(roi, mask)
        assert result is None  # Only 1 frame, need 3

    def test_confirmation_after_3_frames(self, detector):
        """Dart at same position for 3 frames should be confirmed."""
        mask = self._make_mask_with_blob((200, 200))
        roi = np.zeros((400, 400), dtype=np.uint8)

        # Frame 1 and 2: no confirmation yet
        detector.detect(roi, mask)
        detector.detect(roi, mask)

        # Frame 3: should confirm
        result = detector.detect(roi, mask)
        assert result is not None
        assert isinstance(result, DartDetection)
        assert result.frame_count >= 3

    def test_moving_object_no_confirmation(self, detector):
        """Object moving between frames should not confirm."""
        roi = np.zeros((400, 400), dtype=np.uint8)

        # Different positions each frame (far apart)
        for pos in [(50, 50), (200, 200), (350, 350)]:
            mask = self._make_mask_with_blob(pos)
            result = detector.detect(roi, mask)

        assert result is None  # Positions differ too much

    def test_reset_clears_state(self, detector):
        """Reset should clear all candidates and confirmations."""
        mask = self._make_mask_with_blob((200, 200))
        roi = np.zeros((400, 400), dtype=np.uint8)

        detector.detect(roi, mask)
        detector.detect(roi, mask)
        detector.reset()

        # After reset, should need 3 new frames
        result = detector.detect(roi, mask)
        assert result is None

    def test_small_blob_filtered(self, detector):
        """Very small blob (below min_area) should be ignored."""
        mask = np.zeros((400, 400), dtype=np.uint8)
        cv2.circle(mask, (200, 200), 1, 255, -1)  # Tiny, ~3 pixels
        roi = np.zeros((400, 400), dtype=np.uint8)

        for _ in range(5):
            result = detector.detect(roi, mask)
        assert result is None


def test_register_confirmed_adds_detection():
    from src.cv.detector import DartImpactDetector, DartDetection
    d = DartImpactDetector()
    det = DartDetection(center=(10, 10), area=200, confidence=0.8, frame_count=3)
    result = d.register_confirmed(det)
    assert result is True
    assert len(d.get_all_confirmed()) == 1


def test_register_confirmed_deduplicates():
    from src.cv.detector import DartImpactDetector, DartDetection
    d = DartImpactDetector()
    det = DartDetection(center=(10, 10), area=200, confidence=0.8, frame_count=3)
    d.register_confirmed(det)
    result = d.register_confirmed(det)  # same position again
    assert result is False
    assert len(d.get_all_confirmed()) == 1
