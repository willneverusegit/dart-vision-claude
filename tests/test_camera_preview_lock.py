"""Tests for P65: camera preview endpoint locking, caching, and timeout."""

import time as _time_mod
from unittest.mock import patch, MagicMock

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Build a single app for all tests in this module.
import src.web.routes as _routes_mod
from src.web.routes import setup_routes

_CV2_VC = "src.web.routes.cv2.VideoCapture"
_TIME = "src.web.routes._time"

_app = FastAPI()
_state: dict = {}
_router = setup_routes(_state)
_app.include_router(_router)


def _fake_cap(opened=True, read_ok=True):
    fake_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    cap = MagicMock()
    cap.isOpened.return_value = opened
    cap.read.return_value = (read_ok, fake_frame if read_ok else None)
    return cap


def _clear_preview_cache():
    """Clear the closure-scoped preview cache between tests.

    The cache/locks dicts live inside the setup_routes closure.  We find them
    via the endpoint function's __code__.co_freevars / cell contents.
    """
    # Walk the routes to find the endpoint and its closure cells
    for route in _router.routes:
        if hasattr(route, "path") and route.path == "/api/camera/preview/{source}":
            fn = route.endpoint
            if hasattr(fn, "__wrapped__"):
                fn = fn.__wrapped__
            for cell in (fn.__closure__ or []):
                obj = cell.cell_contents
                if isinstance(obj, dict):
                    obj.clear()
            return
    # Fallback: brute-force doesn't harm
    pass


@pytest.fixture(autouse=True)
def _clean_cache():
    """Clear preview cache before each test."""
    _clear_preview_cache()
    yield
    _clear_preview_cache()


@pytest.fixture()
def client():
    return TestClient(_app)


# --------------- TTL cache ---------------

class TestPreviewCache:
    def test_second_request_hits_cache(self, client):
        """Two rapid requests should only open the camera once."""
        with patch(_CV2_VC, return_value=_fake_cap()) as vc:
            r1 = client.get("/api/camera/preview/0")
            assert r1.status_code == 200
            r2 = client.get("/api/camera/preview/0")
            assert r2.status_code == 200
            assert vc.call_count == 1

    def test_different_sources_not_cached(self, client):
        """Different camera sources get independent cache entries."""
        with patch(_CV2_VC, return_value=_fake_cap()) as vc:
            client.get("/api/camera/preview/0")
            client.get("/api/camera/preview/1")
            assert vc.call_count == 2

    def test_cache_expires_after_ttl(self, client):
        """After TTL expires, camera is opened again."""
        real_mono = _time_mod.monotonic
        call_count = [0]

        with patch(_CV2_VC, return_value=_fake_cap()) as vc:
            # First request: real time
            r1 = client.get("/api/camera/preview/0")
            assert r1.status_code == 200
            assert vc.call_count == 1

        # Expire the cache by directly modifying the tuple timestamp
        for route in _router.routes:
            if hasattr(route, "path") and route.path == "/api/camera/preview/{source}":
                fn = route.endpoint
                for cell in (fn.__closure__ or []):
                    obj = cell.cell_contents
                    if isinstance(obj, dict) and 0 in obj and isinstance(obj.get(0), tuple):
                        # Set timestamp to 0 (long expired)
                        obj[0] = (0.0, obj[0][1])

        with patch(_CV2_VC, return_value=_fake_cap()) as vc:
            r2 = client.get("/api/camera/preview/0")
            assert r2.status_code == 200
            assert vc.call_count == 1  # fresh call after cache expiry


# --------------- Locking ---------------

class TestPreviewLocking:
    def test_lock_created_per_source(self, client):
        """Each source gets its own asyncio.Lock — both succeed."""
        with patch(_CV2_VC, return_value=_fake_cap()):
            r0 = client.get("/api/camera/preview/0")
            r1 = client.get("/api/camera/preview/1")
            assert r0.status_code == 200
            assert r1.status_code == 200


# --------------- Error cases ---------------

class TestPreviewErrors:
    def test_camera_not_available_returns_404(self, client):
        with patch(_CV2_VC, return_value=_fake_cap(opened=False)):
            r = client.get("/api/camera/preview/0")
            assert r.status_code == 404
            assert r.json()["error"] == "Camera not available"

    def test_camera_read_fails_returns_404(self, client):
        with patch(_CV2_VC, return_value=_fake_cap(read_ok=False)):
            r = client.get("/api/camera/preview/0")
            assert r.status_code == 404


# --------------- Response format ---------------

class TestPreviewResponse:
    def test_returns_jpeg(self, client):
        with patch(_CV2_VC, return_value=_fake_cap()):
            r = client.get("/api/camera/preview/0")
            assert r.status_code == 200
            assert r.headers["content-type"] == "image/jpeg"
            assert r.content[:2] == b'\xff\xd8'

    def test_cached_response_also_jpeg(self, client):
        with patch(_CV2_VC, return_value=_fake_cap()):
            r1 = client.get("/api/camera/preview/0")
            r2 = client.get("/api/camera/preview/0")  # cache hit
            assert r2.status_code == 200
            assert r2.headers["content-type"] == "image/jpeg"
            assert r1.content == r2.content
