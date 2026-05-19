"""Skua — share Python objects via shareable web links."""

# Keep in sync with pyproject.toml's `version` field. We deliberately don't
# read via importlib.metadata: staging overlays source on top of a PyPI
# install, and metadata would report the stale PyPI version regardless of
# what this file says. The literal wins. See root CLAUDE.md > Versioning.
__version__ = "0.12.0"

from skua._collection import Collection, collection
from skua.client import get_auth_status, login, set_token
from skua.config import configure
from skua.exceptions import ConfigurationError, SkuaError, UploadError
from skua.profile import open_profile
from skua.record import record, snap
from skua.result import RecordResult, SnapResult


def init(*args: object, **kwargs: object) -> None:
    """Removed in 0.12. Use skua.collection() or bare skua.record() instead.

    Raises ConfigurationError with a copy-paste migration snippet so existing
    notebooks fail loudly instead of silently misrouting records.
    """
    raise ConfigurationError(
        "skua.init() was removed in getskua 0.12.\n"
        "\n"
        "If you had a single named collection:\n"
        "    c = skua.collection(\"<your name>\")\n"
        "    c.record(fig, title=\"...\")\n"
        "\n"
        "If you want records to go to your private default:\n"
        "    skua.record(fig, title=\"...\")  # no init needed\n"
    )


__all__ = [
    "record",
    "Record",
    "collection",
    "Collection",
    "init",
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

# Silent back-compat aliases — not in __all__, not in docs.
token = set_token
