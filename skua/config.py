"""Configuration for Skua.

All runtime settings are resolved from environment variables. `skua.configure()`
is deprecated — it exists only to keep older notebooks running. Prefer:

    SKUA_API_URL    — override the API host (default: https://api.skua.dev)
    SKUA_WEB_URL    — override the web host (default: https://skua.dev)
    SKUA_TOKEN      — authentication token (also supported: ~/.skua/client file)

Per-collection visibility lives on `skua.collection(visibility=...)` now,
not here.
"""

import os
import warnings
from pathlib import Path
from typing import Optional

# `client_token_file` is the on-disk store for the X-Skua-Token value used by
# every API call from this machine. The same file is used whether the user
# is anonymous (auto-generated `anon_*` value) or verified (token persisted
# after login() / auth()) — there is no "session" concept on disk anymore.
#
# The legacy ~/.skua/session and ~/.skua/token files are still read on first
# access (see client.get_client_token) so existing installs migrate
# transparently. New writes always go to ~/.skua/client.
_config = {
    "api_url": os.getenv("SKUA_API_URL", "https://api.skua.dev"),
    "web_url": os.getenv("SKUA_WEB_URL", "https://skua.dev"),
    "client_token_file": Path.home() / ".skua" / "client",
    "token": None,
}


def configure(
    api_url: Optional[str] = None,
    web_url: Optional[str] = None,
    session_file: Optional[Path] = None,
    token: Optional[str] = None,
    client_token_file: Optional[Path] = None,
) -> None:
    """Deprecated. Use environment variables (SKUA_API_URL, SKUA_WEB_URL,
    SKUA_TOKEN) instead, and set per-collection visibility on
    `skua.collection(visibility=...)`.

    Kept so old notebooks don't break. Emits DeprecationWarning.
    """
    warnings.warn(
        "skua.configure() is deprecated. Use the SKUA_API_URL / SKUA_WEB_URL / "
        "SKUA_TOKEN environment variables, and set per-collection visibility "
        "on skua.collection(visibility=...). This function will be removed "
        "in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )

    if api_url is not None:
        _config["api_url"] = api_url

    if web_url is not None:
        _config["web_url"] = web_url

    # `session_file` is the historical kwarg name; still honored as an alias.
    if client_token_file is not None:
        _config["client_token_file"] = client_token_file
    elif session_file is not None:
        _config["client_token_file"] = session_file

    if token is not None:
        _config["token"] = token


def get_api_url() -> str:
    return _config["api_url"]


def get_web_url() -> str:
    return _config["web_url"]


def get_client_token_file() -> Path:
    return _config["client_token_file"]


# Back-compat alias — older callers (and tests) still reach for this.
def get_session_file() -> Path:
    return get_client_token_file()


def get_token() -> Optional[str]:
    """Return an explicit auth token from runtime config or env var.

    Note: this does NOT read the on-disk client token file — that lives in
    `client.get_client_token()`. Use this only when you want to know if an
    explicit override (SKUA_TOKEN / configure(token=...)) is in effect.
    """
    token = _config.get("token")
    if token:
        return token

    token = os.getenv("SKUA_TOKEN")
    if token:
        return token

    return None
