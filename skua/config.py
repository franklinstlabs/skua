"""Configuration management for Skua."""

import os
from pathlib import Path
from typing import Optional

# Default configuration
_config = {
    "api_url": os.getenv("SKUA_API_URL", "https://api.skua.dev"),
    "web_url": os.getenv("SKUA_WEB_URL", "https://skua.dev"),
    "session_file": Path.home() / ".skua" / "session",
    "token": None,
}

# Session-wide settings set by skua.init()
_session_config: dict = {}


def init(public: Optional[bool] = None) -> None:
    """Set session-wide defaults for record().

    Call once at the top of a notebook to apply settings to all subsequent
    record() calls. Per-call arguments to record() override these defaults.

    Args:
        public: Whether findings are public (True) or private (False).
                If not set, the server decides based on your account status:
                anonymous users get public, verified users get private.

    Example:
        >>> import skua
        >>> skua.init(public=True)  # All findings public this session
        >>> skua.record(fig, title="Revenue")  # Uses the public default
        >>> skua.record(fig2, title="Internal", public=False)  # Override to private
    """
    if public is not None:
        _session_config["public"] = public


def get_session_public() -> Optional[bool]:
    """Get the session-wide public setting from init().

    Returns:
        True/False if set via init(), None if not configured
    """
    return _session_config.get("public")


def configure(
    api_url: Optional[str] = None,
    web_url: Optional[str] = None,
    session_file: Optional[Path] = None,
    token: Optional[str] = None,
) -> None:
    """Configure low-level Skua settings (API URL, token, etc.).

    For visibility defaults use skua.init() instead.

    Args:
        api_url: Base URL for Skua API (default: https://api.skua.dev)
        web_url: Base URL for Skua web app (default: https://skua.dev)
        session_file: Path to session ID file (default: ~/.skua/session)
        token: Authentication token for programmatic access (default: None)

    Example:
        >>> import skua
        >>> skua.configure(api_url="http://localhost:8000", web_url="http://localhost:5173")
    """
    if api_url is not None:
        _config["api_url"] = api_url

    if web_url is not None:
        _config["web_url"] = web_url

    if session_file is not None:
        _config["session_file"] = session_file

    if token is not None:
        _config["token"] = token


def get_api_url() -> str:
    """Get the configured API URL.

    Returns:
        API URL string
    """
    return _config["api_url"]


def get_session_file() -> Path:
    """Get the configured session file path.

    Returns:
        Path to session file
    """
    return _config["session_file"]


def get_token() -> Optional[str]:
    """Get the authentication token.

    Priority: runtime config > env var > ~/.skua/token file.

    Returns:
        Token string or None if not configured
    """
    # Runtime config (set via configure() or set_token())
    token = _config.get("token")
    if token:
        return token

    # Environment variable
    token = os.getenv("SKUA_TOKEN")
    if token:
        return token

    # Persisted token file
    token_file = Path.home() / ".skua" / "token"
    if token_file.exists():
        token = token_file.read_text().strip()
        if token:
            return token

    return None


def get_web_url() -> str:
    """Get the configured web app URL.

    Returns:
        Web app URL string
    """
    return _config["web_url"]
