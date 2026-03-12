"""Computer Vision pipeline modules for Dart-Vision."""

from src.cv.board_calibration import BoardCalibrationManager
from src.cv.camera_calibration import CameraCalibrationManager
from src.cv.capture import ThreadedCamera
from src.cv.calibration import CalibrationManager
from src.cv.roi import ROIProcessor
from src.cv.motion import MotionDetector
from src.cv.detector import DartImpactDetector, DartDetection
from src.cv.field_mapper import FieldMapper
from src.cv.geometry import BoardGeometry, BoardPose, CameraIntrinsics
from src.cv.pipeline import DartPipeline
from src.cv.remapping import CombinedRemapper
from src.cv.replay import ReplayCamera

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
    "FieldMapper",
    "BoardGeometry",
    "BoardPose",
    "CameraIntrinsics",
    "CombinedRemapper",
    "DartPipeline",
]
