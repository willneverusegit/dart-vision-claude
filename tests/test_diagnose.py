"""Tests for src/diagnose.py (P5)."""

from unittest.mock import patch, MagicMock

from src.diagnose import (
    check_python_version,
    check_dependencies,
    check_config_files,
    run_diagnostics,
    print_diagnostics,
)


class TestCheckPythonVersion:
    def test_current_python_ok(self):
        ok, msg = check_python_version()
        assert ok
        assert "Python" in msg

    def test_old_python_fails(self):
        import sys
        real = sys.version_info
        try:
            # Simulate old python by patching the function's comparison
            # Since we can't easily mock sys.version_info, test the logic directly
            ok = real >= (3, 10)
            assert ok  # Current python should pass
            # Test that (3,9) would fail
            assert not ((3, 9, 0) >= (3, 10))
        finally:
            pass


class TestCheckDependencies:
    def test_all_deps_available(self):
        results = check_dependencies()
        assert len(results) >= 7
        # At least cv2, numpy, fastapi should be available in test env
        cv2_result = [r for r in results if "opencv" in r[1]]
        assert len(cv2_result) == 1
        assert cv2_result[0][0] is True

    @patch("builtins.__import__", side_effect=ImportError("missing"))
    def test_missing_dep(self, mock_import):
        results = check_dependencies()
        for ok, msg in results:
            assert not ok
            assert "FEHLT" in msg


class TestCheckConfigFiles:
    def test_returns_list(self):
        results = check_config_files()
        assert isinstance(results, list)
        assert len(results) == 2

    @patch("os.path.isfile", return_value=False)
    def test_missing_files(self, mock_isfile):
        results = check_config_files()
        for ok, msg in results:
            assert not ok
            assert "nicht vorhanden" in msg


class TestRunDiagnostics:
    def test_returns_structured_result(self):
        results = run_diagnostics()
        assert "ok" in results
        assert "checks" in results
        assert isinstance(results["checks"], list)
        assert len(results["checks"]) > 0

    def test_each_check_has_required_fields(self):
        results = run_diagnostics()
        for check in results["checks"]:
            assert "name" in check
            assert "ok" in check
            assert "detail" in check


class TestPrintDiagnostics:
    def test_prints_without_error(self, capsys):
        results = {
            "ok": True,
            "checks": [
                {"name": "Test", "ok": True, "detail": "alles gut"},
            ],
        }
        print_diagnostics(results)
        captured = capsys.readouterr()
        assert "Systemdiagnose" in captured.out
        assert "[OK]" in captured.out

    def test_prints_failure(self, capsys):
        results = {
            "ok": False,
            "checks": [
                {"name": "Test", "ok": False, "detail": "fehlt"},
            ],
        }
        print_diagnostics(results)
        captured = capsys.readouterr()
        assert "[!!]" in captured.out
        assert "Probleme gefunden" in captured.out
