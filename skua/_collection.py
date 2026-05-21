"""Named collection handles for the Skua SDK.

A *collection* is a user-facing scope for records. Users create handles via
`skua.collection(name)`; calling twice with the same name (after whitespace trim)
returns the same handle. Bare `skua.record()` writes to a per-user "Default"
collection without needing a handle.

First call to `skua.collection(name)` within a process performs a synchronous
backend roundtrip (`POST /collections`) — the response gives the handle its id,
url, and persisted visibility. Subsequent calls in the same process return the
cached handle without network I/O.

Modeled on Python's `logging.getLogger(name)` — named handles are global,
fetched by name. The visibility kwarg is a creation hint: persisted server-side
on first creation; later calls with conflicting kwargs raise ConfigurationError
rather than silently ignore.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from skua.client import get_auth_status
from skua.exceptions import ConfigurationError, UploadError, ValidationError

Visibility = Literal["public", "unlisted", "private"]
_VALID_VISIBILITIES = ("public", "unlisted", "private")
_MAX_NAME_LENGTH = 100

_collections: dict[str, "Collection"] = {}


def _validate_name(name: str) -> str:
    """Trim and validate a collection name. Returns the normalized form."""
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError("Collection name must be non-empty.")
    if len(cleaned) > _MAX_NAME_LENGTH:
        raise ValidationError(
            f"Collection name too long ({len(cleaned)} chars). "
            f"Maximum: {_MAX_NAME_LENGTH}."
        )
    return cleaned


def _validate_visibility(visibility: Optional[str]) -> Optional[str]:
    if visibility is None:
        return None
    if visibility not in _VALID_VISIBILITIES:
        raise ValidationError(
            f"Invalid visibility {visibility!r}. "
            f"Expected one of: {', '.join(_VALID_VISIBILITIES)}."
        )
    return visibility


class Collection:
    """A handle to a named user-facing collection.

    Don't instantiate directly — use `skua.collection(name)` to get a handle
    that's cached by name within the process.

    Attributes:
        id: 12-char base62 collection id (for /c/{id} URLs).
        name: Display name (the user's original casing).
        visibility: Persisted access-gate visibility on the collection
            ('public' / 'unlisted' / 'private').
        url: Canonical /c/{id} URL — shareable.
    """

    def __init__(
        self,
        *,
        id: str,
        name: str,
        visibility: str,
        url: str,
    ) -> None:
        self.id = id
        self.name = name
        self.visibility = visibility
        self.url = url

    def record(self, obj: Any, title: str, **kwargs: Any) -> Any:
        """Record an object into this collection.

        Same signature as module-level `skua.record()`; the collection's name
        is appended to the wire payload as `collection_name`. Per-call
        `visibility=` overrides the collection's persisted default for this
        single record (server-side).
        """
        from skua.record import _record_impl
        return _record_impl(obj, title=title, collection_name=self.name, **kwargs)

    def __repr__(self) -> str:
        return f"Collection(name={self.name!r}, visibility={self.visibility!r}, url={self.url!r})"


def collection(name: str, *, visibility: Optional[Visibility] = None) -> Collection:
    """Return a named collection handle.

    First call within a process performs a synchronous backend roundtrip to
    create-or-get the collection row. Subsequent calls with the same name in
    the same process return the cached handle.

    Args:
        name: 1–100 chars after trim. Becomes the collection's display name.
        visibility: Persisted server-side as the collection's access gate.
            'public' (URL works + listed on profile), 'unlisted' (URL works,
            not on profile — the default), 'private' (URL only works for
            owner). Strict-error on mismatch with persisted value.

    Raises:
        ValidationError: If name is empty/too long, or visibility is invalid.
        ConfigurationError: If the collection already exists and the
            visibility kwarg conflicts with the persisted value. Drop the
            kwarg or pick a different name.

    Example:
        >>> c = skua.collection("Q3 Review")  # creates if needed
        >>> c.record(fig, title="Revenue")
        >>> c2 = skua.collection("Q3 Review")  # returns same handle, free
        >>> c is c2
        True
    """
    cleaned = _validate_name(name)
    visibility = _validate_visibility(visibility)

    existing = _collections.get(cleaned)
    if existing is not None:
        if visibility is not None and existing.visibility != visibility:
            raise ConfigurationError(
                f"Collection {cleaned!r} exists with visibility={existing.visibility!r}. "
                f"You passed visibility={visibility!r}. Drop the visibility= kwarg to "
                f"use it as-is, or pick a different name to create a new collection "
                f"with visibility={visibility!r}."
            )
        return existing

    # Fail-fast for anon → 'private' before any backend roundtrip. Same
    # rationale as record.py: only paid when 'private' is requested
    # explicitly, common path stays network-cheap.
    if visibility == "private":
        if not get_auth_status().get("verified"):
            raise UploadError(
                "Private visibility requires a verified account. "
                "Run `skua.login()` to verify your email, or use "
                "visibility='unlisted' for an unguessable shareable link."
            )

    # First touch in this process — synchronous backend resolution. The
    # server's 409 on visibility mismatch is converted to ConfigurationError
    # in client.create_or_get_collection.
    from skua.client import create_or_get_collection as _create_or_get

    response = _create_or_get(name=cleaned, visibility=visibility)
    handle = Collection(
        id=response["id"],
        name=response["name"],
        visibility=response["visibility"],
        url=response["url"],
    )
    _collections[cleaned] = handle
    return handle
