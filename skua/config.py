"""Configuration for Skua.

All runtime settings come from environment variables — there is no
`skua.configure()` call. Set these before importing skua:

    SKUA_API_URL    — override the API host (default: https://api.skua.dev)
    SKUA_WEB_URL    — override the web host (default: https://skua.dev)
    SKUA_TOKEN      — authentication token (also supported: ~/.skua/client file)

Per-collection visibility lives on `skua.collection(visibility=...)`.
"""

import os
from pathlib import Path
from typing import Optional

# `client_token_file` is the on-disk store for the X-Skua-Token value used by
# every API call from this machine. Same file whether the user is anonymous
# (auto-generated `anon_*`) or verified (token persisted after login() /
# auth()) — there is no "session" concept on disk.
_config = {
    "api_url": os.getenv("SKUA_API_URL", "https://api.skua.dev"),
    "web_url": os.getenv("SKUA_WEB_URL", "https://skua.dev"),
    "client_token_file": Path.home() / ".skua" / "client",
    "token": None,
}


def get_api_url() -> str:
    return _config["api_url"]


def get_web_url() -> str:
    return _config["web_url"]


def get_client_token_file() -> Path:
    return _config["client_token_file"]


def get_token() -> Optional[str]:
    """Return an explicit auth token from runtime config or env var.

    Does NOT read the on-disk client token file — that's `client.get_client_token()`.
    Use this only when you want to know if an explicit override (SKUA_TOKEN)
    is in effect.
    """
    token = _config.get("token")
    if token:
        return token

    token = os.getenv("SKUA_TOKEN")
    if token:
        return token

    return None
