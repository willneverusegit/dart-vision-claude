"""Multi-camera pipeline: coordinate multiple DartPipelines and fuse results."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import numpy as np

from src.cv.geometry import BOARD_RADIUS_MM, BoardGeometry
from src.cv.pipeline import DartPipeline
from src.cv.stereo_utils import (
    CameraParams,
    point_3d_to_board_2d,
    transform_to_board_frame,
    triangulate_point,
)
from src.utils.config import get_board_transform, get_stereo_pair

logger = logging.getLogger(__name__)

MAX_DETECTION_TIME_DIFF_S = 0.15
MAX_BUFFERED_DETECTIONS_PER_CAMERA = 3
DETECTION_BUFFER_RETENTION_S = 2.0

_TARGET_FPS = 30
_FRAME_INTERVAL_S = 1.0 / _TARGET_FPS

BOARD_DEPTH_TOLERANCE_M = 0.015


class MultiCameraPipeline:
    """Orchestrate multiple DartPipeline instances and fuse detections."""

    def __init__(
        self,
        camera_configs: list[dict],
        on_multi_dart_detected: Callable[[dict], None] | None = None,
        debug: bool = False,
    ) -> None:
        self.camera_configs = camera_configs
        self.on_multi_dart_detected = on_multi_dart_detected
        self.debug = debug

        self._pipelines: dict[str, DartPipeline] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._detection_buffer: dict[str, dict | list[dict]] = {}
        self._buffer_lock = threading.Lock()
        self._running = False
        self._fusion_thread: threading.Thread | None = None
        self._camera_errors: dict[str, str] = {}

        self._stereo_params: dict[str, CameraParams] = {}
        self._board_transforms: dict[str, dict] = {}

    def start(self) -> None:
        """Start all camera pipelines in separate threads."""
        self._running = True

        for cfg in self.camera_configs:
            cam_id = cfg["camera_id"]
            src = cfg.get("src", 0)

            pipeline = DartPipeline(
                camera_src=src,
                on_dart_detected=lambda score, det, _id=cam_id: self._on_single_detection(_id, score, det),
                debug=self.debug,
                capture_width=cfg.get("capture_width"),
                capture_height=cfg.get("capture_height"),
                capture_fps=cfg.get("capture_fps"),
            )

            from src.cv.board_calibration import BoardCalibrationManager
            from src.cv.camera_calibration import CameraCalibrationManager

            pipeline.board_calibration = BoardCalibrationManager(camera_id=cam_id)
            pipeline.camera_calibration = CameraCalibrationManager(camera_id=cam_id)

            self._pipelines[cam_id] = pipeline

            thread = threading.Thread(
                target=self._run_pipeline_loop,
                args=(cam_id, pipeline),
                daemon=True,
                name=f"cv-pipeline-{cam_id}",
            )
            self._threads[cam_id] = thread
            thread.start()
            logger.info("Pipeline started for camera '%s' (src=%s)", cam_id, src)

        self._fusion_thread = threading.Thread(target=self._fusion_loop, daemon=True, name="cv-fusion")
        self._fusion_thread.start()
        self._load_extrinsics()

    def stop(self) -> None:
        """Stop all pipelines."""
        self._running = False
        for cam_id, pipeline in self._pipelines.items():
            pipeline.stop()
            logger.info("Pipeline stopped for camera '%s'", cam_id)
        for thread in self._threads.values():
            thread.join(timeout=5.0)
        if self._fusion_thread:
            self._fusion_thread.join(timeout=5.0)

    def _run_pipeline_loop(self, cam_id: str, pipeline: DartPipeline) -> None:
        """Frame processing loop for a single camera, rate-limited to _TARGET_FPS."""
        try:
            pipeline.start()
        except Exception as exc:
            logger.warning("Camera '%s' failed to start: %s", cam_id, exc)
            self._camera_errors[cam_id] = str(exc)
            return

        while self._running:
            started_at = time.monotonic()
            try:
                pipeline.process_frame()
            except Exception as exc:
                logger.debug("Frame error on '%s': %s", cam_id, exc)
            elapsed = time.monotonic() - started_at
            sleep_s = max(0.0, _FRAME_INTERVAL_S - elapsed)
            if sleep_s > 0:
                time.sleep(sleep_s)

    def _load_extrinsics(self) -> None:
        """Load stereo pair extrinsics and board transforms from config files."""
        for cfg in self.camera_configs:
            cam_id = cfg["camera_id"]
            board_transform = get_board_transform(cam_id)
            if board_transform is not None:
                try:
                    self._board_transforms[cam_id] = {
                        "R_cb": np.array(board_transform["R_cb"], dtype=np.float64).reshape(3, 3),
                        "t_cb": np.array(board_transform["t_cb"], dtype=np.float64).reshape(3),
                    }
                    logger.info("Loaded board_transform for camera '%s'", cam_id)
                except Exception as exc:
                    logger.warning("Invalid board_transform for '%s': %s", cam_id, exc)
            else:
                logger.warning(
                    "No board_transform found for camera '%s' - triangulation will be skipped",
                    cam_id,
                )

        for index, cfg_a in enumerate(self.camera_configs):
            for cfg_b in self.camera_configs[index + 1:]:
                cam_a = cfg_a["camera_id"]
                cam_b = cfg_b["camera_id"]
                pair_data = get_stereo_pair(cam_a, cam_b)
                if pair_data is None:
                    logger.warning(
                        "No stereo pair data for '%s'--'%s' - triangulation disabled for this pair",
                        cam_a,
                        cam_b,
                    )
                    continue

                pipe_a = self._pipelines.get(cam_a)
                pipe_b = self._pipelines.get(cam_b)
                if pipe_a is None or pipe_b is None:
                    continue

                intr_a = pipe_a.camera_calibration.get_intrinsics()
                intr_b = pipe_b.camera_calibration.get_intrinsics()
                if intr_a is None or intr_b is None:
                    logger.warning(
                        "Missing intrinsics for '%s' or '%s' - triangulation disabled for this pair",
                        cam_a,
                        cam_b,
                    )
                    continue

                self._stereo_params[cam_a] = CameraParams(
                    camera_id=cam_a,
                    camera_matrix=intr_a.camera_matrix,
                    dist_coeffs=intr_a.dist_coeffs,
                    R=np.eye(3, dtype=np.float64),
                    T=np.zeros((3, 1), dtype=np.float64),
                )
                self._stereo_params[cam_b] = CameraParams(
                    camera_id=cam_b,
                    camera_matrix=intr_b.camera_matrix,
                    dist_coeffs=intr_b.dist_coeffs,
                    R=np.array(pair_data["R"], dtype=np.float64).reshape(3, 3),
                    T=np.array(pair_data["T"], dtype=np.float64).reshape(3, 1),
                )
                logger.info("Loaded stereo params for pair '%s'--'%s'", cam_a, cam_b)

    def _on_single_detection(self, camera_id: str, score_result: dict, detection) -> None:
        """Callback from a single pipeline. Buffer detections for short burst fusion."""
        with self._buffer_lock:
            now = time.time()
            entry = {
                "camera_id": camera_id,
                "score_result": score_result,
                "detection": detection,
                "timestamp": now,
            }
            entries = self._camera_entries_locked(camera_id)
            entries.append(entry)
            entries = [
                candidate
                for candidate in entries
                if (now - candidate["timestamp"]) <= DETECTION_BUFFER_RETENTION_S
            ]
            if len(entries) > MAX_BUFFERED_DETECTIONS_PER_CAMERA:
                entries = entries[-MAX_BUFFERED_DETECTIONS_PER_CAMERA:]
            self._set_camera_entries_locked(camera_id, entries)

    def _camera_entries_locked(self, camera_id: str) -> list[dict]:
        value = self._detection_buffer.get(camera_id)
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        return [value]

    def _set_camera_entries_locked(self, camera_id: str, entries: list[dict]) -> None:
        if not entries:
            self._detection_buffer.pop(camera_id, None)
        elif len(entries) == 1:
            self._detection_buffer[camera_id] = entries[0]
        else:
            self._detection_buffer[camera_id] = entries

    def _flatten_detection_buffer_locked(self) -> list[dict]:
        entries: list[dict] = []
        for camera_id in list(self._detection_buffer.keys()):
            entries.extend(self._camera_entries_locked(camera_id))
        entries.sort(key=lambda entry: entry["timestamp"])
        return entries

    def _prune_detection_buffer_locked(self, now: float) -> None:
        for camera_id in list(self._detection_buffer.keys()):
            entries = [
                entry
                for entry in self._camera_entries_locked(camera_id)
                if (now - entry["timestamp"]) <= DETECTION_BUFFER_RETENTION_S
            ]
            self._set_camera_entries_locked(camera_id, entries)

    def _matching_entries_locked(self, anchor: dict) -> list[dict]:
        matches = [anchor]
        anchor_ts = anchor["timestamp"]
        for camera_id in list(self._detection_buffer.keys()):
            if camera_id == anchor["camera_id"]:
                continue
            candidates = [
                entry
                for entry in self._camera_entries_locked(camera_id)
                if abs(entry["timestamp"] - anchor_ts) <= MAX_DETECTION_TIME_DIFF_S
            ]
            if candidates:
                matches.append(min(candidates, key=lambda entry: abs(entry["timestamp"] - anchor_ts)))
        return matches

    def _remove_entries_locked(self, entries_to_remove: list[dict]) -> None:
        grouped: dict[str, list[dict]] = {}
        for entry in entries_to_remove:
            grouped.setdefault(entry["camera_id"], []).append(entry)

        for camera_id, removable in grouped.items():
            remaining = [
                entry
                for entry in self._camera_entries_locked(camera_id)
                if all(entry is not doomed for doomed in removable)
            ]
            self._set_camera_entries_locked(camera_id, remaining)

    def _fusion_loop(self) -> None:
        """Periodically check detection buffer and fuse multi-camera results."""
        while self._running:
            time.sleep(0.05)
            self._try_fuse()

    def _try_fuse(self) -> None:
        """Attempt to fuse detections from multiple cameras."""
        with self._buffer_lock:
            now = time.time()
            self._prune_detection_buffer_locked(now)
            entries = self._flatten_detection_buffer_locked()
            if not entries:
                return

            anchor = entries[0]
            matched_entries = self._matching_entries_locked(anchor)
            if len(matched_entries) < 2:
                age = now - anchor["timestamp"]
                if age <= MAX_DETECTION_TIME_DIFF_S:
                    return
                result = dict(anchor["score_result"])
                result["source"] = "single" if len(self._detection_buffer) == 1 else "single_timeout"
                result["camera_id"] = anchor["camera_id"]
                logger.info(
                    "Timeout fallback: camera_id='%s' age=%.3fs matched_cameras=%d",
                    anchor["camera_id"],
                    age,
                    len(matched_entries),
                )
                self._emit(result)
                self._remove_entries_locked([anchor])
                return

            cam_params = self._stereo_params
            triangulated = False
            for i in range(len(matched_entries)):
                for j in range(i + 1, len(matched_entries)):
                    p1 = cam_params.get(matched_entries[i]["camera_id"])
                    p2 = cam_params.get(matched_entries[j]["camera_id"])
                    if p1 is None or p2 is None:
                        continue

                    det1 = matched_entries[i]["detection"]
                    det2 = matched_entries[j]["detection"]
                    if det1 is None or det2 is None:
                        continue

                    tri = triangulate_point(det1.center, det2.center, p1, p2)
                    if not tri.valid:
                        continue

                    board_transform = self._board_transforms.get(matched_entries[i]["camera_id"])
                    if board_transform is None:
                        logger.debug(
                            "No board_transform for camera '%s' - skipping triangulation",
                            matched_entries[i]["camera_id"],
                        )
                        continue

                    p_board = transform_to_board_frame(
                        tri.point_3d,
                        board_transform["R_cb"],
                        board_transform["t_cb"],
                    )
                    if abs(p_board[2]) > BOARD_DEPTH_TOLERANCE_M:
                        logger.info(
                            "Triangulation Z implausible in board frame (Z=%.4f m) for cameras '%s','%s' - voting fallback",
                            p_board[2],
                            matched_entries[i]["camera_id"],
                            matched_entries[j]["camera_id"],
                        )
                        continue

                    board_x_mm, board_y_mm = point_3d_to_board_2d(p_board)
                    pipeline_1 = self._pipelines.get(matched_entries[i]["camera_id"])
                    if pipeline_1 and pipeline_1.geometry:
                        geo = pipeline_1.geometry
                        radius_px = geo.double_outer_radius_px
                        mm_per_px = BOARD_RADIUS_MM / radius_px if radius_px > 0 else 1.0
                        ox, oy = geo.optical_center_px
                        roi_x = ox + board_x_mm / mm_per_px
                        roi_y = oy + board_y_mm / mm_per_px
                        hit = geo.point_to_score(roi_x, roi_y)
                        result = geo.hit_to_dict(hit)
                        result["source"] = "triangulation"
                        result["reprojection_error"] = tri.reprojection_error
                        logger.info(
                            "Triangulation: cameras='%s','%s' reproj=%.2f Z_board=%.4f",
                            matched_entries[i]["camera_id"],
                            matched_entries[j]["camera_id"],
                            tri.reprojection_error,
                            p_board[2],
                        )
                        self._emit(result)
                        triangulated = True
                        break
                if triangulated:
                    break

            if not triangulated:
                result = self._voting_fallback(matched_entries)
                self._emit(result)

            self._remove_entries_locked(matched_entries)

    def _voting_fallback(self, entries: list[dict]) -> dict:
        """When triangulation fails, use confidence-weighted voting."""
        confidences = []
        for entry in entries:
            detection = entry.get("detection")
            confidence = getattr(detection, "confidence", 0.0) if detection else 0.0
            confidences.append(confidence)

        total_conf = sum(confidences)
        if total_conf > 0 and all("total_score" in entry.get("score_result", {}) for entry in entries):
            scores = [entry["score_result"]["total_score"] for entry in entries]
            if len(entries) >= 3:
                sorted_scores = sorted(scores)
                mid = len(sorted_scores) // 2
                if len(sorted_scores) % 2 == 0:
                    weighted_score = (sorted_scores[mid - 1] + sorted_scores[mid]) / 2.0
                else:
                    weighted_score = sorted_scores[mid]
                logger.info("Voting fallback: median score=%s from %d cameras", weighted_score, len(entries))
            else:
                weighted_score = sum(score * conf for score, conf in zip(scores, confidences)) / total_conf
                logger.info(
                    "Voting fallback: weighted score=%.1f (conf=%.2f,%.2f)",
                    weighted_score,
                    *confidences,
                )

            best_idx = confidences.index(max(confidences))
            result = dict(entries[best_idx]["score_result"])
            result["total_score"] = int(round(weighted_score))
            result["source"] = "voting_fallback"
            result["camera_id"] = entries[best_idx]["camera_id"]
            return result

        best_idx = confidences.index(max(confidences))
        best = entries[best_idx]
        result = dict(best["score_result"])
        result["source"] = "voting_fallback"
        result["camera_id"] = best["camera_id"]
        logger.info(
            "Voting fallback: best confidence camera_id='%s' (conf=%.2f)",
            best["camera_id"],
            confidences[best_idx],
        )
        return result

    def _emit(self, score_result: dict) -> None:
        """Emit fused detection via callback."""
        if self.on_multi_dart_detected:
            self.on_multi_dart_detected(score_result)

    def reset_all(self) -> None:
        """Reset detectors on all pipelines (darts removed)."""
        for pipeline in self._pipelines.values():
            pipeline.reset_turn()
        with self._buffer_lock:
            self._detection_buffer.clear()

    def reload_stereo_params(self) -> None:
        """Hot-reload stereo extrinsics and board transforms from config files."""
        logger.info("Reloading stereo extrinsics and board transforms...")
        self._stereo_params.clear()
        self._board_transforms.clear()
        self._load_extrinsics()
        logger.info(
            "Stereo params reloaded: %d camera params, %d board transforms",
            len(self._stereo_params),
            len(self._board_transforms),
        )

    def get_pipelines(self) -> dict[str, DartPipeline]:
        """Expose individual pipelines for frame access, overlays, etc."""
        return dict(self._pipelines)

    def get_camera_errors(self) -> dict[str, str]:
        """Return dict of camera_id -> error message for cameras that failed to start."""
        return dict(self._camera_errors)
