"""Web server modules for Dart-Vision."""

from src.web.events import EventManager
from src.web.routes import setup_routes
from src.web.stream import encode_frame_jpeg, make_mjpeg_frame

__all__ = [
    "EventManager",
    "setup_routes",
    "encode_frame_jpeg",
    "make_mjpeg_frame",
]
