import os

import pytest
import yaml

from config import (
    AppConfig,
    CHUNK_SIZE,
    CHUNK_THRESHOLD,
    DB_PATH,
    SERVER_BASE_URL,
    SYNC_INTERVAL_SECONDS,
    UPLOAD_MAX_RETRIES,
    WATCH_DIR,
    load_config,
)


class TestDefaultConfigValues:
    def test_config_has_expected_module_attributes(self):
        assert DB_PATH is not None
        assert DB_PATH.endswith("shadow.db")
        assert WATCH_DIR is not None
        assert CHUNK_SIZE == 4 * 1024 * 1024
        assert CHUNK_THRESHOLD == CHUNK_SIZE
        assert SYNC_INTERVAL_SECONDS == 10
        assert UPLOAD_MAX_RETRIES == 5
        assert SERVER_BASE_URL == "http://localhost:8000"


class TestLoadConfig:
    def test_load_config_from_temp_yaml(self, tmp_path):
        yaml_path = tmp_path / "test_config.yaml"
        config_data = {
            "server": {"url": "https://custom.example.com", "api_key": "test-key-123"},
            "client": {
                "watch_folder": str(tmp_path / "custom_watch"),
                "chunk_size_mb": 8,
                "sync_interval_sec": 30,
                "max_retries": 10,
                "compression": "zlib",
            },
            "logging": {"level": "DEBUG", "file": str(tmp_path / "test.log")},
            "encryption": {"algorithm": "AES-256-GCM", "pbkdf2_iterations": 200000},
        }
        with open(yaml_path, "w") as f:
            yaml.dump(config_data, f)

        cfg = load_config(str(yaml_path))
        assert isinstance(cfg, AppConfig)
        assert cfg.server.url == "https://custom.example.com"
        assert cfg.server.api_key == "test-key-123"
        assert cfg.client.watch_folder == str(tmp_path / "custom_watch")
        assert cfg.client.chunk_size_mb == 8
        assert cfg.client.sync_interval_sec == 30
        assert cfg.client.max_retries == 10
        assert cfg.client.compression == "zlib"
        assert cfg.logging.level == "DEBUG"
        assert cfg.logging.file == str(tmp_path / "test.log")
        assert cfg.encryption.algorithm == "AES-256-GCM"
        assert cfg.encryption.pbkdf2_iterations == 200000

    def test_load_config_nonexistent_returns_default(self):
        cfg = load_config("/nonexistent/path/config.yaml")
        assert isinstance(cfg, AppConfig)
        assert cfg.server.url == "http://localhost:8000"
        assert cfg.client.chunk_size_mb == 4

    def test_load_config_empty_yaml_returns_default(self, tmp_path):
        empty = tmp_path / "empty.yaml"
        empty.write_text("")
        cfg = load_config(str(empty))
        assert isinstance(cfg, AppConfig)
