"""MJPEG streaming helpers for video feed."""

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


def encode_frame_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    """Encode a frame as JPEG bytes.

    Args:
        frame: BGR image (numpy array)
        quality: JPEG quality (0-100)

    Returns:
        JPEG-encoded bytes
    """
    params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    ok, buffer = cv2.imencode(".jpg", frame, params)
    if not ok:
        logger.warning("JPEG encoding failed")
        return b""
    return buffer.tobytes()


CRLF = b"\r\n"


def make_mjpeg_frame(jpeg_bytes: bytes) -> bytes:
    """Wrap JPEG bytes in MJPEG multipart frame.

    Args:
        jpeg_bytes: Raw JPEG data

    Returns:
        Multipart frame bytes with boundary
    """
    parts = [
        b"--frame" + CRLF,
        b"Content-Type: image/jpeg" + CRLF,
        b"Content-Length: " + str(len(jpeg_bytes)).encode() + CRLF,
        CRLF,
        jpeg_bytes + CRLF,
    ]
    return b"".join(parts)
