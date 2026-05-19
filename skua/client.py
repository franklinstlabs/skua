"""HTTP client for Skua API."""

from __future__ import annotations

import secrets
from typing import Any

import requests

from skua.config import (
    get_api_url,
    get_client_token_file,
    get_session_file,  # noqa: F401 — back-compat re-export
    get_token,
    get_web_url,
)
from skua.exceptions import UploadError


def _extract_error_detail(resp: requests.Response) -> str:
    """Return the most human-readable error string from an API response.

    Tries these shapes in order:
    1. SkuaError envelope  → {"error": {"message": "..."}}
    2. FastAPI detail list → {"detail": [{"msg": "..."}, ...]}
    3. FastAPI detail str  → {"detail": "..."}
    4. Fallback            → "HTTP <status_code>"

    Never raises — malformed JSON or unexpected shapes fall back gracefully.
    """
    try:
        body = resp.json()
    except Exception:
        return f"HTTP {resp.status_code}"

    if not isinstance(body, dict):
        return f"HTTP {resp.status_code}"

    # Shape 1: our SkuaError envelope
    err = body.get("error")
    if isinstance(err, dict) and isinstance(err.get("message"), str):
        return err["message"]

    # Shape 2 + 3: FastAPI auto-422 / plain detail string
    detail = body.get("detail")
    if isinstance(detail, list):
        msgs = [item.get("msg", "") for item in detail if isinstance(item, dict)]
        joined = "; ".join(m for m in msgs if m)
        if joined:
            return joined
    elif isinstance(detail, str) and detail:
        return detail

    return f"HTTP {resp.status_code}"


def get_client_token() -> str:
    """Get or create the X-Skua-Token value for this machine.

    Resolution order:
      1. Explicit override — SKUA_TOKEN env or skua.configure(token=...)
      2. ~/.skua/client (canonical on-disk location)
      3. Legacy fallback — ~/.skua/token or ~/.skua/session, transparently
         migrated to ~/.skua/client on read
      4. Generate a fresh anonymous identity (anon_*), persist to
         ~/.skua/client

    The returned value is what we send as the X-Skua-Token header. Anonymous
    and verified identities are not distinguished here — the server decides
    that based on the token itself.
    """
    explicit = get_token()
    if explicit:
        return explicit

    client_file = get_client_token_file()
    client_file.parent.mkdir(parents=True, exist_ok=True)

    if client_file.exists():
        existing = client_file.read_text().strip()
        if existing:
            return existing

    # Migrate from legacy file locations. Verified token first (a verified
    # client whose ~/.skua/token still exists shouldn't lose its identity
    # just because we renamed files), then anonymous session as a fallback.
    for legacy_name in ("token", "session"):
        legacy = client_file.parent / legacy_name
        if legacy.exists():
            value = legacy.read_text().strip()
            if value:
                client_file.write_text(value)
                return value

    new_token = f"anon_{secrets.token_hex(8)}"
    client_file.write_text(new_token)
    return new_token


# Back-compat alias for the historic name. Internal call sites have been
# updated; external imports keep working.
def get_session_id() -> str:
    return get_client_token()


