"""Reusable ChArUco detection helpers shared by calibration workflows."""

from __future__ import annotations

import logging

import cv2


def collect_charuco_frame_observations(
    frames: list,
    board,
    detector,
    *,
    min_marker_count: int = 4,
    min_charuco_corners: int = 4,
    logger: logging.Logger | None = None,
    skip_log_level: str = "debug",
    skip_log_template: str = "Frame %d: only %d markers, skipping",
) -> tuple[list, list, tuple[int, int] | None]:
    """Collect usable ChArUco corner/id observations across multiple frames."""
    all_charuco_corners: list = []
    all_charuco_ids: list = []
    image_size = None

    for index, frame in enumerate(frames):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        if image_size is None:
            image_size = gray.shape[::-1]

        corners, ids, _ = detector.detectMarkers(gray)
        marker_count = 0 if ids is None else len(ids)
        if ids is None or marker_count < min_marker_count:
            if logger is not None:
                log_fn = getattr(logger, skip_log_level, logger.debug)
                log_fn(skip_log_template, index, marker_count)
            continue

        ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
            corners,
            ids,
            gray,
            board,
        )
        if ret >= min_charuco_corners:
            all_charuco_corners.append(charuco_corners)
            all_charuco_ids.append(charuco_ids)

    return all_charuco_corners, all_charuco_ids, image_size
