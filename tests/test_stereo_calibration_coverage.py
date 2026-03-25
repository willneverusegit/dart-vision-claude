"""Coverage tests for stereo_calibration.py — targets untested branches."""

import numpy as np
import cv2
import pytest

from src.cv.stereo_calibration import (
    CharucoBoardSpec,
    CharucoDetectionResult,
    BoardPoseEstimate,
    DEFAULT_CHARUCO_BOARD_SPEC,
    LARGE_MARKER_CHARUCO_BOARD_SPEC,
    PORTRAIT_CHARUCO_BOARD_SPEC,
    PORTRAIT_LARGE_MARKER_CHARUCO_BOARD_SPEC,
    ProvisionalStereoResult,
    StereoResult,
    _average_stereo_extrinsics,
    _canonical_preset_name,
    detect_charuco_board,
    estimate_charuco_board_pose,
    provisional_stereo_calibrate,
    resolve_charuco_board_candidates,
    resolve_charuco_board_spec,
    stereo_calibrate,
    stereo_from_board_poses,
    validate_stereo_prerequisites,
)
from src.cv.geometry import CameraIntrinsics


# ---------------------------------------------------------------------------
# CharucoBoardSpec validation and methods
# ---------------------------------------------------------------------------

class TestCharucoBoardSpecValidation:
    """Test __post_init__ validation rules."""

    def test_squares_x_too_small(self):
        with pytest.raises(ValueError, match="at least 2x2"):
            CharucoBoardSpec(1, 5, 0.04, 0.02)

    def test_squares_y_too_small(self):
        with pytest.raises(ValueError, match="at least 2x2"):
            CharucoBoardSpec(5, 1, 0.04, 0.02)

    def test_negative_square_length(self):
        with pytest.raises(ValueError, match="positive"):
            CharucoBoardSpec(5, 5, -0.04, 0.02)

    def test_zero_marker_length(self):
        with pytest.raises(ValueError, match="positive"):
            CharucoBoardSpec(5, 5, 0.04, 0.0)

    def test_marker_not_smaller_than_square(self):
        with pytest.raises(ValueError, match="smaller than"):
            CharucoBoardSpec(5, 5, 0.04, 0.04)

    def test_marker_larger_than_square(self):
        with pytest.raises(ValueError, match="smaller than"):
            CharucoBoardSpec(5, 5, 0.04, 0.05)

    def test_valid_spec_no_error(self):
        spec = CharucoBoardSpec(5, 5, 0.04, 0.02)
        assert spec.squares_x == 5


class TestCharucoBoardSpecMethods:
    """Test to_config_fragment, to_api_payload, create_dictionary, create_board."""

    def test_to_config_fragment(self):
        frag = DEFAULT_CHARUCO_BOARD_SPEC.to_config_fragment()
        assert frag["charuco_preset"] == "7x5_40x20"
        assert frag["charuco_squares_x"] == 7
        assert frag["charuco_squares_y"] == 5
        assert isinstance(frag["charuco_square_length_m"], float)
        assert isinstance(frag["charuco_marker_length_m"], float)

    def test_to_api_payload(self):
        payload = DEFAULT_CHARUCO_BOARD_SPEC.to_api_payload()
        assert payload["preset"] == "7x5_40x20"
        assert payload["squares_x"] == 7
        assert payload["squares_y"] == 5
        assert payload["square_length_mm"] == pytest.approx(40.0)
        assert payload["marker_length_mm"] == pytest.approx(20.0)
        assert payload["dictionary"] == "DICT_6X6_250"

    def test_to_api_payload_large_marker(self):
        payload = LARGE_MARKER_CHARUCO_BOARD_SPEC.to_api_payload()
        assert payload["marker_length_mm"] == pytest.approx(28.0)

    def test_create_dictionary(self):
        d = DEFAULT_CHARUCO_BOARD_SPEC.create_dictionary()
        assert d is not None

    def test_create_board(self):
        board = DEFAULT_CHARUCO_BOARD_SPEC.create_board()
        size = board.getChessboardSize()
        assert tuple(size) == (7, 5)

    def test_create_board_with_dictionary(self):
        d = DEFAULT_CHARUCO_BOARD_SPEC.create_dictionary()
        board = DEFAULT_CHARUCO_BOARD_SPEC.create_board(dictionary=d)
        assert board is not None


# ---------------------------------------------------------------------------
# _canonical_preset_name
# ---------------------------------------------------------------------------

