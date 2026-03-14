"""Tests for the Skua configuration module.

Covers:
- configure() - Setting configuration values
- get_api_url() - API URL retrieval and defaults
- get_web_url() - Web URL retrieval and defaults
- get_session_file() - Session file path retrieval
- init() / get_session_public() - Session-wide visibility defaults
- Environment variable handling
- Configuration isolation and reset
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the module to get access to the internal _config dict
import skua.config as config_module
from skua.config import (
    configure,
    get_api_url,
    get_session_file,
    get_session_public,
    get_token,
    get_web_url,
    init,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def reset_config():
    """Reset configuration to default values after each test.

    This ensures tests are isolated and don't affect each other.
    """
    original_config = config_module._config.copy()
    original_session_config = config_module._session_config.copy()

    yield

    config_module._config.clear()
    config_module._config.update(original_config)
    config_module._session_config.clear()
    config_module._session_config.update(original_session_config)


@pytest.fixture
def clean_env():
    """Remove Skua environment variables for testing defaults.

    Also resets the config module to pick up the cleared env vars.
    """
    # Save and remove env vars
    saved_env = {}
    env_vars = ["SKUA_API_URL", "SKUA_WEB_URL"]
    for var in env_vars:
        if var in os.environ:
            saved_env[var] = os.environ.pop(var)

    # Reset config to pick up the new env state
    config_module._config["api_url"] = "https://api.skua.dev"
    config_module._config["web_url"] = "https://skua.dev"

    yield

    # Restore env vars
    for var, value in saved_env.items():
        os.environ[var] = value


# =============================================================================
# Tests: configure() - Basic Configuration
# =============================================================================


class TestConfigureBasic:
    """Tests for basic configure() functionality."""

    def test_configure_api_url(self, reset_config):
        """Test setting API URL via configure()."""
        configure(api_url="http://localhost:8000")

        assert get_api_url() == "http://localhost:8000"

    def test_configure_web_url(self, reset_config):
        """Test setting web URL via configure()."""
        configure(web_url="http://localhost:5173")

        assert get_web_url() == "http://localhost:5173"

    def test_configure_session_file(self, reset_config, tmp_path):
        """Test setting session file path via configure()."""
        session_file = tmp_path / "custom_session"
        configure(session_file=session_file)

        assert get_session_file() == session_file

    def test_configure_multiple_values(self, reset_config, tmp_path):
        """Test setting multiple configuration values at once."""
        session_file = tmp_path / "session"
        configure(
            api_url="http://api.test.com",
            web_url="http://web.test.com",
            session_file=session_file,
        )

        assert get_api_url() == "http://api.test.com"
        assert get_web_url() == "http://web.test.com"
        assert get_session_file() == session_file

    def test_configure_preserves_unset_values(self, reset_config):
        """Test that configure() only changes specified values."""
        # Set initial value
        configure(api_url="http://initial.com")

        # Configure only web_url
        configure(web_url="http://newweb.com")

        # api_url should be unchanged
        assert get_api_url() == "http://initial.com"
        assert get_web_url() == "http://newweb.com"

    def test_configure_can_be_called_multiple_times(self, reset_config):
        """Test that configure() can be called multiple times to update values."""
        configure(api_url="http://first.com")
        assert get_api_url() == "http://first.com"

        configure(api_url="http://second.com")
        assert get_api_url() == "http://second.com"

        configure(api_url="http://third.com")
        assert get_api_url() == "http://third.com"


# =============================================================================
# Tests: configure() - None Handling
# =============================================================================


class TestConfigureNoneHandling:
    """Tests for None value handling in configure()."""

    def test_configure_none_does_not_change_api_url(self, reset_config):
        """Test that passing None explicitly does not change api_url."""
        configure(api_url="http://set.com")
        configure(api_url=None)

        # Should still be the set value, not None
        assert get_api_url() == "http://set.com"

    def test_configure_none_does_not_change_web_url(self, reset_config):
        """Test that passing None explicitly does not change web_url."""
        configure(web_url="http://set.com")
        configure(web_url=None)

        assert get_web_url() == "http://set.com"

    def test_configure_none_does_not_change_session_file(self, reset_config, tmp_path):
        """Test that passing None explicitly does not change session_file."""
        session_file = tmp_path / "session"
        configure(session_file=session_file)
        configure(session_file=None)

        assert get_session_file() == session_file



# =============================================================================
# Tests: get_api_url()
# =============================================================================


class TestGetApiUrl:
    """Tests for get_api_url() function."""

    def test_returns_default_url(self, reset_config, clean_env):
        """Test that default API URL is returned when not configured."""
        assert get_api_url() == "https://api.skua.dev"

    def test_returns_configured_url(self, reset_config):
        """Test that configured API URL is returned."""
        configure(api_url="http://custom.api.com")

        assert get_api_url() == "http://custom.api.com"

    def test_returns_string_type(self, reset_config):
        """Test that get_api_url() returns a string."""
        result = get_api_url()

        assert isinstance(result, str)

    def test_handles_urls_with_port(self, reset_config):
        """Test that URLs with port numbers are handled correctly."""
        configure(api_url="http://localhost:8000")

        assert get_api_url() == "http://localhost:8000"

    def test_handles_urls_with_path(self, reset_config):
        """Test that URLs with paths are handled correctly."""
        configure(api_url="http://api.example.com/v1")

        assert get_api_url() == "http://api.example.com/v1"

    def test_handles_https_urls(self, reset_config):
        """Test that HTTPS URLs are handled correctly."""
        configure(api_url="https://secure.api.com")

        assert get_api_url() == "https://secure.api.com"


# =============================================================================
# Tests: get_web_url()
# =============================================================================


class TestGetWebUrl:
    """Tests for get_web_url() function."""

    def test_returns_default_url(self, reset_config, clean_env):
        """Test that default web URL is returned when not configured."""
        assert get_web_url() == "https://skua.dev"

    def test_returns_configured_url(self, reset_config):
        """Test that configured web URL is returned."""
        configure(web_url="http://custom.web.com")

        assert get_web_url() == "http://custom.web.com"

    def test_returns_string_type(self, reset_config):
        """Test that get_web_url() returns a string."""
        result = get_web_url()

        assert isinstance(result, str)

    def test_handles_urls_with_port(self, reset_config):
        """Test that URLs with port numbers are handled correctly."""
        configure(web_url="http://localhost:5173")

        assert get_web_url() == "http://localhost:5173"


# =============================================================================
# Tests: get_session_file()
# =============================================================================


class TestGetSessionFile:
    """Tests for get_session_file() function."""

    def test_returns_default_path(self, reset_config):
        """Test that default session file path is returned."""
        result = get_session_file()

        assert result == Path.home() / ".skua" / "session"

    def test_returns_path_object(self, reset_config):
        """Test that get_session_file() returns a Path object."""
        result = get_session_file()

        assert isinstance(result, Path)

    def test_returns_configured_path(self, reset_config, tmp_path):
        """Test that configured session file path is returned."""
        custom_path = tmp_path / "custom" / "session"
        configure(session_file=custom_path)

        assert get_session_file() == custom_path

    def test_path_is_absolute(self, reset_config, tmp_path):
        """Test that returned path is absolute."""
        custom_path = tmp_path / "session"
        configure(session_file=custom_path)

        result = get_session_file()

        assert result.is_absolute()


# =============================================================================
# Tests: init() / get_session_public()
# =============================================================================


class TestInit:
    """Tests for init() and get_session_public()."""

    def test_returns_none_by_default(self, reset_config):
        """Test that None is returned when init() not called."""
        assert get_session_public() is None

    def test_init_public_true(self, reset_config):
        """Test setting public=True via init()."""
        init(public=True)

        assert get_session_public() is True

    def test_init_public_false(self, reset_config):
        """Test setting public=False via init()."""
        init(public=False)

        assert get_session_public() is False

    def test_init_none_does_not_change_setting(self, reset_config):
        """Test that init(public=None) does not change existing setting."""
        init(public=True)
        init(public=None)

        assert get_session_public() is True

    def test_init_can_be_overridden(self, reset_config):
        """Test that init() can be called multiple times to change setting."""
        init(public=True)
        assert get_session_public() is True

        init(public=False)
        assert get_session_public() is False


# =============================================================================
# Tests: Environment Variable Handling
# =============================================================================


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_api_url_from_environment(self, reset_config):
        """Test that SKUA_API_URL environment variable is respected."""
        with patch.dict(os.environ, {"SKUA_API_URL": "http://env.api.com"}):
            # Reload config to pick up env var
            config_module._config["api_url"] = os.getenv(
                "SKUA_API_URL", "https://api.skua.dev"
            )

            assert get_api_url() == "http://env.api.com"

    def test_web_url_from_environment(self, reset_config):
        """Test that SKUA_WEB_URL environment variable is respected."""
        with patch.dict(os.environ, {"SKUA_WEB_URL": "http://env.web.com"}):
            # Reload config to pick up env var
            config_module._config["web_url"] = os.getenv(
                "SKUA_WEB_URL", "https://skua.dev"
            )

            assert get_web_url() == "http://env.web.com"

    def test_configure_overrides_environment(self, reset_config):
        """Test that configure() overrides environment variables."""
        with patch.dict(os.environ, {"SKUA_API_URL": "http://env.api.com"}):
            # Env var is set, but configure() should override
            configure(api_url="http://configured.api.com")

            assert get_api_url() == "http://configured.api.com"


# =============================================================================
# Tests: URL Format Edge Cases
# =============================================================================


class TestUrlFormatEdgeCases:
    """Tests for URL format edge cases."""

    def test_trailing_slash_preserved(self, reset_config):
        """Test that trailing slashes are preserved as-is.

        Note: The config module doesn't normalize trailing slashes.
        The calling code should handle this if needed.
        """
        configure(api_url="http://api.test.com/")

        assert get_api_url() == "http://api.test.com/"

    def test_no_trailing_slash_preserved(self, reset_config):
        """Test that URLs without trailing slashes are preserved."""
        configure(api_url="http://api.test.com")

        assert get_api_url() == "http://api.test.com"

    def test_empty_string_url(self, reset_config):
        """Test behavior with empty string URL."""
        configure(api_url="")

        # Empty string is a valid (though probably wrong) value
        assert get_api_url() == ""

    def test_url_with_query_params(self, reset_config):
        """Test that URLs with query parameters are preserved."""
        configure(api_url="http://api.test.com?key=value")

        assert get_api_url() == "http://api.test.com?key=value"

    def test_url_with_fragment(self, reset_config):
        """Test that URLs with fragments are preserved."""
        configure(api_url="http://api.test.com#section")

        assert get_api_url() == "http://api.test.com#section"


# =============================================================================
# Tests: Session File Path Edge Cases
# =============================================================================


class TestSessionFilePathEdgeCases:
    """Tests for session file path edge cases."""

    def test_nested_path(self, reset_config, tmp_path):
        """Test that deeply nested paths are handled."""
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "session"
        configure(session_file=deep_path)

        assert get_session_file() == deep_path

    def test_path_with_spaces(self, reset_config, tmp_path):
        """Test that paths with spaces are handled."""
        space_path = tmp_path / "path with spaces" / "session"
        configure(session_file=space_path)

        assert get_session_file() == space_path

    def test_path_with_special_chars(self, reset_config, tmp_path):
        """Test that paths with special characters are handled."""
        special_path = tmp_path / "path-with_special.chars" / "session"
        configure(session_file=special_path)

        assert get_session_file() == special_path


# =============================================================================
# Tests: Configuration State
# =============================================================================


class TestConfigurationState:
    """Tests for configuration state management."""

    def test_config_is_module_level(self, reset_config):
        """Test that configuration is shared at module level."""
        # Set in one call
        configure(api_url="http://test1.com")

        # Get from another import
        from skua.config import get_api_url as get_api_url_fresh

        assert get_api_url_fresh() == "http://test1.com"

    def test_config_persists_across_calls(self, reset_config):
        """Test that configuration persists across multiple getter calls."""
        configure(api_url="http://persistent.com")

        assert get_api_url() == "http://persistent.com"
        assert get_api_url() == "http://persistent.com"
        assert get_api_url() == "http://persistent.com"


# =============================================================================
# Tests: Type Safety
# =============================================================================


class TestTypeSafety:
    """Tests for type safety in configuration."""

    def test_api_url_accepts_string(self, reset_config):
        """Test that api_url accepts string type."""
        configure(api_url="http://string.url.com")

        assert get_api_url() == "http://string.url.com"

    def test_session_file_accepts_path(self, reset_config, tmp_path):
        """Test that session_file accepts Path type."""
        path = tmp_path / "session"
        configure(session_file=path)

        assert get_session_file() == path

    def test_session_file_accepts_string_path(self, reset_config, tmp_path):
        """Test that session_file can work with Path created from string."""
        path_str = str(tmp_path / "session")
        configure(session_file=Path(path_str))

        assert get_session_file() == Path(path_str)


# =============================================================================
# Tests: get_token()
# =============================================================================


class TestGetToken:
    """Tests for get_token() function."""

    def test_returns_none_by_default(self, reset_config):
        """Test that None is returned when token not configured."""
        config_module._config["token"] = None

        assert get_token() is None

    def test_returns_configured_token(self, reset_config):
        """Test that configured token is returned."""
        configure(token="my-secret-token")

        assert get_token() == "my-secret-token"

    def test_configure_preserves_token(self, reset_config):
        """Test that configuring other values doesn't clear token."""
        configure(token="keep-me")
        configure(api_url="http://other.com")

        assert get_token() == "keep-me"

    def test_token_can_be_updated(self, reset_config):
        """Test that token can be changed via configure()."""
        configure(token="first-token")
        assert get_token() == "first-token"

        configure(token="second-token")
        assert get_token() == "second-token"

    def test_none_does_not_clear_token(self, reset_config):
        """Test that passing None explicitly does not clear token."""
        configure(token="set-token")
        configure(token=None)

        assert get_token() == "set-token"


# =============================================================================
# Tests: Documentation Examples
# =============================================================================


class TestDocumentationExamples:
    """Tests that verify documentation examples work correctly."""

    def test_basic_configure_example(self, reset_config):
        """Test the basic configure example from docstring."""
        # From: skua.configure(api_url="http://localhost:8000", web_url="http://localhost:5173")
        configure(api_url="http://localhost:8000", web_url="http://localhost:5173")

        assert get_api_url() == "http://localhost:8000"
        assert get_web_url() == "http://localhost:5173"

    def test_local_development_setup(self, reset_config, tmp_path):
        """Test typical local development configuration."""
        session_file = tmp_path / "dev_session"
        configure(
            api_url="http://localhost:8000",
            web_url="http://localhost:5173",
            session_file=session_file,
        )

        assert get_api_url() == "http://localhost:8000"
        assert get_web_url() == "http://localhost:5173"
        assert get_session_file() == session_file

    def test_production_defaults(self, reset_config, clean_env):
        """Test that production defaults are sensible."""
        assert get_api_url() == "https://api.skua.dev"
        assert get_web_url() == "https://skua.dev"
        assert get_session_file() == Path.home() / ".skua" / "session"
        assert get_session_public() is None
