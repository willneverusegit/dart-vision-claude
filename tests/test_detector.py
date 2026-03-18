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


class TestAreaRangeExtended:
    """P12: Extended area range and ROI scaling tests."""

    def _make_mask_with_blob(self, center, radius, size=(400, 400)):
        mask = np.zeros(size, dtype=np.uint8)
        cv2.circle(mask, center, radius, 255, -1)
        return mask

    def test_default_area_max_is_2000(self):
        d = DartImpactDetector()
        assert d.area_max == 2000

    def test_large_dart_detected_with_new_default(self):
        """A blob with area ~1454 should pass the filter with area_max=2000."""
        d = DartImpactDetector(confirmation_frames=1, area_max=2000)
        mask = self._make_mask_with_blob((200, 200), radius=22)
        roi = np.zeros((400, 400), dtype=np.uint8)
        # First call adds candidate, second call confirms (confirmation_frames=1)
        d.detect(roi, mask)
        result = d.detect(roi, mask)
        assert result is not None

    def test_very_large_blob_filtered(self):
        """A blob exceeding area_max should be filtered out."""
        d = DartImpactDetector(confirmation_frames=1, area_max=500)
        # radius 20 gives area ~1256, well above 500
        mask = self._make_mask_with_blob((200, 200), radius=20)
        roi = np.zeros((400, 400), dtype=np.uint8)
        d.detect(roi, mask)
        result = d.detect(roi, mask)
        assert result is None

    def test_small_bull_blob_detected(self):
        """Small blob (outer-bull size) should be detected with low area_min."""
        d = DartImpactDetector(confirmation_frames=1, area_min=5, area_max=2000)
        # radius 3 gives area ~20
        mask = self._make_mask_with_blob((200, 200), radius=3)
        roi = np.zeros((400, 400), dtype=np.uint8)
        d.detect(roi, mask)
        result = d.detect(roi, mask)
        assert result is not None

    def test_scale_area_to_roi_doubles_for_800x800(self):
        """800x800 ROI should scale area range by 4x vs 400x400 reference."""
        d = DartImpactDetector(area_min=10, area_max=2000)
        d.scale_area_to_roi(800, 800, reference_size=400)
        assert d.area_min == 40
        assert d.area_max == 8000

    def test_scale_area_to_roi_halves_for_200x200(self):
        """200x200 ROI should scale area range by 0.25x."""
        d = DartImpactDetector(area_min=10, area_max=2000)
        d.scale_area_to_roi(200, 200, reference_size=400)
        assert d.area_min == 2  # int(10 * 0.25) = 2
        assert d.area_max == 500

    def test_scale_area_min_never_zero(self):
        """area_min should be at least 1 after scaling."""
        d = DartImpactDetector(area_min=1, area_max=2000)
        d.scale_area_to_roi(50, 50, reference_size=400)
        assert d.area_min >= 1
        assert d.area_max > d.area_min

    def test_confidence_high_for_area_2000(self):
        """Area 2000 should give full area_score in compute_dart_confidence."""
        from src.cv.detector import compute_dart_confidence
        # Create a simple rectangular contour with known area
        contour = np.array([[[0, 0]], [[50, 0]], [[50, 40]], [[0, 40]]], dtype=np.int32)
        area = cv2.contourArea(contour)  # 2000
        conf = compute_dart_confidence(contour, area)
        assert conf > 0.0  # Should not be penalized for area


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


def test_is_already_confirmed_delegates_to_cooldown_manager():
    """P51: _is_already_confirmed delegates to CooldownManager.is_in_exclusion_zone,
    not to the _confirmed list. Verify by checking that clearing _confirmed
    does NOT affect exclusion checks (zones live in CooldownManager)."""
    from src.cv.detector import DartImpactDetector, DartDetection
    d = DartImpactDetector(exclusion_zone_px=50, cooldown_frames=30)
    det = DartDetection(center=(100, 100), area=200, confidence=0.8, frame_count=3)
    d.register_confirmed(det)

    # Exclusion is active via CooldownManager
    nearby = DartDetection(center=(110, 110), area=200, confidence=0.8, frame_count=3)
    assert d._is_already_confirmed(nearby) is True

    # Clear _confirmed list (turn state) — exclusion should STILL hold
    d._confirmed.clear()
    assert d._is_already_confirmed(nearby) is True

    # Far away detection is not excluded
    far = DartDetection(center=(300, 300), area=200, confidence=0.8, frame_count=3)
    assert d._is_already_confirmed(far) is False


def test_confirmed_list_only_used_for_turn_state():
    """P51: _confirmed list is only for get_all_confirmed (turn state),
    not for spatial exclusion logic."""
    from src.cv.detector import DartImpactDetector, DartDetection
    d = DartImpactDetector(exclusion_zone_px=50, cooldown_frames=30)
    det1 = DartDetection(center=(100, 100), area=200, confidence=0.8, frame_count=3)
    det2 = DartDetection(center=(300, 300), area=200, confidence=0.8, frame_count=3)

    d.register_confirmed(det1)
    # Wait out cooldown for det2
    for _ in range(31):
        d.tick()
    d.register_confirmed(det2)

    confirmed = d.get_all_confirmed()
    assert len(confirmed) == 2
    centers = {c.center for c in confirmed}
    assert (100, 100) in centers
    assert (300, 300) in centers
