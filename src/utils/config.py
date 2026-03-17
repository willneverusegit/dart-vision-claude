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


def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    """Load YAML config from file. Returns empty dict if file doesn't exist."""
    if not os.path.exists(path):
        logger.info("Config file not found: %s — using defaults", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if data else {}


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
                     reprojection_error: float,
                     path: str = MULTI_CAM_CONFIG_PATH) -> None:
    """Save extrinsics for a camera pair."""
    from datetime import datetime, timezone
    cfg = load_multi_cam_config(path)
    if "pairs" not in cfg:
        cfg["pairs"] = {}
    key = f"{cam_a}--{cam_b}"
    cfg["pairs"][key] = {
        "R": R,
        "T": T,
        "reprojection_error": reprojection_error,
        "calibrated_utc": datetime.now(timezone.utc).isoformat(),
    }
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
