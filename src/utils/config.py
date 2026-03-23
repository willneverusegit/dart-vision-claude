"""Config loader/writer with atomic file operations."""

from __future__ import annotations

import os
import tempfile
import yaml
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "calibration_config.yaml"
)

MULTI_CAM_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "multi_cam.yaml"
)


def validate_matrix_shape(data, expected_rows: int, expected_cols: int,
                          name: str) -> str | None:
    """Return error string if data doesn't match expected matrix shape, None if OK."""
    if not isinstance(data, list) or len(data) != expected_rows:
        return f"{name}: expected {expected_rows} rows, got {type(data).__name__} len={len(data) if isinstance(data, list) else '?'}"
    for i, row in enumerate(data):
        if not isinstance(row, list) or len(row) != expected_cols:
            row_len = len(row) if isinstance(row, list) else "?"
            return f"{name}[{i}]: expected {expected_cols} cols, got {row_len}"
        for j, val in enumerate(row):
            if not isinstance(val, (int, float)):
                return f"{name}[{i}][{j}]: expected number, got {type(val).__name__}"
    return None


def validate_calibration_config(config: dict) -> list[str]:
    """Validate calibration config structure. Returns list of warnings/errors."""
    errors: list[str] = []
    if not isinstance(config, dict):
        return [f"Config root is not a dict: {type(config).__name__}"]

    cameras = config.get("cameras")
    if cameras is None:
        return errors  # no cameras section, nothing to validate
    if not isinstance(cameras, dict):
        return [f"'cameras' is not a dict: {type(cameras).__name__}"]

    for profile_name, profile in cameras.items():
        if not isinstance(profile, dict):
            errors.append(f"Profile '{profile_name}' is not a dict")
            continue

        # camera_matrix: 3x3
        if "camera_matrix" in profile:
            err = validate_matrix_shape(profile["camera_matrix"], 3, 3,
                                        f"profiles.{profile_name}.camera_matrix")
            if err:
                errors.append(err)

        # dist_coeffs: list of floats (flat) or list of lists of floats
        if "dist_coeffs" in profile:
            dc = profile["dist_coeffs"]
            if isinstance(dc, list):
                for i, item in enumerate(dc):
                    if isinstance(item, list):
                        for j, v in enumerate(item):
                            if not isinstance(v, (int, float)):
                                errors.append(
                                    f"profiles.{profile_name}.dist_coeffs[{i}][{j}]: "
                                    f"expected number, got {type(v).__name__}"
                                )
                    elif not isinstance(item, (int, float)):
                        errors.append(
                            f"profiles.{profile_name}.dist_coeffs[{i}]: "
                            f"expected number or list, got {type(item).__name__}"
                        )
            else:
                errors.append(f"profiles.{profile_name}.dist_coeffs: expected list")

        # board_transform: R_cb 3x3, t_cb 3x1
        if "board_transform" in profile:
            bt = profile["board_transform"]
            if isinstance(bt, dict):
                if "R_cb" in bt:
                    err = validate_matrix_shape(bt["R_cb"], 3, 3,
                                                f"profiles.{profile_name}.board_transform.R_cb")
                    if err:
                        errors.append(err)
                if "t_cb" in bt:
                    err = validate_matrix_shape(bt["t_cb"], 3, 1,
                                                f"profiles.{profile_name}.board_transform.t_cb")
                    if err:
                        errors.append(err)
            else:
                errors.append(f"profiles.{profile_name}.board_transform: expected dict")

    return errors


