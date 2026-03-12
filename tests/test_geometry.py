"""Tests for board-centric geometry model."""

from src.cv.geometry import BoardGeometry, BoardPose


def test_board_pose_from_config():
    pose = BoardPose.from_config(
        {
            "center_px": [200, 200],
            "radii_px": [10, 20, 100, 110, 180, 200],
            "rotation_deg": 5.0,
            "optical_center_roi_px": [202, 198],
            "valid": True,
            "method": "aruco",
        }
    )
    assert pose.valid
    assert pose.optical_center_roi_px == (202.0, 198.0)
    assert pose.radii_px[-1] == 200.0


def test_geometry_normalize_and_polar():
    geometry = BoardGeometry(
        roi_size=(400, 400),
        center_px=(200.0, 200.0),
        optical_center_px=(200.0, 200.0),
        radii_px=(10.0, 20.0, 100.0, 110.0, 180.0, 200.0),
        rotation_deg=0.0,
        valid=True,
        method="manual",
    )

    nx, ny = geometry.normalize_point(200.0, 200.0)
    assert round(nx, 4) == 0.0
    assert round(ny, 4) == 0.0

    radius_norm, angle_deg = geometry.point_to_polar(200.0, 100.0)
    assert 0.49 <= radius_norm <= 0.51
    assert angle_deg == 0.0
