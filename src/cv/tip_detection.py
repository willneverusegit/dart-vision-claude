"""Dart tip detection via contour narrowing analysis.

Approach: A dart contour is widest at the flights and narrowest at the tip.
We use the minAreaRect to find the dart's main axis, then scan along that
axis to find the narrowest end — that's where the tip is.

The algorithm works in 3 steps:
1. Get the dart's axis direction from minAreaRect
2. Project all contour points onto that axis
3. Split the contour into two halves and find which half is narrower
   → the narrowest endpoint is the tip

This is robust because:
- It doesn't assume any fixed dart orientation
- It works regardless of camera angle (left/right/top)
- It relies on the physical shape of a dart (flights > barrel > tip)
"""

from __future__ import annotations

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def find_dart_tip(
    contour: np.ndarray,
    gray_frame: np.ndarray | None = None,
) -> tuple[int, int] | None:
    """Find the tip of a dart from its diff contour.

    The tip is the point at the narrow end of the dart silhouette.
    Returns (x, y) pixel coordinates or None if detection fails.

    When *gray_frame* is provided, sub-pixel refinement via
    ``cv2.cornerSubPix`` is applied around the detected tip for
    higher accuracy at ring/sector boundaries.

    Parameters
    ----------
    contour:
        OpenCV contour (Nx1x2 array) of the dart's diff blob.
    gray_frame:
        Optional grayscale frame for sub-pixel refinement.
    """
    if contour is None or len(contour) < 10:
        logger.debug("tip_detection: contour too small (%s points)", len(contour) if contour is not None else 0)
        return None

    # Step 1: Get main axis from minAreaRect
    rect = cv2.minAreaRect(contour)
    rect_center, rect_size, rect_angle = rect

    # Use the longer side as the main axis
    w, h = rect_size
    if w < 5 and h < 5:
        logger.debug("tip_detection: rect too small (%.1f x %.1f)", w, h)
        return None

    # Angle of the longer axis in radians
    # OpenCV minAreaRect angle convention: angle of rotation of the rect
    # We want the direction along the longer dimension
    angle_rad = np.deg2rad(rect_angle)
    if w < h:
        # height is the long axis — rotate 90 degrees
        angle_rad += np.pi / 2

    axis_dir = np.array([np.cos(angle_rad), np.sin(angle_rad)])

    # Step 2: Project all contour points onto the main axis
    points = contour.reshape(-1, 2).astype(np.float64)
    center = np.array(rect_center)
    projections = (points - center) @ axis_dir  # scalar projections

    # Step 3: Split contour into two halves along the axis
    # and measure the "width" (spread perpendicular to axis) of each half
    perp_dir = np.array([-axis_dir[1], axis_dir[0]])
    perp_projections = (points - center) @ perp_dir

    median_proj = np.median(projections)

    # Positive half (one end of the dart) and negative half (other end)
    pos_mask = projections > median_proj
    neg_mask = projections <= median_proj

    if pos_mask.sum() < 3 or neg_mask.sum() < 3:
        logger.debug("tip_detection: not enough points in halves")
        return None

    # Width = spread of perpendicular projections in each half
    pos_width = np.ptp(perp_projections[pos_mask])  # peak-to-peak = max - min
    neg_width = np.ptp(perp_projections[neg_mask])

    # The narrower half contains the tip
    if pos_width < neg_width:
        # Tip is on the positive side — find the extreme point
        tip_candidates = points[pos_mask]
        tip_projections = projections[pos_mask]
    else:
        # Tip is on the negative side
        tip_candidates = points[neg_mask]
        tip_projections = projections[neg_mask]

    # The tip is the point furthest along the axis in the narrow half
    if pos_width < neg_width:
        tip_idx = np.argmax(tip_projections)
    else:
        tip_idx = np.argmin(tip_projections)

    tip = tip_candidates[tip_idx]
    tip_x, tip_y = int(round(tip[0])), int(round(tip[1]))

    # Sub-pixel refinement if grayscale frame is available
    if gray_frame is not None:
        tip_x, tip_y = _refine_subpixel(gray_frame, tip_x, tip_y)

    logger.debug(
        "tip_detection: tip=(%d,%d) pos_width=%.1f neg_width=%.1f ratio=%.2f",
        tip_x, tip_y, pos_width, neg_width,
        min(pos_width, neg_width) / max(pos_width, neg_width, 1),
    )

    return (tip_x, tip_y)


def _refine_subpixel(
    gray: np.ndarray, tip_x: int, tip_y: int, win: int = 10,
) -> tuple[int, int]:
    """Refine tip position to sub-pixel accuracy using cornerSubPix.

    Crops a small ROI around the tip, finds corners, and picks the one
    closest to the original tip estimate.  Falls back to the original
    position if refinement fails.
    """
    h, w = gray.shape[:2]
    x0 = max(tip_x - win, 0)
    y0 = max(tip_y - win, 0)
    x1 = min(tip_x + win, w)
    y1 = min(tip_y + win, h)
    # cornerSubPix needs roi >= winSize*2+5 = 11px in each dimension
    if x1 - x0 < 11 or y1 - y0 < 11:
        return tip_x, tip_y

    roi = gray[y0:y1, x0:x1]
    corners = cv2.goodFeaturesToTrack(roi, maxCorners=8, qualityLevel=0.01, minDistance=3)
    if corners is None or len(corners) == 0:
        return tip_x, tip_y

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.01)
    try:
        refined = cv2.cornerSubPix(roi, corners, winSize=(3, 3), zeroZone=(-1, -1), criteria=criteria)
    except cv2.error:
        return tip_x, tip_y

    # Pick corner closest to original tip (in ROI coords)
    local_tip = np.array([tip_x - x0, tip_y - y0], dtype=np.float32)
    dists = np.linalg.norm(refined.reshape(-1, 2) - local_tip, axis=1)
    best = refined[np.argmin(dists)].reshape(2)

    rx = int(round(best[0] + x0))
    ry = int(round(best[1] + y0))
    logger.debug("tip_detection: subpixel refined (%d,%d) → (%d,%d)", tip_x, tip_y, rx, ry)
    return rx, ry
