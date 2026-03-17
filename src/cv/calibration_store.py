"""Shared YAML load/save helpers for calibration config."""

from __future__ import annotations

import logging
import os
import tempfile
import threading

import yaml

from src.cv.calibration_common import default_calibration_config

logger = logging.getLogger(__name__)

_config_file_lock = threading.Lock()


def load_calibration_config(config_path: str, camera_id: str) -> dict:
    """Load one camera's calibration config from disk."""
    config = default_calibration_config()
    if not os.path.exists(config_path):
        return config

    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        if "cameras" in raw and camera_id in raw["cameras"]:
            config.update(raw["cameras"][camera_id])
        elif "cameras" not in raw and raw.get("valid"):
            config.update(raw)
        elif "cameras" not in raw and raw:
            config.update(raw)
    except Exception as exc:
        logger.error("Config load error: %s", exc)
    return config


def save_calibration_config_atomic(config_path: str, camera_id: str, config: dict) -> None:
    """Persist one camera's config atomically in the shared YAML file."""
    with _config_file_lock:
        config_dir = os.path.dirname(os.path.abspath(config_path))
        os.makedirs(config_dir, exist_ok=True)

        full: dict = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as handle:
                    full = yaml.safe_load(handle) or {}
            except Exception:
                full = {}

        if "cameras" not in full:
            old_data = {key: value for key, value in full.items() if key not in ("schema_version",)}
            full = {"schema_version": 3, "cameras": {}}
            if old_data:
                full["cameras"]["default"] = old_data

        full["cameras"][camera_id] = dict(config)
        full["schema_version"] = 3

        fd, temp_path = tempfile.mkstemp(suffix=".yaml", dir=config_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.dump(full, handle, default_flow_style=False)
            os.replace(temp_path, config_path)
            logger.info("Config saved to %s (camera_id=%s)", config_path, camera_id)
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
