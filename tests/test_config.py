"""Tests for config loader/writer."""

import os
from src.utils.config import load_config, save_config


class TestConfigLoader:
    def test_load_nonexistent_returns_empty(self, tmp_path):
        path = str(tmp_path / "nonexistent.yaml")
        result = load_config(path)
        assert result == {}

    def test_load_empty_file_returns_empty(self, tmp_path):
        path = str(tmp_path / "empty.yaml")
        with open(path, "w") as f:
            f.write("")
        result = load_config(path)
        assert result == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "config.yaml")
        data = {"board_center": [200, 200], "radius": 150, "version": 1}
        save_config(data, path)
        loaded = load_config(path)
        assert loaded == data

    def test_atomic_write_creates_dirs(self, tmp_path):
        path = str(tmp_path / "subdir" / "config.yaml")
        save_config({"key": "value"}, path)
        assert os.path.exists(path)
        loaded = load_config(path)
        assert loaded["key"] == "value"

    def test_overwrite_existing(self, tmp_path):
        path = str(tmp_path / "config.yaml")
        save_config({"v": 1}, path)
        save_config({"v": 2}, path)
        loaded = load_config(path)
        assert loaded["v"] == 2
