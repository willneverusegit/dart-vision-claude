"""Tests for logging setup (P4): idempotency, session ID, file rotation."""

import logging
import os
import tempfile

from src.utils.logger import setup_logging, SESSION_ID


class TestSetupLogging:
    def _cleanup_handlers(self):
        """Remove dart-vision handlers from root logger."""
        root = logging.getLogger()
        root.handlers = [h for h in root.handlers if not getattr(h, "_dartvision", False)]

    def test_session_id_is_string(self):
        assert isinstance(SESSION_ID, str)
        assert len(SESSION_ID) == 8

    def test_idempotent_no_duplicate_handlers(self):
        self._cleanup_handlers()
        root = logging.getLogger()
        before = len(root.handlers)

        setup_logging()
        after_first = len(root.handlers)
        assert after_first == before + 1

        setup_logging()
        after_second = len(root.handlers)
        assert after_second == after_first  # no new handler

        self._cleanup_handlers()

    def test_stdout_handler_created(self):
        self._cleanup_handlers()
        setup_logging()
        root = logging.getLogger()
        dv_handlers = [h for h in root.handlers if getattr(h, "_dartvision", False)]
        assert len(dv_handlers) >= 1
        assert any(isinstance(h, logging.StreamHandler) for h in dv_handlers)
        self._cleanup_handlers()

    def test_file_handler_rotation(self):
        self._cleanup_handlers()
        tmpdir = tempfile.mkdtemp()
        try:
            log_path = os.path.join(tmpdir, "test.log")
            setup_logging(log_file=log_path)

            root = logging.getLogger()
            dv_handlers = [h for h in root.handlers if getattr(h, "_dartvision", False)]
            assert len(dv_handlers) == 2

            test_logger = logging.getLogger("test_file_rotation")
            test_logger.info("Test log line")

            for h in dv_handlers:
                h.flush()

            assert os.path.exists(log_path)
            with open(log_path, encoding="utf-8") as f:
                content = f.read()
            assert "Test log line" in content
            assert SESSION_ID in content
        finally:
            self._cleanup_handlers()
            # Clean up temp files (close handles first on Windows)
            try:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass

    def test_session_id_in_log_format(self):
        self._cleanup_handlers()
        setup_logging()
        root = logging.getLogger()
        dv_handlers = [h for h in root.handlers if getattr(h, "_dartvision", False)]
        assert len(dv_handlers) >= 1
        # Check formatter includes session ID
        fmt = dv_handlers[0].formatter._fmt
        assert SESSION_ID in fmt
        self._cleanup_handlers()

    def test_json_format(self):
        self._cleanup_handlers()
        setup_logging(json_format=True)
        root = logging.getLogger()
        dv_handlers = [h for h in root.handlers if getattr(h, "_dartvision", False)]
        fmt = dv_handlers[0].formatter._fmt
        assert '"session"' in fmt
        assert SESSION_ID in fmt
        self._cleanup_handlers()

    def test_level_change_on_second_call(self):
        self._cleanup_handlers()
        setup_logging(level=logging.WARNING)
        root = logging.getLogger()
        assert root.level == logging.WARNING

        # Second call should update level without adding handler
        setup_logging(level=logging.DEBUG)
        assert root.level == logging.DEBUG
        dv_handlers = [h for h in root.handlers if getattr(h, "_dartvision", False)]
        assert len(dv_handlers) == 1

        self._cleanup_handlers()

    def test_log_dir_created_automatically(self):
        self._cleanup_handlers()
        tmpdir = tempfile.mkdtemp()
        try:
            log_path = os.path.join(tmpdir, "subdir", "nested", "app.log")
            setup_logging(log_file=log_path)
            assert os.path.isdir(os.path.join(tmpdir, "subdir", "nested"))
        finally:
            self._cleanup_handlers()
            try:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass
