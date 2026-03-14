"""HTTP client for Skua API."""

from __future__ import annotations

import secrets
from typing import Any

import requests

from skua.config import get_api_url, get_session_file, get_token, get_web_url
from skua.exceptions import UploadError


def get_session_id() -> str:
    """Get or create a session ID.

    If a token is configured via skua.configure(token=...), use it directly
    as the X-Skua-Token header value (the backend hashes it to find the session).

    Otherwise, fall back to the file-based anonymous session ID stored
    in ~/.skua/session.

    Returns:
        Session ID or token string
    """
    # Token-based auth takes priority (e.g. seed script, CI)
    token = get_token()
    if token:
        return token

    session_file = get_session_file()
    session_file.parent.mkdir(parents=True, exist_ok=True)

    # Try to read existing session ID
    if session_file.exists():
        session_id = session_file.read_text().strip()
        if session_id:
            return session_id

    # Generate new session ID
    session_id = f"anon_{secrets.token_hex(8)}"
    session_file.write_text(session_id)
    return session_id


def upload_finding(data: dict[str, Any]) -> dict[str, Any]:
    """Upload a finding to Skua API.

    Args:
        data: Dictionary containing:
            - content: Serialized content dict with 'data', 'type', 'format', 'metadata'
            - title: Finding title
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
        "tags": (None, json.dumps([])),
    }

    if data.get("description") is not None:
        form_data["description"] = (None, data["description"])

    if data.get("visibility") is not None:
        form_data["visibility"] = (None, data["visibility"])

    files = {"data": (filename, file_data)}

    headers = {"X-Skua-Token": session_id}

    try:
        response = requests.post(
            f"{api_url}/api/findings",
            data=form_data,
            files=files,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        # Use the response from the exception (may differ from our response var)
        err_resp = http_err.response if http_err.response is not None else response
        detail = str(getattr(err_resp, "status_code", "unknown"))
        try:
            body = err_resp.json()
            if isinstance(body, dict) and "detail" in body:
                detail = body["detail"]
        except Exception:
            pass
        raise UploadError(f"Failed to upload finding: {detail}")
    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to upload finding: {e}")

    result = response.json()
    return {
        "id": result["id"],
        "creator_username": result.get("creator_username"),
        "visibility": result.get("visibility", "public"),
    }


def login() -> str:
    """Open browser to verify your email and unlock longer retention.

    Opens skua.dev/verify where you enter your email. You'll receive
    an email with a skua.token("sk_...") command to paste in your notebook.

    Returns:
        URL that was opened in the browser

    Example:
        >>> import skua
        >>> skua.login()
        Opening browser to verify your email...
        'https://skua.dev/verify'
    """
    import webbrowser

    web_url = get_web_url()
    url = f"{web_url}/verify"

    print("Opening browser to verify your email...")
    print(f"If the browser doesn't open, visit: {url}")

    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print(f"Please visit: {url}")

    return url


def set_token(raw_token: str) -> None:
    """Activate a verification token and persist it.

    Called after receiving a token via email. Activates the token with
    the backend (upgrading the session), then saves it to ~/.skua/token
    for future use.

    Args:
        raw_token: Token from the verification email (sk_...)

    Raises:
        UploadError: If activation fails

    Example:
        >>> import skua
        >>> skua.token("sk_abc123def456...")
        Verified as user@example.com -- findings kept for 90 days
    """
    from pathlib import Path

    from skua.config import _config
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
    current_auth = get_session_id()

    try:
        response = requests.post(
            f"{api_url}/api/auth/activate-token",
            json={"token": raw_token},
            headers={"X-Skua-Token": current_auth},
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Try to extract detail from response
        detail = "Activation failed"
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        raise UploadError(f"Token activation failed: {detail}")

    data = response.json()

    # Persist token to file
    token_file = Path.home() / ".skua" / "token"
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(raw_token)

    # Update in-memory config so subsequent calls use this token
    _config["token"] = raw_token

    print(f"Verified as {data['email']} -- findings kept for {data['retention_days']} days")


# Backward compatibility alias
request_verification = login


def get_auth_status() -> dict[str, Any]:
    """Get current authentication status.

    Returns information about whether the current session is authenticated,
    the associated email if any, and the retention policy.

    Returns:
        Dictionary with keys:
        - authenticated (bool): Whether user is authenticated
        - email (str | None): Email address if authenticated, None otherwise
        - session_id (str): Current session ID
        - retention_days (int): Days findings are retained (7 for anonymous, 30+ for verified)

    Raises:
        UploadError: If the request fails

    Example:
        >>> import skua
        >>> status = skua.status()
        >>> if status["authenticated"]:
        ...     print(f"Logged in as {status['email']}")
        ... else:
        ...     print("Anonymous session")
    """
    api_url = get_api_url()
    session_id = get_session_id()

    headers = {
        "X-Skua-Token": session_id,
    }

    try:
        response = requests.get(
            f"{api_url}/api/auth/status",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to get authentication status: {e}")

    return response.json()
