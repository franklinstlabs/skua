"""Skua — share Python objects via shareable web links."""

# Keep in sync with pyproject.toml's `version` field. We deliberately don't
# read via importlib.metadata: staging overlays source on top of a PyPI
# install, and metadata would report the stale PyPI version regardless of
# what this file says. The literal wins. See root CLAUDE.md > Versioning.
__version__ = "0.13.0"

from skua._collection import Collection, collection
from skua.client import get_auth_status, login, set_token
from skua.exceptions import ConfigurationError, SkuaError, UploadError
from skua.profile import open_profile
from skua.record import record
from skua.result import RecordResult

__all__ = [
    "record",
    "Record",
    "collection",
    "Collection",
    "auth",
    "login",
    "open_profile",
    "status",
    "SkuaError",
    "UploadError",
    "ConfigurationError",
]

# Primary aliases
auth = set_token
status = get_auth_status

# `Record` is the primary class name for the returned object.
Record = RecordResult
