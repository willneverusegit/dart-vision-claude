"""Combined remapping for lens undistortion + board homography in one pass."""

from __future__ import annotations

import logging

import cv2
import numpy as np

from src.cv.geometry import CameraIntrinsics

logger = logging.getLogger(__name__)


class CombinedRemapper:
    """Prepare and apply a single-pass remap from raw frame to ROI board space."""

    def __init__(self, roi_size: tuple[int, int] = (400, 400)) -> None:
        self.roi_size = roi_size
        self._homography: np.ndarray | None = None
        self._intrinsics: CameraIntrinsics | None = None
        self._map_x: np.ndarray | None = None
        self._map_y: np.ndarray | None = None

    @property
    def has_combined_map(self) -> bool:
        """Whether single-pass remap tables are available."""
        return self._map_x is not None and self._map_y is not None

    @property
    def homography(self) -> np.ndarray | None:
        return self._homography

    def configure(self, homography: np.ndarray | None, intrinsics: CameraIntrinsics | None) -> None:
        """(Re)configure remapping from calibration artifacts."""
        self._homography = None if homography is None else np.array(homography, dtype=np.float64).reshape(3, 3)
        self._intrinsics = intrinsics
        self._map_x = None
        self._map_y = None

        if self._homography is None:
            return
        if intrinsics is None or not intrinsics.valid:
            logger.info("Remapper configured with board homography only (no lens intrinsics)")
            return

        try:
            self._map_x, self._map_y = self._build_combined_maps(self._homography, intrinsics)
            logger.info("Combined remap map prepared (%dx%d)", self.roi_size[0], self.roi_size[1])
        except Exception as exc:
            self._map_x = None
            self._map_y = None
            logger.warning("Combined map build failed, using fallback path: %s", exc)

    def roi_to_raw(self, x: float, y: float) -> tuple[float, float]:
        """Transform a point from ROI board space back to raw camera pixel coords.

        Uses inverse homography + re-distortion (matching the forward remap path).
        Returns the original point unchanged if no homography is configured.
        """
        if self._homography is None:
            return (x, y)

        # Step 1: ROI -> undistorted full-frame via inverse homography
        h_inv = np.linalg.inv(self._homography)
        roi_pt = np.array([[[x, y]]], dtype=np.float64)
        undist_pt = cv2.perspectiveTransform(roi_pt, h_inv).reshape(2)

        # Step 2: undistorted -> raw (re-distort) if we have intrinsics
        if self._intrinsics is not None and self._intrinsics.valid:
            k = self._intrinsics.camera_matrix
            fx, fy = float(k[0, 0]), float(k[1, 1])
            cx, cy = float(k[0, 2]), float(k[1, 2])
            if fx != 0 and fy != 0:
                normalized = np.array([[(undist_pt[0] - cx) / fx,
                                        (undist_pt[1] - cy) / fy, 1.0]])
                distorted, _ = cv2.projectPoints(
                    normalized,
                    np.zeros((3, 1), dtype=np.float64),
                    np.zeros((3, 1), dtype=np.float64),
                    self._intrinsics.camera_matrix,
                    self._intrinsics.dist_coeffs,
                )
                return (float(distorted[0, 0, 0]), float(distorted[0, 0, 1]))

        return (float(undist_pt[0]), float(undist_pt[1]))

    def remap(self, frame: np.ndarray) -> np.ndarray:
        """Transform raw camera frame to ROI board space."""
        if self.has_combined_map:
            return cv2.remap(
                frame,
                self._map_x,
                self._map_y,
                interpolation=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
            )

        if self._homography is None:
            return frame

        working = frame
        if self._intrinsics is not None and self._intrinsics.valid:
            working = cv2.undistort(
                frame,
                self._intrinsics.camera_matrix,
                self._intrinsics.dist_coeffs,
            )
        return cv2.warpPerspective(working, self._homography, self.roi_size)

    def _build_combined_maps(
        self, homography: np.ndarray, intrinsics: CameraIntrinsics
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build lookup maps from ROI pixel grid back to distorted raw image pixels."""
        width, height = self.roi_size
        xs, ys = np.meshgrid(
            np.arange(width, dtype=np.float64),
            np.arange(height, dtype=np.float64),
        )
        roi_pts = np.stack((xs.ravel(), ys.ravel()), axis=-1).reshape(-1, 1, 2)

        h_inv = np.linalg.inv(homography)
        undistorted_pts = cv2.perspectiveTransform(roi_pts, h_inv).reshape(-1, 2)

        k = intrinsics.camera_matrix
        fx, fy = float(k[0, 0]), float(k[1, 1])
        cx, cy = float(k[0, 2]), float(k[1, 2])
        if fx == 0 or fy == 0:
            raise ValueError("Invalid focal lengths in camera matrix")

        normalized = np.empty((undistorted_pts.shape[0], 3), dtype=np.float64)
        normalized[:, 0] = (undistorted_pts[:, 0] - cx) / fx
        normalized[:, 1] = (undistorted_pts[:, 1] - cy) / fy
        normalized[:, 2] = 1.0

        distorted_pts, _ = cv2.projectPoints(
            normalized,
            np.zeros((3, 1), dtype=np.float64),
            np.zeros((3, 1), dtype=np.float64),
            intrinsics.camera_matrix,
            intrinsics.dist_coeffs,
        )
        distorted_pts = distorted_pts.reshape(height, width, 2)
        map_x = distorted_pts[:, :, 0].astype(np.float32)
        map_y = distorted_pts[:, :, 1].astype(np.float32)
        return map_x, map_y
