"""Module-level record() and the shared _record_impl that Collection.record() also uses."""

from __future__ import annotations

from typing import Any, Literal, Optional

from skua.client import get_auth_status, upload_record
from skua.config import get_api_url, get_web_url
from skua.exceptions import UploadError, ValidationError
from skua.result import RecordResult
from skua.serializers import serialize_object

Visibility = Literal["public", "unlisted", "private"]
_VALID_VISIBILITIES = ("public", "unlisted", "private")


def record(
    obj: Any,
    title: str,
    description: Optional[str] = None,
    visibility: Optional[Visibility] = None,
    tags: Optional[list[str]] = None,
) -> RecordResult:
    """Record and share a Python object via Skua's per-user Default collection.

    Args:
        obj: Object to record (matplotlib figure, pandas DataFrame, etc.).
        title: Title for the record (max 500 chars).
        description: Optional description (max 1000 chars).
        visibility: One of "public", "unlisted", "private". Omit for server default.
        tags: Optional tags (max 20, each ≤30 chars).

    For project-scoped collections, use `skua.collection(name).record(...)` instead.

    Returns:
        RecordResult with .url and .metadata. Displays as the original object in notebooks.

    Raises:
        ValidationError: If args are invalid.
        UploadError: If upload fails.
        SerializationError: If object cannot be serialized.
    """
    return _record_impl(
        obj,
        title=title,
        description=description,
        visibility=visibility,
        tags=tags,
        collection_name=None,
    )


def _record_impl(
    obj: Any,
    title: str,
    description: Optional[str] = None,
    visibility: Optional[Visibility] = None,
    tags: Optional[list[str]] = None,
    collection_name: Optional[str] = None,
) -> RecordResult:
    """Shared upload path used by both module-level record() and Collection.record().

    Visibility resolution lives server-side (see backend/api/records.py): per-call
    visibility wins; otherwise the collection's persisted default_visibility is
    used; final fallback 'unlisted'. The SDK no longer substitutes a collection's
    default at the client side — that was the old process-local behavior, replaced
    by server-persisted defaults in 0.12 (spec at
    docs/superpowers/specs/2026-04-24-collection-sdk-api-design.md)."""

    if obj is None:
        raise ValidationError(
            "Cannot record None. "
            "Pass a matplotlib figure, pandas DataFrame, PIL Image, or other object."
        )
    if isinstance(obj, (str, dict, list)) and len(obj) == 0:
        raise ValidationError(
            f"Cannot record empty {type(obj).__name__}. "
            "Pass a value with actual content."
        )
    # Defensive type-check before any string ops. Belt-and-braces against
    # callers passing a Mock, an int, or some other non-string — caught a
    # production-data leak in the past where a test fixture's MagicMock
    # ended up being sent as the record title.
    if not isinstance(title, str):
        raise ValidationError(
            f"Title must be a string, got {type(title).__name__}."
        )
    if not title or not title.strip():
        raise ValidationError("Title is required.")
    if len(title) > 500:
        raise ValidationError(
            f"Title too long ({len(title)} characters). Maximum: 500 characters."
        )
    if description and len(description) > 1000:
        raise ValidationError(
            f"Description too long ({len(description)} characters). Maximum: 1000 characters."
        )

    clean_tags: list[str] = []
    if tags:
        clean_tags = [t.strip() for t in tags if t.strip()]
        if len(clean_tags) > 20:
            raise ValidationError(f"Too many tags ({len(clean_tags)}). Maximum: 20 tags.")
        for tag in clean_tags:
            if len(tag) > 30:
                raise ValidationError(
                    f"Tag too long ({len(tag)} characters): '{tag[:20]}...'. Maximum: 30 characters."
                )

    # Per-call visibility wins; otherwise omit and let the server fall back to
    # the collection's persisted default_visibility (or 'unlisted' as the
    # backend hard fallback).
    if visibility is not None and visibility not in _VALID_VISIBILITIES:
        raise ValidationError(
            f"Invalid visibility {visibility!r}. "
            f"Expected one of: {', '.join(_VALID_VISIBILITIES)}."
        )

    # Fail-fast for anon → 'private'. The backend rejects the same shape with
    # the same message, but it'd only fire after we serialize and upload up
    # to 10MB. The /auth/status roundtrip is only paid when the caller asks
    # for private explicitly — the common no-kwarg path stays network-cheap.
    if visibility == "private":
        if not get_auth_status().get("verified"):
            raise UploadError(
                "Private visibility requires a verified account. "
                "Run `skua.login()` to verify your email, or use "
                "visibility='unlisted' for an unguessable shareable link."
            )

    serialized = serialize_object(obj)

    record_data: dict[str, Any] = {
        "content": serialized,
        "title": title.strip(),
        "description": description,
        "visibility": visibility,
        "tags": clean_tags,
    }
    if collection_name is not None:
        record_data["collection_name"] = collection_name

    result = upload_record(record_data)

    record_id = result["id"]
    creator_username = result.get("creator_username")
    applied_visibility = result.get("visibility", "public")
    collection_id = result.get("collection_id")
    response_collection_name = result.get("collection_name")
    collection_url = result.get("collection_url")

    url = f"{get_web_url()}/r/{record_id}"
    raw_url = f"{get_api_url()}/records/{record_id}/raw"

    label = response_collection_name or "Default"
    print(f"✓ {label} · {title.strip()} → {url} ({applied_visibility})")

    metadata: dict[str, Any] = {
        "id": record_id,
        "title": title.strip(),
        "visibility": applied_visibility,
        "raw_url": raw_url,
        "collection_name": response_collection_name,
        "collection_id": collection_id,
        "collection_url": collection_url,
    }
    if creator_username:
        metadata["creator_username"] = creator_username

    return RecordResult(obj=obj, url=url, metadata=metadata)
