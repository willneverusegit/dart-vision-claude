"""Extracts and warps the dartboard region using homography."""

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ROIProcessor:
    """Extracts and warps the dartboard region using homography."""

    def __init__(self, roi_size: tuple[int, int] = (400, 400)) -> None:
        self.roi_size = roi_size
        self.homography: np.ndarray | None = None

    def set_homography(self, src_points: np.ndarray, dst_points: np.ndarray) -> None:
        """Set perspective transform from 4 source to 4 destination points."""
        src = np.float32(src_points)
        dst = np.float32(dst_points)
        self.homography = cv2.getPerspectiveTransform(src, dst)
        logger.info("Homography set from %d point pairs", len(src_points))

    def set_homography_matrix(self, matrix: np.ndarray) -> None:
        """Directly set the 3x3 homography matrix (from config)."""
        self.homography = np.array(matrix, dtype=np.float64).reshape(3, 3)

    def warp_roi(self, frame: np.ndarray) -> np.ndarray:
        """Apply perspective transform. Falls back to identity if no homography set."""
        if self.homography is None:
            logger.debug("No homography set, returning original frame")
            return frame
        try:
            warped = cv2.warpPerspective(frame, self.homography, self.roi_size)
            return warped
        except cv2.error as e:
            logger.error("Warp failed: %s — falling back to identity", e)
            return frame

    def polar_unwrap(self, roi_frame: np.ndarray, center: tuple[int, int] | None = None,
                     radius: int = 200) -> np.ndarray:
        """Convert circular dartboard to linear polar coordinates."""
        if center is None:
            h, w = roi_frame.shape[:2]
            center = (w // 2, h // 2)
        polar = cv2.warpPolar(
            roi_frame,
            (2 * radius, 360),
            center,
            radius,
            cv2.WARP_POLAR_LINEAR
        )
        return polar
