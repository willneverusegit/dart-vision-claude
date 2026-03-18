"""Camera health monitoring for multi-camera pipeline."""
import time
import logging

logger = logging.getLogger(__name__)


class CameraHealthMonitor:
    """Monitor per-camera health in multi-camera pipeline."""
    LOW_FPS_THRESHOLD = 10.0

    def check_health(self, multi_pipeline) -> dict[str, dict]:
        result = {}
        errors = multi_pipeline.get_camera_errors()
        pipelines = multi_pipeline.get_pipelines()
        for cfg in multi_pipeline.camera_configs:
            cam_id = cfg["camera_id"]
            error_info = errors.get(cam_id)
            # Support both old str format and new dict format
            if isinstance(error_info, dict):
                error_msg = error_info.get("message", "")
                error_level = error_info.get("level", "error")
            elif isinstance(error_info, str):
                error_msg = error_info
                error_level = "error"
            else:
                error_msg = None
                error_level = None
            pipeline = pipelines.get(cam_id)
            fps = 0.0
            if pipeline is not None and hasattr(pipeline, 'get_stats'):
                stats = pipeline.get_stats()
                fps = stats.get("fps", 0.0)
            if error_msg and error_level == "error":
                status = "red"
            elif error_msg and error_level == "warning":
                status = "yellow"
            elif fps > 0 and fps < self.LOW_FPS_THRESHOLD:
                status = "yellow"
            else:
                status = "green"
            result[cam_id] = {"status": status, "error": error_msg, "fps": round(fps, 1), "timestamp": round(time.time(), 2)}
        return result
