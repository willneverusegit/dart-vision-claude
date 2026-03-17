"""Helpers for consistent shared app_state mutation."""

from __future__ import annotations

import threading


def initialize_runtime_state(
    state: dict,
    *,
    game_engine,
    event_manager,
    shutdown_event: threading.Event,
    pending_hits_lock: threading.Lock,
    pipeline_lock: threading.Lock,
) -> None:
    """Initialize the shared runtime state for a fresh app lifespan."""
    state["game_engine"] = game_engine
    state["event_manager"] = event_manager
    state["shutdown_event"] = shutdown_event
    state["pending_hits_lock"] = pending_hits_lock
    state["pending_hits"] = {}
    state["pending_hits_expired_total"] = 0
    state["pending_hits_rejected_by_timeout_total"] = 0
    state["pending_hits_dropped_overflow_total"] = 0
    state["pipeline_lock"] = pipeline_lock
    state["pipeline"] = None
    state["pipeline_running"] = False
    state["multi_pipeline"] = None
    state["multi_pipeline_running"] = False
    state["active_camera_ids"] = []
    state["multi_latest_frames"] = {}
    state["latest_frame"] = None
    state["pipeline_stop_event"] = None
    state["pipeline_thread"] = None
    state["multi_pipeline_stop_event"] = None
    state["multi_pipeline_thread"] = None


def set_single_pipeline_state(state: dict, pipeline, *, running: bool) -> None:
    state["pipeline"] = pipeline
    state["pipeline_running"] = running


def clear_single_pipeline_state(state: dict) -> None:
    state["pipeline_running"] = False
    state["pipeline"] = None


def set_multi_pipeline_state(state: dict, pipeline, camera_ids: list[str]) -> None:
    state["multi_pipeline"] = pipeline
    state["multi_pipeline_running"] = True
    state["active_camera_ids"] = list(camera_ids)


def clear_multi_pipeline_state(state: dict) -> None:
    state["multi_pipeline_running"] = False
    state["active_camera_ids"] = []
    state["multi_pipeline"] = None
    state["multi_latest_frames"] = {}


def set_pipeline_thread_handles(
    state: dict,
    kind: str,
    *,
    stop_event: threading.Event | None,
    thread: threading.Thread | None,
) -> None:
    if kind == "single":
        state["pipeline_stop_event"] = stop_event
        state["pipeline_thread"] = thread
    else:
        state["multi_pipeline_stop_event"] = stop_event
        state["multi_pipeline_thread"] = thread


def clear_pipeline_thread_handles(state: dict, kind: str) -> None:
    set_pipeline_thread_handles(state, kind, stop_event=None, thread=None)


def set_multi_latest_frame(state: dict, camera_id: str, frame) -> None:
    state["multi_latest_frames"][camera_id] = frame
    active_ids = state.get("active_camera_ids", [])
    if state.get("latest_frame") is None or (active_ids and camera_id == active_ids[0]):
        state["latest_frame"] = frame


def clear_multi_latest_frames(state: dict) -> None:
    state["multi_latest_frames"] = {}
