"""Tests for MJPEG stream helpers."""

import numpy as np
from src.web.stream import encode_frame_jpeg, make_mjpeg_frame


class TestStreamHelpers:
    def test_encode_frame_returns_bytes(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = encode_frame_jpeg(frame)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_encode_frame_starts_with_jpeg_magic(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = encode_frame_jpeg(frame)
        # JPEG magic bytes
        assert result[:2] == b"\xff\xd8"

    def test_encode_frame_quality_affects_size(self):
        frame = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        low_q = encode_frame_jpeg(frame, quality=10)
        high_q = encode_frame_jpeg(frame, quality=95)
        assert len(high_q) > len(low_q)

    def test_make_mjpeg_frame_has_boundary(self):
        jpeg = b"\xff\xd8fake_jpeg\xff\xd9"
        result = make_mjpeg_frame(jpeg)
        assert b"--frame" in result

    def test_make_mjpeg_frame_has_content_type(self):
        jpeg = b"\xff\xd8fake\xff\xd9"
        result = make_mjpeg_frame(jpeg)
        assert b"Content-Type: image/jpeg" in result

    def test_make_mjpeg_frame_has_content_length(self):
        jpeg = b"0123456789"
        result = make_mjpeg_frame(jpeg)
        assert b"Content-Length: 10" in result
