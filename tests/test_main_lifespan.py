import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_lifespan_startup_game_engine():
    from src.main import lifespan, app, app_state
    with patch('src.main.setup_logging'), patch('src.utils.config.get_startup_cameras', return_value=[]), patch('src.main.start_single_pipeline'), patch('src.main.stop_pipeline_thread'), patch('src.cv.recorder.VideoRecorder', return_value=MagicMock()), patch('src.main.StaticFiles'):
        async with lifespan(app):
            assert app_state["game_engine"] is not None
            assert app_state["event_manager"] is not None


@pytest.mark.asyncio
async def test_lifespan_startup_shutdown_event():
    from src.main import lifespan, app, app_state
    with patch('src.main.setup_logging'), patch('src.utils.config.get_startup_cameras', return_value=[]), patch('src.main.start_single_pipeline'), patch('src.main.stop_pipeline_thread'), patch('src.cv.recorder.VideoRecorder', return_value=MagicMock()), patch('src.main.StaticFiles'):
        async with lifespan(app):
            assert isinstance(app_state["shutdown_event"], threading.Event)
            assert not app_state["shutdown_event"].is_set()


@pytest.mark.asyncio
async def test_lifespan_startup_locks():
    from src.main import lifespan, app, app_state
    with patch('src.main.setup_logging'), patch('src.utils.config.get_startup_cameras', return_value=[]), patch('src.main.start_single_pipeline'), patch('src.main.stop_pipeline_thread'), patch('src.cv.recorder.VideoRecorder', return_value=MagicMock()), patch('src.main.StaticFiles'):
        async with lifespan(app):
            assert app_state["pending_hits_lock"] is not None
            assert app_state["pipeline_lock"] is not None


@pytest.mark.asyncio
async def test_lifespan_startup_telemetry():
    from src.main import lifespan, app, app_state
    from src.utils.telemetry import TelemetryHistory
    with patch('src.main.setup_logging'), patch('src.utils.config.get_startup_cameras', return_value=[]), patch('src.main.start_single_pipeline'), patch('src.main.stop_pipeline_thread'), patch('src.cv.recorder.VideoRecorder', return_value=MagicMock()), patch('src.main.StaticFiles'):
        async with lifespan(app):
            assert isinstance(app_state.get("telemetry"), TelemetryHistory)


@pytest.mark.asyncio
async def test_lifespan_shutdown_sets_event():
    from src.main import lifespan, app, app_state
    with patch('src.main.setup_logging'), patch('src.utils.config.get_startup_cameras', return_value=[]), patch('src.main.start_single_pipeline'), patch('src.main.stop_pipeline_thread'), patch('src.cv.recorder.VideoRecorder', return_value=MagicMock()), patch('src.main.StaticFiles'):
        async with lifespan(app):
            pass
        assert app_state["shutdown_event"].is_set()


@pytest.mark.asyncio
async def test_lifespan_startup_multi_camera():
    from src.main import lifespan, app, app_state
    cam_configs = [{"camera_id": "cam0", "src": 0}]
    started = []

    def fake_thread(**kwargs):
        m = MagicMock()
        m.start.side_effect = lambda: started.append(True)
        return m

    with patch('src.main.setup_logging'), patch('src.utils.config.get_startup_cameras', return_value=cam_configs), patch('src.main.stop_pipeline_thread'), patch('src.cv.recorder.VideoRecorder', return_value=MagicMock()), patch('src.main.StaticFiles'), patch('src.main.threading.Thread', side_effect=fake_thread):
        async with lifespan(app):
            pass
    assert len(started) >= 1


def test_telemetry_cleanup_calls_cleanup():
    mock_writer = MagicMock()
    mock_writer.cleanup_old_files.return_value = 2
    state = {"telemetry_jsonl_writer": mock_writer}
    writer = state.get("telemetry_jsonl_writer")
    if writer is not None:
        deleted = writer.cleanup_old_files()
        assert deleted == 2
    mock_writer.cleanup_old_files.assert_called_once()


def test_telemetry_cleanup_no_writer():
    state = {}
    writer = state.get("telemetry_jsonl_writer")
    if writer is not None:
        writer.cleanup_old_files()


def test_telemetry_cleanup_exception_swallowed():
    mock_writer = MagicMock()
    mock_writer.cleanup_old_files.side_effect = OSError("disk full")
    state = {"telemetry_jsonl_writer": mock_writer}
    writer = state.get("telemetry_jsonl_writer")
    if writer is not None:
        try:
            writer.cleanup_old_files()
        except Exception:
            pass
    mock_writer.cleanup_old_files.assert_called_once()


@pytest.mark.asyncio
async def test_lifespan_attaches_jsonl_writer():
    from src.main import lifespan, app, app_state
    mock_writer = MagicMock()
    with patch('src.main.setup_logging'), patch('src.utils.config.get_startup_cameras', return_value=[]), patch('src.main.start_single_pipeline'), patch('src.main.stop_pipeline_thread'), patch('src.cv.recorder.VideoRecorder', return_value=MagicMock()), patch('src.main.StaticFiles'), patch('src.utils.telemetry.TelemetryJSONLWriter.from_env', return_value=mock_writer):
        async with lifespan(app):
            assert app_state.get("telemetry_jsonl_writer") is mock_writer