class TestCanonicalPresetName:
    def test_known_preset_matches(self):
        assert _canonical_preset_name(DEFAULT_CHARUCO_BOARD_SPEC) == "7x5_40x20"

    def test_custom_returns_custom(self):
        custom = CharucoBoardSpec(3, 3, 0.05, 0.03, preset_name="whatever")
        assert _canonical_preset_name(custom) == "custom"

    def test_portrait_preset(self):
        assert _canonical_preset_name(PORTRAIT_CHARUCO_BOARD_SPEC) == "5x7_40x20"

    def test_portrait_large_marker(self):
        assert _canonical_preset_name(PORTRAIT_LARGE_MARKER_CHARUCO_BOARD_SPEC) == "5x7_40x28"


# ---------------------------------------------------------------------------
# resolve_charuco_board_spec edge cases
# ---------------------------------------------------------------------------

class TestResolveCharucoBoardSpec:
    def test_with_board_spec_parameter(self):
        spec = resolve_charuco_board_spec(board_spec=LARGE_MARKER_CHARUCO_BOARD_SPEC)
        assert spec == LARGE_MARKER_CHARUCO_BOARD_SPEC

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            resolve_charuco_board_spec(preset="nonexistent")

    def test_default_when_no_args(self):
        spec = resolve_charuco_board_spec()
        assert spec == DEFAULT_CHARUCO_BOARD_SPEC

    def test_config_overrides_squares(self):
        spec = resolve_charuco_board_spec(
            config={"charuco_squares_x": 5, "charuco_squares_y": 7}
        )
        assert spec.squares_x == 5
        assert spec.squares_y == 7

    def test_square_length_mm_override(self):
        spec = resolve_charuco_board_spec(square_length_mm=50.0)
        assert spec.square_length_m == pytest.approx(0.05)

    def test_marker_length_mm_override(self):
        spec = resolve_charuco_board_spec(marker_length_mm=25.0)
        assert spec.marker_length_m == pytest.approx(0.025)


# ---------------------------------------------------------------------------
# resolve_charuco_board_candidates edge cases
# ---------------------------------------------------------------------------

class TestResolveCharucoBoardCandidates:
    def test_with_board_spec(self):
        candidates = resolve_charuco_board_candidates(
            board_spec=LARGE_MARKER_CHARUCO_BOARD_SPEC
        )
        assert len(candidates) == 1
        assert candidates[0] == LARGE_MARKER_CHARUCO_BOARD_SPEC

    def test_non_auto_preset(self):
        candidates = resolve_charuco_board_candidates(preset="7x5_40x28")
        assert len(candidates) == 1
        assert candidates[0] == LARGE_MARKER_CHARUCO_BOARD_SPEC

    def test_auto_deduplicates(self):
        candidates = resolve_charuco_board_candidates(preset="auto")
        names = [c.preset_name for c in candidates]
        assert len(names) == len(set(names))

    def test_auto_with_mm_overrides(self):
        candidates = resolve_charuco_board_candidates(
            preset="auto", square_length_mm=50.0
        )
        for c in candidates:
            assert c.square_length_m == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# detect_charuco_board edge cases
# ---------------------------------------------------------------------------

