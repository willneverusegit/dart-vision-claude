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
            error = errors.get(cam_id)
            pipeline = pipelines.get(cam_id)
            fps = 0.0
            if pipeline is not None and hasattr(pipeline, 'get_stats'):
                stats = pipeline.get_stats()
                fps = stats.get("fps", 0.0)
            if error:
                status = "red"
            elif fps > 0 and fps < self.LOW_FPS_THRESHOLD:
                status = "yellow"
            else:
                status = "green"
            result[cam_id] = {"status": status, "error": error, "fps": round(fps, 1), "timestamp": round(time.time(), 2)}
        return result
