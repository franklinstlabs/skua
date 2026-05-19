"""Tests for skua.config.

skua.configure() is deprecated (as of 0.11). These tests confirm it still
works for back-compat, emits a DeprecationWarning, and that the URL/token
getters resolve from env vars / ~/.skua/token when configure() isn't used.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import skua.config as config_module
from skua.config import (
    configure,
    get_api_url,
    get_session_file,
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


class TestConfigureEmitsDeprecationWarning:
    """configure() is deprecated in favor of env vars + init(visibility=)."""

    def test_configure_emits_warning(self, reset_config):
        with pytest.warns(DeprecationWarning, match="deprecated"):
            configure(api_url="http://example.com")

    def test_configure_still_sets_api_url(self, reset_config):
        with pytest.warns(DeprecationWarning):
            configure(api_url="http://example.com")
        assert get_api_url() == "http://example.com"

    def test_configure_still_sets_web_url(self, reset_config):
        with pytest.warns(DeprecationWarning):
            configure(web_url="http://example.com")
        assert get_web_url() == "http://example.com"

    def test_configure_still_sets_token(self, reset_config):
        with pytest.warns(DeprecationWarning):
            configure(token="sk_test")
        assert get_token() == "sk_test"

    def test_configure_none_is_noop_for_unset_fields(self, reset_config):
        with pytest.warns(DeprecationWarning):
            configure(api_url="http://first.com")
        with pytest.warns(DeprecationWarning):
            configure(api_url=None)
        assert get_api_url() == "http://first.com"


class TestDefaultURLs:
    def test_default_api_url(self, reset_config, clean_env):
        assert get_api_url() == "https://api.skua.dev"

    def test_default_web_url(self, reset_config, clean_env):
        assert get_web_url() == "https://skua.dev"

    def test_default_session_file(self, reset_config):
        # Canonical path is ~/.skua/client now; the old `~/.skua/session`
        # only lives on as a migration source inside get_client_token().
        assert get_session_file() == Path.home() / ".skua" / "client"


class TestGetToken:
    def test_returns_none_by_default(self, reset_config, tmp_path):
        config_module._config["token"] = None
        with patch("skua.config.Path.home", return_value=tmp_path):
            assert get_token() is None

    def test_returns_env_token(self, reset_config, tmp_path):
        config_module._config["token"] = None
        with patch.dict(os.environ, {"SKUA_TOKEN": "env_token"}), \
             patch("skua.config.Path.home", return_value=tmp_path):
            assert get_token() == "env_token"

    def test_token_file_no_longer_read_directly(self, reset_config, tmp_path):
        # `get_token()` is now strictly the explicit-override channel
        # (env var or skua.configure(token=...)). On-disk lookup moved
        # to client.get_client_token() so the resolution path lives in
        # one place. Legacy ~/.skua/token is still picked up there as a
        # migration source — see test_client.py for that coverage.
        config_module._config["token"] = None
        skua_dir = tmp_path / ".skua"
        skua_dir.mkdir()
        (skua_dir / "token").write_text("file_token\n")
        with patch.dict(os.environ, {}, clear=False), \
             patch("skua.config.Path.home", return_value=tmp_path):
            os.environ.pop("SKUA_TOKEN", None)
            assert get_token() is None

    def test_runtime_config_beats_env(self, reset_config):
        with pytest.warns(DeprecationWarning):
            configure(token="runtime")
        with patch.dict(os.environ, {"SKUA_TOKEN": "env"}):
            assert get_token() == "runtime"