def upload_record(data: dict[str, Any]) -> dict[str, Any]:
    """Upload a record to Skua API.

    Args:
        data: Dictionary containing:
            - content: Serialized content dict with 'data', 'type', 'format', 'metadata'
            - title: Record title
            - description: Optional description
            - visibility: 'public' | 'private' | None (server decides if None)

    Returns:
        Dict with 'id', 'creator_username', 'visibility'

    Raises:
        UploadError: If upload fails or validation fails
    """
    import base64
    import json

    api_url = get_api_url()
    session_id = get_session_id()

    content = data["content"]

    # Prepare file data based on format
    if content["format"] in ("png", "jpg", "jpeg"):
        # Image data is base64-encoded
        file_data = base64.b64decode(content["data"])
        filename = f"image.{content['format']}"
    elif content["format"] == "json":
        # DataFrame JSON data - wrap with metadata
        payload = {
            "data": content["data"],
            "metadata": content.get("metadata", {}),
        }
        file_data = json.dumps(payload).encode("utf-8")
        filename = "data.json"
    else:
        # Text or other formats
        file_data = content["data"].encode("utf-8")
        filename = "data.txt"

    # Client-side validation: Check file size before upload (fail fast)
    max_size_bytes = 10 * 1024 * 1024  # 10MB (same limit as server)
    file_size_bytes = len(file_data)

    if file_size_bytes > max_size_bytes:
        size_mb = file_size_bytes / (1024 * 1024)
        max_mb = max_size_bytes / (1024 * 1024)
        raise UploadError(
            f"File too large ({size_mb:.1f}MB). "
            f"Maximum allowed: {max_mb}MB. "
            f"Try reducing image resolution or DataFrame size."
        )

    # Prepare form data
    form_data = {
        "title": (None, data["title"]),
        "content_type": (None, content["type"]),
        "tags": (None, json.dumps(data.get("tags", []))),
    }

    if data.get("description") is not None:
        form_data["description"] = (None, data["description"])

    if data.get("visibility") is not None:
        form_data["visibility"] = (None, data["visibility"])

    if data.get("collection_name") is not None:
        form_data["collection_name"] = (None, data["collection_name"])

    files = {"data": (filename, file_data)}

    # Optional OpenGraph preview sidecar. Plotly's serializer attaches a 1200×630
    # PNG via kaleido so social scrapers (LinkedIn/Slack/X) show the chart.
    # Sent as a second multipart file; the backend endpoint treats it as optional.
    preview_b64 = content.get("preview_png_b64")
    if preview_b64:
        preview_bytes = base64.b64decode(preview_b64)
        files["preview_png"] = ("preview.png", preview_bytes, "image/png")

    headers = {"X-Skua-Token": session_id}

    try:
        response = requests.post(
            f"{api_url}/records",
            data=form_data,
            files=files,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        err_resp = http_err.response if http_err.response is not None else response
        detail = _extract_error_detail(err_resp)
        raise UploadError(f"Failed to upload record: {detail}")
    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to upload record: {e}")

    result = response.json()

    # Surface a warning if this update silently replaced an artifact of a different
    # type (e.g. a DataFrame was just overwritten by a plot under the same title).
    # Same title = same URL is the product rule, but a type swap is usually an
    # oversight worth flagging.
    type_changed_from = result.get("type_changed_from")
    if type_changed_from:
        import sys
        new_type = data["content"]["type"]
        print(
            f"⚠ '{data['title']}' was a {type_changed_from}; "
            f"replaced with a {new_type}. Same URL, new content.",
            file=sys.stderr,
        )

    return {
        "id": result["id"],
        "creator_username": result.get("creator_username"),
        "visibility": result.get("visibility", "public"),
        "collection_id": result.get("collection_id"),
        "collection_name": result.get("collection_name"),
        "collection_url": result.get("collection_url"),
    }


def login(timeout: int = 300) -> None:
    """Verify your email to unlock 365-day retention.

    Opens skua.dev/verify in your browser with the current session pre-linked,
    then polls until you complete the verification in the browser.

    If this session is already verified (e.g. a previous skua.login() timed
    out but the user clicked the email link afterwards), short-circuit
    immediately instead of opening a new verify flow.

    Args:
        timeout: Seconds to wait for verification (default 300 = 5 minutes)

    Example:
        >>> import skua
        >>> skua.login()
        Opened https://skua.dev/verify in your browser.
        Complete verification there; I'll wait...
        Verified as you@example.com -- records kept for 365 days
        Profile: https://skua.dev/u/your-username
    """
    import time
    import webbrowser

    api_url = get_api_url()
    web_url = get_web_url()
    client_token = get_client_token()
    session_id = client_token  # back-compat name used below

    def _persist_verified(data: dict[str, Any]) -> None:
        """Persist the verified client token and announce the result.

        After verification the same X-Skua-Token value now resolves to a
        verified client server-side, so we just rewrite the canonical
        client file and print the user's profile URL — the URL is the
        single most useful piece of post-login information (it's where
        every record they record will land).
        """
        client_file = get_client_token_file()
        client_file.parent.mkdir(parents=True, exist_ok=True)
        client_file.write_text(client_token)
        print(
            f"Verified as {data['email']} -- records kept for {data['retention_days']} days"
        )
        username = data.get("username")
        if username:
            print(f"Profile: {web_url}/u/{username}")

    # Fast path: if the session is already verified (late-click recovery),
    # just persist and exit. No browser, no polling.
    try:
        pre_check = requests.get(
            f"{api_url}/auth/status",
            headers={"X-Skua-Token": session_id},
            timeout=10,
        )
        if pre_check.ok:
            data = pre_check.json()
            if data.get("verified") or data.get("authenticated"):
                _persist_verified(data)
                return
    except requests.exceptions.RequestException:
        pass  # Network blip, fall through to the normal flow.

    verify_url = f"{web_url}/verify?client={session_id}"

    try:
        webbrowser.open(verify_url)
    except Exception:
        pass  # If the browser can't launch, the URL is still printed below.

    print(f"Opened {web_url}/verify in your browser.")
    print("Complete verification there; I'll wait...")
    print(f"(If the browser didn't open: visit {verify_url})")
    print(f"Waiting up to {timeout // 60} minutes...")

    # Poll /auth/status until the browser-side verification completes.
    poll_interval = 3
    deadline = time.time() + timeout

    while time.time() < deadline:
        time.sleep(poll_interval)
        try:
            status_response = requests.get(
                f"{api_url}/auth/status",
                headers={"X-Skua-Token": session_id},
                timeout=10,
            )
            if status_response.ok:
                data = status_response.json()
                if data.get("authenticated"):
                    _persist_verified(data)
                    return
        except requests.exceptions.RequestException:
            pass  # Network blip, keep polling

    print("Timed out waiting for verification.")
    print("If you clicked the email link, re-run skua.login() — it will detect the verified session.")
    print("Otherwise, paste the skua.token(\"sk_...\") command from your email.")


def set_token(raw_token: str) -> None:
    """Activate a verification token and persist it.

    Called after receiving a token via email. Activates the token with
    the backend (upgrading the client), then saves it to ~/.skua/client
    for future use.

    Args:
        raw_token: Token from the verification email (sk_...)

    Raises:
        UploadError: If activation fails

    Example:
        >>> import skua
        >>> skua.token("sk_abc123def456...")
        Verified as user@example.com -- records kept for 365 days
        Profile: https://skua.dev/u/your-username
    """
    from skua.exceptions import ValidationError

    if not raw_token.startswith("sk_"):
        raise ValidationError(
            "Invalid token format — must start with 'sk_'. "
            "Copy the full skua.token(\"sk_...\") command from your email."
        )
    if len(raw_token) <= 3:
        raise ValidationError(
            "Token too short. "
            "Copy the full skua.token(\"sk_...\") command from your email."
        )

    api_url = get_api_url()
    web_url = get_web_url()
    current_auth = get_client_token()

    response: requests.Response | None = None
    try:
        response = requests.post(
            f"{api_url}/auth/activate-token",
            json={"token": raw_token},
            headers={"X-Skua-Token": current_auth},
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        err_resp = http_err.response if http_err.response is not None else response
        detail = _extract_error_detail(err_resp) if err_resp is not None else "Activation failed"
        raise UploadError(f"Token activation failed: {detail}")
    except requests.exceptions.RequestException as e:
        raise UploadError(f"Token activation failed: {e}")

    data = response.json()

    # The activated token IS the new client identity — persist it to the
    # canonical client file. Also update in-memory config so subsequent
    # calls in this kernel pick it up immediately without re-reading.
    from skua.config import _config

    client_file = get_client_token_file()
    client_file.parent.mkdir(parents=True, exist_ok=True)
    client_file.write_text(raw_token)
    _config["token"] = raw_token

    print(f"Verified as {data['email']} -- records kept for {data['retention_days']} days")
    username = data.get("username")
    if username:
        print(f"Profile: {web_url}/u/{username}")


# Backward compatibility alias
request_verification = login


def get_auth_status() -> dict[str, Any]:
    """Get current authentication status.

    Returns:
        Dictionary with verified, email, username, retention_days.

    Raises:
        UploadError: If the request fails

    Example:
        >>> import skua
        >>> status = skua.status()
        >>> if status["verified"]:
        ...     print(f"Logged in as @{status['username']} ({status['email']})")
        ... else:
        ...     print(f"Anonymous as @{status['username']}")
    """
    api_url = get_api_url()
    session_id = get_session_id()

    headers = {"X-Skua-Token": session_id}

    response: requests.Response | None = None
    try:
        response = requests.get(
            f"{api_url}/auth/status",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        err_resp = http_err.response if http_err.response is not None else response
        detail = _extract_error_detail(err_resp) if err_resp is not None else "unknown error"
        raise UploadError(f"Failed to get authentication status: {detail}")
    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to get authentication status: {e}")

    payload = response.json()

    # Normalize the response. Older backends return only `authenticated`;
    # newer backends return both `verified` and `authenticated`. The public
    # SDK shape is `verified`.
    verified = bool(payload.get("verified", payload.get("authenticated", False)))

    return {
        "verified": verified,
        "email": payload.get("email"),
        "username": payload.get("username"),
        "retention_days": payload.get("retention_days"),
    }


def create_or_get_collection(
    name: str, *, visibility: str | None = None
) -> dict[str, Any]:
    """Idempotent create-or-get for a named collection.

    Hits POST /collections — the synchronous resolution endpoint that the
    Collection handle uses on first construction within a process.

    Args:
        name: Collection name (1-100 chars).
        visibility: One of 'public' / 'unlisted' / 'private', or None to
            fetch existing without asserting visibility.

    Returns:
        Dict with id, name, visibility, url, created_at, is_owner.

    Raises:
        ConfigurationError: If the collection already exists and the
            visibility kwarg conflicts with the persisted value (409 from
            the backend with VisibilityMismatchError shape).
        UploadError: For other HTTP failures.
    """
    api_url = get_api_url()
    session_id = get_session_id()

    form = {"name": name}
    if visibility is not None:
        form["visibility"] = visibility

    headers = {"X-Skua-Token": session_id}

    response: requests.Response | None = None
    try:
        response = requests.post(
            f"{api_url}/collections",
            data=form,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        err_resp = http_err.response if http_err.response is not None else response
        if err_resp is not None and err_resp.status_code == 409:
            # Visibility mismatch — surface as ConfigurationError so the
            # caller knows the kwarg conflicts with the persisted value.
            from skua.exceptions import ConfigurationError

            detail = _extract_error_detail(err_resp)
            raise ConfigurationError(detail)
        detail = _extract_error_detail(err_resp) if err_resp is not None else "unknown error"
        raise UploadError(f"Failed to resolve collection: {detail}")
    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to resolve collection: {e}")

    return response.json()


# Silent back-compat aliases — `upload_record` is the canonical name now.
# Left in place so pinned releases of downstream tooling keep working.
upload_snapshot = upload_record
upload_finding = upload_record
auth = set_token
