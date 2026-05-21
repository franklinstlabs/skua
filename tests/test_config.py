"""Tests for skua.config.

All settings come from environment variables — `skua.configure()` was
removed in 0.13. These tests confirm the env-var resolution path works.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import skua.config as config_module
from skua.config import (
    get_api_url,
    get_client_token_file,
    get_token,
    get_web_url,
)


@pytest.fixture
def reset_config():
    """Reset configuration to default values after each test."""
    original_config = config_module._config.copy()
    yield
    config_module._config.clear()
    config_module._config.update(original_config)


@pytest.fixture
def clean_env():
    """Remove Skua env vars and reset _config so defaults apply."""
    saved_env = {}
    for var in ("SKUA_API_URL", "SKUA_WEB_URL"):
        if var in os.environ:
            saved_env[var] = os.environ.pop(var)
    config_module._config["api_url"] = "https://api.skua.dev"
    config_module._config["web_url"] = "https://skua.dev"
    yield
    for var, value in saved_env.items():
        os.environ[var] = value


class TestDefaultURLs:
    def test_default_api_url(self, reset_config, clean_env):
        assert get_api_url() == "https://api.skua.dev"

    def test_default_web_url(self, reset_config, clean_env):
        assert get_web_url() == "https://skua.dev"

    def test_default_client_token_file(self, reset_config):
        # Canonical path is ~/.skua/client. There is no longer a
        # "session file" concept on disk.
        assert get_client_token_file() == Path.home() / ".skua" / "client"


class TestGetToken:
    def test_returns_none_by_default(self, reset_config, tmp_path):
        config_module._config["token"] = None
        with patch("skua.config.Path.home", return_value=tmp_path):
            # Ensure no env var leaks in from the surrounding shell.
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("SKUA_TOKEN", None)
                assert get_token() is None

    def test_returns_env_token(self, reset_config, tmp_path):
        config_module._config["token"] = None
        with patch.dict(os.environ, {"SKUA_TOKEN": "env_token"}), \
             patch("skua.config.Path.home", return_value=tmp_path):
            assert get_token() == "env_token"

    def test_token_file_no_longer_read_directly(self, reset_config, tmp_path):
        # `get_token()` is strictly the explicit-override channel (env var
        # or in-memory _config). On-disk lookup lives in
        # client.get_client_token() — see test_client.py for that coverage.
        config_module._config["token"] = None
        skua_dir = tmp_path / ".skua"
        skua_dir.mkdir()
        (skua_dir / "token").write_text("file_token\n")
        with patch.dict(os.environ, {}, clear=False), \
             patch("skua.config.Path.home", return_value=tmp_path):
            os.environ.pop("SKUA_TOKEN", None)
            assert get_token() is None