def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load YAML config from file. Returns empty dict if file doesn't exist."""
    if not os.path.exists(path):
        logger.info("Config file not found: %s — using defaults", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    result = data if data else {}
    warnings = validate_calibration_config(result)
    for w in warnings:
        logger.warning("Config validation: %s", w)
    return result


def save_config(data: dict, path: str = DEFAULT_CONFIG_PATH) -> None:
    """Atomically write config to YAML file (temp-file + os.replace)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=os.path.dirname(path), suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False)
        os.replace(tmp_path, path)
        logger.info("Config saved to %s", path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_multi_cam_config(path: str = MULTI_CAM_CONFIG_PATH) -> dict:
    """Load multi-camera extrinsic parameters."""
    return load_config(path)


# ── Sync/Depth presets ──────────────────────────────────────────────
SYNC_DEPTH_PRESETS: dict[str, dict[str, float]] = {
    "tight":    {"max_time_diff_s": 0.200, "depth_tolerance_m": 0.050},
    "standard": {"max_time_diff_s": 0.500, "depth_tolerance_m": 0.300},
    "loose":    {"max_time_diff_s": 1.000, "depth_tolerance_m": 0.500},
}


def get_sync_depth_config(path: str = MULTI_CAM_CONFIG_PATH) -> dict[str, float]:
    """Load sync/depth fusion parameters from multi_cam.yaml.

    Resolves preset first, then applies any explicit overrides.
    Returns dict with keys: max_time_diff_s, depth_tolerance_m.
    Falls back to 'standard' preset if nothing is configured.
    """
    cfg = load_multi_cam_config(path)
    sd = cfg.get("sync_depth", {}) or {}

    preset_name = sd.get("preset", "standard")
    base = dict(SYNC_DEPTH_PRESETS.get(preset_name, SYNC_DEPTH_PRESETS["standard"]))

    # Explicit overrides beat preset
    for key in ("max_time_diff_s", "depth_tolerance_m"):
        if key in sd and sd[key] is not None:
            base[key] = float(sd[key])

    return base


def get_governor_config(path: str = MULTI_CAM_CONFIG_PATH) -> dict:
    """Load FPS governor settings from multi_cam.yaml.

    Returns dict with keys: secondary_target_fps, min_fps, buffer_max_depth.
    Falls back to sensible defaults.
    """
    cfg = load_multi_cam_config(path)
    gov = cfg.get("governor", {}) or {}
    return {
        "secondary_target_fps": int(gov.get("secondary_target_fps", 15)),
        "min_fps": int(gov.get("min_fps", 10)),
        "buffer_max_depth": int(gov.get("buffer_max_depth", 5)),
    }


def save_multi_cam_config(data: dict, path: str = MULTI_CAM_CONFIG_PATH) -> None:
    """Atomically save multi-camera extrinsic parameters."""
    save_config(data, path)


def get_stereo_pair(cam_a: str, cam_b: str,
                    path: str = MULTI_CAM_CONFIG_PATH) -> dict | None:
    """Load extrinsics for a specific camera pair. Order-independent key lookup."""
    cfg = load_multi_cam_config(path)
    pairs = cfg.get("pairs", {})
    key_ab = f"{cam_a}--{cam_b}"
    key_ba = f"{cam_b}--{cam_a}"
    return pairs.get(key_ab) or pairs.get(key_ba)


def save_stereo_pair(cam_a: str, cam_b: str, R: list, T: list,
                     reprojection_error: float, *,
                     calibration_method: str | None = None,
                     quality_level: str | None = None,
                     intrinsics_source: str | None = None,
                     pose_consistency_px: float | None = None,
                     warning: str | None = None,
                     path: str = MULTI_CAM_CONFIG_PATH) -> None:
    """Save extrinsics for a camera pair."""
    err = validate_matrix_shape(R, 3, 3, "R")
    if err:
        raise ValueError(err)
    # T: accept 3x1 nested or flat length-3
    if isinstance(T, list) and len(T) == 3 and all(isinstance(v, (int, float)) for v in T):
        pass  # flat [x, y, z] is fine
    else:
        err = validate_matrix_shape(T, 3, 1, "T")
        if err:
            raise ValueError(err)
    if not isinstance(reprojection_error, (int, float)) or reprojection_error < 0:
        raise ValueError(f"reprojection_error must be >= 0, got {reprojection_error}")
    from datetime import datetime, timezone
    cfg = load_multi_cam_config(path)
    if "pairs" not in cfg:
        cfg["pairs"] = {}
    key = f"{cam_a}--{cam_b}"
    pair_payload = {
        "R": R,
        "T": T,
        "reprojection_error": reprojection_error,
        "calibrated_utc": datetime.now(timezone.utc).isoformat(),
    }
    if calibration_method is not None:
        pair_payload["calibration_method"] = calibration_method
    if quality_level is not None:
        pair_payload["quality_level"] = quality_level
    if intrinsics_source is not None:
        pair_payload["intrinsics_source"] = intrinsics_source
    if pose_consistency_px is not None:
        pair_payload["pose_consistency_px"] = float(pose_consistency_px)
    if warning is not None:
        pair_payload["warning"] = warning
    cfg["pairs"][key] = pair_payload
    cfg.setdefault("schema_version", 2)
    save_multi_cam_config(cfg, path)


def get_board_transform(cam_id: str, path: str = MULTI_CAM_CONFIG_PATH) -> dict | None:
    """Load per-camera board pose (R_cb, t_cb) from multi_cam.yaml.

    Returns a dict with keys 'R_cb' and 't_cb' (as nested lists), or None
    if the camera has not been board-pose calibrated yet.
    """
    cfg = load_multi_cam_config(path)
    cam_cfg = cfg.get("cameras", {}).get(cam_id, {})
    return cam_cfg.get("board_transform")


def save_board_transform(cam_id: str, R_cb: list, t_cb: list,
                         path: str = MULTI_CAM_CONFIG_PATH) -> None:
    """Atomically save per-camera board pose transform (R_cb, t_cb)."""
    err = validate_matrix_shape(R_cb, 3, 3, "R_cb")
    if err:
        raise ValueError(err)
    # t_cb: accept 3x1 nested or flat length-3
    if isinstance(t_cb, list) and len(t_cb) == 3 and all(isinstance(v, (int, float)) for v in t_cb):
        pass
    else:
        err = validate_matrix_shape(t_cb, 3, 1, "t_cb")
        if err:
            raise ValueError(err)
    cfg = load_multi_cam_config(path)
    cfg.setdefault("cameras", {}).setdefault(cam_id, {})
    cfg["cameras"][cam_id]["board_transform"] = {
        "R_cb": R_cb,
        "t_cb": t_cb,
    }
    cfg["schema_version"] = 2
    save_multi_cam_config(cfg, path)
    logger.info("Board transform saved for camera '%s'", cam_id)


def save_last_cameras(cameras: list[dict], path: str = MULTI_CAM_CONFIG_PATH) -> None:
    """Persist the last-used multi-camera configuration for quick re-start."""
    cfg = load_multi_cam_config(path)
    # Store only camera_id + src (no runtime state)
    cfg["last_cameras"] = [
        {"camera_id": c.get("camera_id", ""), "src": c.get("src", 0)}
        for c in cameras
    ]
    save_multi_cam_config(cfg, path)
    logger.info("Saved last_cameras config (%d cameras)", len(cameras))


def get_last_cameras(path: str = MULTI_CAM_CONFIG_PATH) -> list[dict]:
    """Load last-used multi-camera configuration. Returns [] if none saved."""
    cfg = load_multi_cam_config(path)
    return cfg.get("last_cameras", [])


def get_startup_cameras(path: str = MULTI_CAM_CONFIG_PATH) -> list[dict] | None:
    """Return camera list for multi-pipeline startup, or None for single-cam mode.

    Reads the 'startup' section of multi_cam.yaml. Returns None unless
    startup.mode == 'multi' and at least 2 cameras are configured.
    """
    cfg = load_multi_cam_config(path)
    startup = cfg.get("startup", {})
    if startup.get("mode") != "multi":
        return None
    cameras = startup.get("cameras", [])
    return cameras if len(cameras) >= 2 else None
