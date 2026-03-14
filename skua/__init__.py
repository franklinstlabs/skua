"""Skua - Record and share Jupyter notebook findings via shareable links."""

from skua.client import get_auth_status, login, set_token
from skua.config import configure, init
from skua.exceptions import ConfigurationError, SkuaError, UploadError
from skua.record import record
from skua.result import RecordResult

__version__ = "0.1.1"

__all__ = [
    "record",
    "init",
    "RecordResult",
    "configure",
    "login",
    "token",
    "SkuaError",
    "UploadError",
    "ConfigurationError",
]

# User-facing aliases
token = set_token       # skua.token("sk_...")
status = get_auth_status
