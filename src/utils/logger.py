"""Structured logging setup for Dart-Vision."""

import logging
import os
import sys
import uuid
from logging.handlers import RotatingFileHandler

# Session ID: unique per process start, included in all log lines
SESSION_ID = uuid.uuid4().hex[:8]


def setup_logging(
    level: int = logging.INFO,
    json_format: bool = False,
    log_file: str | None = None,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
) -> None:
    """Configure structured logging (idempotent — safe to call multiple times).

    Args:
        level: Logging level (default INFO).
        json_format: If True, emit JSON lines for production/log aggregation.
        log_file: Optional path for rotating file log. None = stdout only.
        max_bytes: Max size per log file before rotation (default 5MB).
        backup_count: Number of rotated backups to keep (default 3).
    """
    root = logging.getLogger()

    # Idempotent: skip if handlers already configured by us
    if any(getattr(h, "_dartvision", False) for h in root.handlers):
        root.setLevel(level)
        return

    if json_format:
        fmt = (
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"session":"' + SESSION_ID + '",'
            '"module":"%(name)s","message":"%(message)s"}'
        )
        datefmt = "%Y-%m-%dT%H:%M:%S"
    else:
        fmt = f"%(asctime)s [{SESSION_ID}] [%(levelname)s] %(name)s: %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # Stdout handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler._dartvision = True  # type: ignore[attr-defined]
    root.addHandler(stream_handler)

    # Optional file handler with rotation
    if log_file is not None:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler._dartvision = True  # type: ignore[attr-defined]
        root.addHandler(file_handler)

    root.setLevel(level)
