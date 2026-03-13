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
    cfg["schema_version"] = 1
    save_multi_cam_config(cfg, path)
