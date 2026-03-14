"""Structured logging setup for Dart-Vision."""

import logging
import sys


def setup_logging(level: int = logging.INFO, json_format: bool = False) -> None:
    """Configure structured logging to stdout.

    Args:
        level: Logging level (default INFO).
        json_format: If True, emit JSON lines for production/log aggregation.
    """
    if json_format:
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
            '"module":"%(name)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
