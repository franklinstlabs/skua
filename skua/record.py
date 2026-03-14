"""Main record() function for Skua."""

from typing import Any, Optional

from skua.client import upload_finding
from skua.config import get_session_public, get_web_url
from skua.result import RecordResult
from skua.serializers import serialize_object


def record(
    obj: Any,
    title: str,
    description: Optional[str] = None,
    public: Optional[bool] = None,
) -> RecordResult:
    """Record and share a Python object via Skua.

    Serializes the object, uploads it to Skua, and returns a RecordResult object
    that wraps the original object while providing access to the URL and metadata.

    In Jupyter notebooks, the RecordResult displays the original object transparently,
    so you can use record() as the last call in a cell to display the object.

    Args:
        obj: Object to record (matplotlib figure, pandas DataFrame, etc.)
        title: Title for the finding (required, max 500 characters)
        description: Optional short description providing context (max 1000 characters)
        public: Override visibility for this finding.
                True = anyone with the URL can view.
                False = private, only you can view (requires verified account).
                None = use the default from skua.init(), or the server default
                (public for anonymous users, private for verified users).

    Returns:
        RecordResult object with:
        - Displays as the original object in notebooks
        - .url: The shareable URL
        - .metadata: Finding metadata (id, title, visibility)

    Raises:
        UploadError: If upload to Skua API fails
        SerializationError: If object cannot be serialized

    Examples:
        Basic usage:
        >>> skua.record(fig, title="Q3 Revenue")
        ✓ swift-gannet-4291 · Q3 Revenue → https://skua.dev/f/abc123 (private)

        Public override:
        >>> skua.record(fig, title="Q3 Revenue", public=True)
        ✓ swift-gannet-4291 · Q3 Revenue → https://skua.dev/f/abc123 (public)

        Session default via init():
        >>> skua.init(public=True)
        >>> skua.record(fig, title="Revenue")  # uses public default
        ✓ swift-gannet-4291 · Revenue → https://skua.dev/f/abc123 (public)
    """
    from skua.exceptions import ValidationError

    if obj is None:
        raise ValidationError(
            "Cannot record None. "
            "Pass a matplotlib figure, pandas DataFrame, PIL Image, or other object."
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

    # Resolve visibility: per-call > init() default > None (server decides)
    if public is not None:
        visibility = "public" if public else "private"
    elif (session_public := get_session_public()) is not None:
        visibility = "public" if session_public else "private"
    else:
        visibility = None  # Server applies its own default

    serialized = serialize_object(obj)

    finding_data = {
        "content": serialized,
        "title": title.strip(),
        "description": description,
        "visibility": visibility,
    }

    result = upload_finding(finding_data)

    finding_id = result["id"]
    creator_username = result.get("creator_username")
    applied_visibility = result.get("visibility", "public")

    url = f"{get_web_url()}/f/{finding_id}"

    # Print success line: ✓ username · Title → URL (visibility)
    if creator_username:
        print(f"✓ {creator_username} · {title.strip()} → {url} ({applied_visibility})")
    else:
        print(f"✓ {title.strip()} → {url} ({applied_visibility})")

    metadata = {
        "id": finding_id,
        "title": title.strip(),
        "visibility": applied_visibility,
    }

    return RecordResult(obj=obj, url=url, metadata=metadata)
