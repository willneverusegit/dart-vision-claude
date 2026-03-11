"""Config loader/writer with atomic file operations."""

import os
import tempfile
import yaml
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "calibration_config.yaml"
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