class TestDetectCharucoBoardEdgeCases:
    def test_empty_candidates_list(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = detect_charuco_board(frame, board_specs=[])
        assert not result.interpolation_ok
        assert result.warning is not None
        # Empty list falls through to default board_spec via resolve, no markers found
        assert "charuco" in result.warning.lower() or "konfiguriert" in result.warning.lower()

    def test_grayscale_input(self):
        frame = np.zeros((100, 100), dtype=np.uint8)
        result = detect_charuco_board(frame, board_spec=DEFAULT_CHARUCO_BOARD_SPEC)
        assert not result.interpolation_ok

    def test_no_markers_found(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = detect_charuco_board(frame, board_spec=DEFAULT_CHARUCO_BOARD_SPEC)
        assert result.markers_found == 0
        assert "charuco" in result.warning.lower() or "sichtbar" in result.warning.lower()

    def test_few_markers_warning(self, monkeypatch):
        """When markers < min_markers, warning mentions count."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        class FakeDetector:
            def detectMarkers(self, _gray):
                corners = [np.zeros((1, 4, 2), dtype=np.float32)]
                ids = np.array([[0], [1]], dtype=np.int32)
                return corners, ids, None

        monkeypatch.setattr(
            "src.cv.stereo_calibration._build_aruco_detector",
            lambda _d: FakeDetector(),
        )
        result = detect_charuco_board(frame, board_spec=DEFAULT_CHARUCO_BOARD_SPEC, min_markers=4)
        assert not result.interpolation_ok
        assert result.markers_found == 2
        assert "2" in result.warning

    def test_markers_ok_but_no_interpolation(self, monkeypatch):
        """Enough markers, but no charuco corners interpolated — multi-candidate path."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        class FakeDetector:
            def detectMarkers(self, _gray):
                corners = [np.zeros((1, 4, 2), dtype=np.float32)] * 5
                ids = np.arange(5, dtype=np.int32).reshape(-1, 1)
                return corners, ids, None

        monkeypatch.setattr(
            "src.cv.stereo_calibration._build_aruco_detector",
            lambda _d: FakeDetector(),
        )
        monkeypatch.setattr(
            "src.cv.stereo_calibration.cv2.aruco.interpolateCornersCharuco",
            lambda _c, _i, _g, _b: (0, None, None),
        )
        result = detect_charuco_board(frame, preset="auto")
        assert not result.interpolation_ok
        assert result.board_spec is None  # multi-candidate, 0 corners -> None
        assert "interpoliert" in result.warning.lower()

    def test_few_corners_warning(self, monkeypatch):
        """Corners found but < min_corners."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        class FakeDetector:
            def detectMarkers(self, _gray):
                corners = [np.zeros((1, 4, 2), dtype=np.float32)] * 5
                ids = np.arange(5, dtype=np.int32).reshape(-1, 1)
                return corners, ids, None

        monkeypatch.setattr(
            "src.cv.stereo_calibration._build_aruco_detector",
            lambda _d: FakeDetector(),
        )
        monkeypatch.setattr(
            "src.cv.stereo_calibration.cv2.aruco.interpolateCornersCharuco",
            lambda _c, _i, _g, _b: (
                2,
                np.zeros((2, 1, 2), dtype=np.float32),
                np.array([[0], [1]], dtype=np.int32),
            ),
        )
        result = detect_charuco_board(
            frame, board_spec=DEFAULT_CHARUCO_BOARD_SPEC, min_corners=4
        )
        assert not result.interpolation_ok
        assert result.charuco_corners_found == 2
        assert "2" in result.warning

    def test_single_candidate_no_markers_returns_spec(self):
        """Single candidate with no markers still returns the board_spec."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = detect_charuco_board(frame, board_spec=DEFAULT_CHARUCO_BOARD_SPEC)
        assert result.board_spec == DEFAULT_CHARUCO_BOARD_SPEC


# ---------------------------------------------------------------------------
# estimate_charuco_board_pose
# ---------------------------------------------------------------------------

class TestEstimateCharucoBoardPose:
    @pytest.fixture
    def intrinsics(self):
        K = np.array([[500, 0, 320], [0, 500, 240], [0, 0, 1]], dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        return CameraIntrinsics(camera_matrix=K, dist_coeffs=D, valid=True)

    def test_none_intrinsics(self):
        detection = CharucoDetectionResult(
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            charuco_corners=np.zeros((10, 1, 2), dtype=np.float32),
            charuco_ids=np.arange(10).reshape(-1, 1),
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=10,
            interpolation_ok=True,
        )
        assert estimate_charuco_board_pose(detection, None) is None

    def test_no_board_spec(self, intrinsics):
        detection = CharucoDetectionResult(
            board_spec=None,
            charuco_corners=None,
            charuco_ids=None,
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=0,
            interpolation_ok=False,
        )
        assert estimate_charuco_board_pose(detection, intrinsics) is None

    def test_interpolation_not_ok(self, intrinsics):
        detection = CharucoDetectionResult(
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            charuco_corners=None,
            charuco_ids=None,
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=0,
            interpolation_ok=False,
        )
        assert estimate_charuco_board_pose(detection, intrinsics) is None

    def test_too_few_ids(self, intrinsics):
        detection = CharucoDetectionResult(
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            charuco_corners=np.zeros((2, 1, 2), dtype=np.float32),
            charuco_ids=np.array([[0], [1]], dtype=np.int32),
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=2,
            interpolation_ok=True,
        )
        assert estimate_charuco_board_pose(detection, intrinsics) is None

    def test_success_with_synthetic_points(self, intrinsics):
        """Create synthetic image points from known board corners and verify pose."""
        spec = DEFAULT_CHARUCO_BOARD_SPEC
        board = spec.create_board()
        obj_pts = board.getChessboardCorners()

        # Use first 8 corners
        ids = np.arange(8)
        obj_subset = obj_pts[ids].reshape(-1, 3).astype(np.float64)

        # Place board at z=0.3m in front of camera
        rvec = np.array([[0.1], [-0.05], [0.02]], dtype=np.float64)
        tvec = np.array([[0.0], [0.0], [0.3]], dtype=np.float64)
        img_pts, _ = cv2.projectPoints(
            obj_subset, rvec, tvec,
            intrinsics.camera_matrix, intrinsics.dist_coeffs,
        )

        detection = CharucoDetectionResult(
            board_spec=spec,
            charuco_corners=img_pts.reshape(-1, 1, 2).astype(np.float32),
            charuco_ids=ids.reshape(-1, 1).astype(np.int32),
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=8,
            interpolation_ok=True,
        )
        pose = estimate_charuco_board_pose(detection, intrinsics)
        assert pose is not None
        assert isinstance(pose, BoardPoseEstimate)
        assert pose.R.shape == (3, 3)
        assert pose.t.shape == (3,)
        assert pose.corner_count == 8
        assert pose.reprojection_error_px < 1.0
        assert pose.board_spec == spec

    def test_cv2_error_returns_none(self, intrinsics, monkeypatch):
        """cv2.solvePnP raising cv2.error should return None."""
        spec = DEFAULT_CHARUCO_BOARD_SPEC

        def fake_solvePnP(*args, **kwargs):
            raise cv2.error("synthetic test error")

        monkeypatch.setattr("src.cv.stereo_calibration.cv2.solvePnP", fake_solvePnP)

        detection = CharucoDetectionResult(
            board_spec=spec,
            charuco_corners=np.random.rand(8, 1, 2).astype(np.float32) * 600,
            charuco_ids=np.arange(8).reshape(-1, 1).astype(np.int32),
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=8,
            interpolation_ok=True,
        )
        assert estimate_charuco_board_pose(detection, intrinsics) is None

    def test_solvePnP_fails_returns_none(self, intrinsics, monkeypatch):
        """solvePnP returning success=False."""
        spec = DEFAULT_CHARUCO_BOARD_SPEC

        monkeypatch.setattr(
            "src.cv.stereo_calibration.cv2.solvePnP",
            lambda *a, **kw: (False, None, None),
        )

        detection = CharucoDetectionResult(
            board_spec=spec,
            charuco_corners=np.random.rand(8, 1, 2).astype(np.float32) * 600,
            charuco_ids=np.arange(8).reshape(-1, 1).astype(np.int32),
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=8,
            interpolation_ok=True,
        )
        assert estimate_charuco_board_pose(detection, intrinsics) is None


# ---------------------------------------------------------------------------
# stereo_from_board_poses
# ---------------------------------------------------------------------------

class TestStereoFromBoardPoses:
    def test_identity_poses(self):
        """Two identical poses → R=I, T=0."""
        pose = BoardPoseEstimate(
            R=np.eye(3, dtype=np.float64),
            t=np.array([0, 0, 0.3], dtype=np.float64),
            rvec=np.zeros((3, 1), dtype=np.float64),
            tvec=np.array([[0], [0], [0.3]], dtype=np.float64),
            reprojection_error_px=0.1,
            corner_count=8,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        )
        R, T = stereo_from_board_poses(pose, pose)
        np.testing.assert_allclose(R, np.eye(3), atol=1e-10)
        np.testing.assert_allclose(T, np.zeros((3, 1)), atol=1e-10)

    def test_translation_only(self):
        """Cameras differ only in translation."""
        pose_a = BoardPoseEstimate(
            R=np.eye(3, dtype=np.float64),
            t=np.array([0, 0, 0.3], dtype=np.float64),
            rvec=np.zeros((3, 1), dtype=np.float64),
            tvec=np.array([[0], [0], [0.3]], dtype=np.float64),
            reprojection_error_px=0.1,
            corner_count=8,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        )
        pose_b = BoardPoseEstimate(
            R=np.eye(3, dtype=np.float64),
            t=np.array([0.1, 0, 0.3], dtype=np.float64),
            rvec=np.zeros((3, 1), dtype=np.float64),
            tvec=np.array([[0.1], [0], [0.3]], dtype=np.float64),
            reprojection_error_px=0.1,
            corner_count=8,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        )
        R, T = stereo_from_board_poses(pose_a, pose_b)
        np.testing.assert_allclose(R, np.eye(3), atol=1e-10)
        assert T[0, 0] == pytest.approx(0.1, abs=1e-10)

    def test_output_types(self):
        pose = BoardPoseEstimate(
            R=np.eye(3),
            t=np.zeros(3),
            rvec=np.zeros((3, 1)),
            tvec=np.zeros((3, 1)),
            reprojection_error_px=0.0,
            corner_count=4,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        )
        R, T = stereo_from_board_poses(pose, pose)
        assert R.dtype == np.float64
        assert T.dtype == np.float64
        assert T.shape == (3, 1)


# ---------------------------------------------------------------------------
# _average_stereo_extrinsics
# ---------------------------------------------------------------------------

class TestAverageStereoExtrinsics:
    def test_single_pair(self):
        R = np.eye(3, dtype=np.float64)
        T = np.array([[0.1], [0.0], [0.0]], dtype=np.float64)
        R_avg, T_avg = _average_stereo_extrinsics([R], [T])
        np.testing.assert_allclose(R_avg, R, atol=1e-10)
        np.testing.assert_allclose(T_avg, T, atol=1e-10)

    def test_multiple_pairs_averaging(self):
        R1 = np.eye(3, dtype=np.float64)
        R2 = np.eye(3, dtype=np.float64)
        T1 = np.array([[0.1], [0.0], [0.0]], dtype=np.float64)
        T2 = np.array([[0.3], [0.0], [0.0]], dtype=np.float64)
        R_avg, T_avg = _average_stereo_extrinsics([R1, R2], [T1, T2])
        np.testing.assert_allclose(R_avg, np.eye(3), atol=1e-10)
        assert T_avg[0, 0] == pytest.approx(0.2, abs=1e-10)

    def test_negative_determinant_correction(self):
        """When SVD produces negative det, U[:,-1] is flipped."""
        # Create a rotation sum that will produce negative determinant
        # by using a reflection matrix
        R_reflect = np.diag([1.0, 1.0, -1.0])
        T = np.array([[0.1], [0.0], [0.0]], dtype=np.float64)
        R_avg, T_avg = _average_stereo_extrinsics([R_reflect], [T])
        # After correction, det should be positive
        assert np.linalg.det(R_avg) > 0

    def test_output_types(self):
        R = np.eye(3, dtype=np.float32)  # input float32
        T = np.zeros((3, 1), dtype=np.float32)
        R_avg, T_avg = _average_stereo_extrinsics([R], [T])
        assert R_avg.dtype == np.float64
        assert T_avg.dtype == np.float64


# ---------------------------------------------------------------------------
# provisional_stereo_calibrate
# ---------------------------------------------------------------------------

class TestProvisionalStereoCalibrate:
    @pytest.fixture
    def intrinsics(self):
        K = np.array([[500, 0, 320], [0, 500, 240], [0, 0, 1]], dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        return CameraIntrinsics(camera_matrix=K, dist_coeffs=D, valid=True)

    def _make_detection(self, spec, intrinsics, rvec, tvec, n_corners=8):
        """Create a synthetic CharucoDetectionResult with projectable corners."""
        board = spec.create_board()
        obj_pts = board.getChessboardCorners()
        ids = np.arange(n_corners)
        obj_subset = obj_pts[ids].reshape(-1, 3).astype(np.float64)
        img_pts, _ = cv2.projectPoints(
            obj_subset, rvec, tvec,
            intrinsics.camera_matrix, intrinsics.dist_coeffs,
        )
        return CharucoDetectionResult(
            board_spec=spec,
            charuco_corners=img_pts.reshape(-1, 1, 2).astype(np.float32),
            charuco_ids=ids.reshape(-1, 1).astype(np.int32),
            marker_corners=(),
            marker_ids=None,
            markers_found=0,
            charuco_corners_found=n_corners,
            interpolation_ok=True,
        )

    def test_frame_count_mismatch(self, intrinsics):
        det = CharucoDetectionResult(
            board_spec=None, charuco_corners=None, charuco_ids=None,
            marker_corners=(), marker_ids=None, markers_found=0,
            charuco_corners_found=0, interpolation_ok=False,
        )
        result = provisional_stereo_calibrate([det], [], intrinsics, intrinsics)
        assert not result.ok
        assert "mismatch" in result.error_message.lower()

    def test_too_few_usable_pairs(self, intrinsics):
        # Empty detections → no pose pairs
        det = CharucoDetectionResult(
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
            charuco_corners=None, charuco_ids=None,
            marker_corners=(), marker_ids=None, markers_found=0,
            charuco_corners_found=0, interpolation_ok=False,
        )
        dets = [det] * 5
        result = provisional_stereo_calibrate(dets, dets, intrinsics, intrinsics)
        assert not result.ok
        assert "usable" in result.error_message.lower()

    def test_success_with_synthetic_data(self, intrinsics):
        """3+ valid pose pairs should produce ok=True."""
        spec = DEFAULT_CHARUCO_BOARD_SPEC
        rvec_a = np.array([[0.1], [-0.05], [0.02]], dtype=np.float64)
        tvec_a = np.array([[0.0], [0.0], [0.3]], dtype=np.float64)
        rvec_b = np.array([[0.12], [-0.04], [0.01]], dtype=np.float64)
        tvec_b = np.array([[0.08], [0.0], [0.3]], dtype=np.float64)

        dets_a = []
        dets_b = []
        for i in range(4):
            # Vary pose slightly for each frame
            rv_a = rvec_a + np.array([[i * 0.02], [0], [0]], dtype=np.float64)
            rv_b = rvec_b + np.array([[i * 0.02], [0], [0]], dtype=np.float64)
            dets_a.append(self._make_detection(spec, intrinsics, rv_a, tvec_a))
            dets_b.append(self._make_detection(spec, intrinsics, rv_b, tvec_b))

        result = provisional_stereo_calibrate(dets_a, dets_b, intrinsics, intrinsics)
        assert result.ok
        assert result.R is not None
        assert result.T is not None
        assert result.pairs_used >= 3
        assert result.error_message is None

    def test_result_fields(self, intrinsics):
        det = CharucoDetectionResult(
            board_spec=None, charuco_corners=None, charuco_ids=None,
            marker_corners=(), marker_ids=None, markers_found=0,
            charuco_corners_found=0, interpolation_ok=False,
        )
        result = provisional_stereo_calibrate([], [], intrinsics, intrinsics)
        assert isinstance(result, ProvisionalStereoResult)


# ---------------------------------------------------------------------------
# validate_stereo_prerequisites
# ---------------------------------------------------------------------------

class TestValidateStereoPrerequisites:
    def test_both_cameras_invalid(self, tmp_path):
        """No calibration config → both cameras should fail validation."""
        config_path = str(tmp_path / "nonexistent_config.yaml")
        result = validate_stereo_prerequisites("cam_a", "cam_b", config_path=config_path)
        assert result["ready"] is False
        assert len(result["errors"]) >= 1

    def test_returns_dict_with_expected_keys(self, tmp_path):
        config_path = str(tmp_path / "nonexistent_config.yaml")
        result = validate_stereo_prerequisites("cam_a", "cam_b", config_path=config_path)
        assert "ready" in result
        assert "errors" in result
        assert "warnings" in result


# ---------------------------------------------------------------------------
# stereo_calibrate exception paths
# ---------------------------------------------------------------------------

class TestStereoCalibrateExceptionPaths:
    def test_cv2_error_in_stereo_calibrate(self, monkeypatch):
        """stereoCalibrate raising cv2.error is caught gracefully."""
        K = np.eye(3, dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        spec = DEFAULT_CHARUCO_BOARD_SPEC

        # Need to produce enough usable frame pairs to reach stereoCalibrate
        board = spec.create_board()
        obj_pts = board.getChessboardCorners()
        ids = np.arange(8)
        obj_subset = obj_pts[ids].reshape(-1, 3).astype(np.float64)

        rvec = np.array([[0.1], [0.0], [0.0]], dtype=np.float64)
        tvec = np.array([[0.0], [0.0], [0.3]], dtype=np.float64)
        K_real = np.array([[500, 0, 160], [0, 500, 120], [0, 0, 1]], dtype=np.float64)
        img_pts, _ = cv2.projectPoints(obj_subset, rvec, tvec, K_real, D)

        # Monkeypatch detect_charuco_corners to return valid corners
        corners = img_pts.reshape(-1, 1, 2).astype(np.float32)
        charuco_ids = ids.reshape(-1, 1).astype(np.int32)

        monkeypatch.setattr(
            "src.cv.stereo_calibration.detect_charuco_corners",
            lambda *a, **kw: (corners, charuco_ids),
        )

        def fake_stereoCalibrate(*args, **kwargs):
            raise cv2.error("test error")

        monkeypatch.setattr(
            "src.cv.stereo_calibration.cv2.stereoCalibrate",
            fake_stereoCalibrate,
        )

        frames = [np.zeros((240, 320, 3), dtype=np.uint8)] * 5
        result = stereo_calibrate(frames, frames, K_real, D, K_real, D, board_spec=spec)
        assert not result.ok
        assert "failed" in result.error_message.lower()

    def test_non_finite_rms(self, monkeypatch):
        """Non-finite reprojection error is caught."""
        K = np.array([[500, 0, 160], [0, 500, 120], [0, 0, 1]], dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        spec = DEFAULT_CHARUCO_BOARD_SPEC

        board = spec.create_board()
        ids = np.arange(8)
        corners = np.random.rand(8, 1, 2).astype(np.float32) * 300
        charuco_ids = ids.reshape(-1, 1).astype(np.int32)

        monkeypatch.setattr(
            "src.cv.stereo_calibration.detect_charuco_corners",
            lambda *a, **kw: (corners, charuco_ids),
        )

        monkeypatch.setattr(
            "src.cv.stereo_calibration.cv2.stereoCalibrate",
            lambda *a, **kw: (
                float("inf"),  # non-finite rms
                None, None, None, None,
                np.eye(3), np.zeros((3, 1)),
                np.eye(3), np.eye(3),
            ),
        )

        frames = [np.zeros((240, 320, 3), dtype=np.uint8)] * 5
        result = stereo_calibrate(frames, frames, K, D, K, D, board_spec=spec)
        assert not result.ok
        assert "non-finite" in result.error_message.lower()

    def test_stereo_calibrate_success_path(self, monkeypatch):
        """Success path reaches the final return."""
        K = np.array([[500, 0, 160], [0, 500, 120], [0, 0, 1]], dtype=np.float64)
        D = np.zeros((5, 1), dtype=np.float64)
        spec = DEFAULT_CHARUCO_BOARD_SPEC

        ids = np.arange(8)
        corners = np.random.rand(8, 1, 2).astype(np.float32) * 300
        charuco_ids = ids.reshape(-1, 1).astype(np.int32)

        monkeypatch.setattr(
            "src.cv.stereo_calibration.detect_charuco_corners",
            lambda *a, **kw: (corners, charuco_ids),
        )

        monkeypatch.setattr(
            "src.cv.stereo_calibration.cv2.stereoCalibrate",
            lambda *a, **kw: (
                0.42,  # rms
                None, None, None, None,
                np.eye(3), np.array([[0.1], [0], [0]]),
                np.eye(3), np.eye(3),
            ),
        )

        frames = [np.zeros((240, 320, 3), dtype=np.uint8)] * 5
        result = stereo_calibrate(frames, frames, K, D, K, D, board_spec=spec)
        assert result.ok
        assert result.reprojection_error == pytest.approx(0.42)
        np.testing.assert_allclose(result.R, np.eye(3))


# ---------------------------------------------------------------------------
# ProvisionalStereoResult fields
# ---------------------------------------------------------------------------

class TestProvisionalStereoResultFields:
    def test_fields(self):
        r = ProvisionalStereoResult(
            ok=True, R=np.eye(3), T=np.zeros((3, 1)),
            reprojection_error=0.5, pose_consistency_px=0.3,
            pairs_used=5, error_message=None,
        )
        assert r.ok is True
        assert r.pairs_used == 5
        assert r.pose_consistency_px == 0.3


# ---------------------------------------------------------------------------
# BoardPoseEstimate fields
# ---------------------------------------------------------------------------

class TestBoardPoseEstimateFields:
    def test_fields(self):
        pe = BoardPoseEstimate(
            R=np.eye(3), t=np.zeros(3),
            rvec=np.zeros((3, 1)), tvec=np.zeros((3, 1)),
            reprojection_error_px=0.1, corner_count=8,
            board_spec=DEFAULT_CHARUCO_BOARD_SPEC,
        )
        assert pe.reprojection_error_px == 0.1
        assert pe.corner_count == 8
