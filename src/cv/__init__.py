"""Computer Vision pipeline modules for Dart-Vision."""

from src.cv.board_calibration import BoardCalibrationManager
from src.cv.camera_calibration import CameraCalibrationManager
from src.cv.capture import ThreadedCamera
from src.cv.calibration import CalibrationManager
from src.cv.roi import ROIProcessor
from src.cv.motion import MotionDetector
from src.cv.detector import DartImpactDetector, DartDetection
from src.cv.geometry import BoardGeometry, BoardHit, BoardPose, CameraIntrinsics, PolarCoord
from src.cv.pipeline import DartPipeline
from src.cv.remapping import CombinedRemapper
from src.cv.replay import ReplayCamera
from src.cv.stereo_calibration import StereoResult, stereo_calibrate, detect_charuco_corners
from src.cv.stereo_utils import CameraParams, TriangulationResult, triangulate_point, point_3d_to_board_2d
from src.cv.multi_camera import MultiCameraPipeline

__all__ = [
    "BoardCalibrationManager",
    "CameraCalibrationManager",
    "ThreadedCamera",
    "ReplayCamera",
    "CalibrationManager",
    "ROIProcessor",
    "MotionDetector",
    "DartImpactDetector",
    "DartDetection",
    "BoardGeometry",
    "BoardHit",
    "BoardPose",
    "CameraIntrinsics",
    "PolarCoord",
    "CombinedRemapper",
    "DartPipeline",
    "StereoResult",
    "stereo_calibrate",
    "detect_charuco_corners",
    "CameraParams",
    "TriangulationResult",
    "triangulate_point",
    "point_3d_to_board_2d",
    "MultiCameraPipeline",
]
