"""Open the current SDK user's profile page in a browser.

For a verified user, this mints a short-lived login URL so the browser
session is already signed in and private/unlisted records are visible.
For an anonymous user, it just opens the public profile URL directly —
anonymous sessions can't "log in" (there's no password or email), but
the profile page itself is public, so the visitor view still works.
"""

from __future__ import annotations

import webbrowser
from typing import Any

import requests

from skua.client import _extract_error_detail, get_client_token
from skua.config import get_api_url, get_web_url
from skua.exceptions import UploadError


def open_profile(open_browser: bool = True) -> str:
    """Open your profile page in a browser.

    Verified users get a short-lived one-click login URL so the browser
    lands already signed in — unlisted and private records are visible.
    Anonymous users get the bare public profile URL; the visitor view
    shows only public records and lacks the owner affordances (edit
    visibility, delete), since an anonymous client has no way to prove
    ownership in a browser session.

    Args:
        open_browser: If True (default), also calls webbrowser.open() so
                      the link pops up automatically. Set False to just get
                      the URL back (useful in headless/CI contexts).

    Returns:
        The profile URL. For verified users, a single-use login link
        valid for 5 minutes. For anonymous users, the plain public URL.

    Raises:
        UploadError: If the API call fails.

    Example:
        >>> import skua
        >>> skua.login()                 # optional — verified users get owner view
        >>> url = skua.open_profile()    # opens your profile in the browser
    """
    api_url = get_api_url()
    session_id = get_client_token()

    # Ask the API who this session belongs to. Using /auth/status instead
    # of branching on a local `anon_` prefix because verified clients keep
    # their original anon_ client id (they're just linked to a user now);
    # the server is the only authority on verified-or-not.
    try:
        status_response = requests.get(
            f"{api_url}/auth/status",
            headers={"X-Skua-Token": session_id},
            timeout=30,
        )
        status_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to open profile: {e}")

    status: dict[str, Any] = status_response.json()
    is_verified = bool(status.get("verified", status.get("authenticated", False)))
    username = status.get("username")

    if not is_verified:
        # Anonymous path: no login flow, just the public profile URL.
        # Username is always present (auto-generated adjective-bird-NNNN)
        # so this is the stable link to whatever this client has uploaded.
        if not username:
            raise UploadError(
                "Could not determine your profile URL — the server didn't return a "
                "username for this session."
            )
        url = f"{get_web_url()}/u/{username}"
        print(f"Opening your profile: {url}")
        if open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return url

    # Verified path: mint a one-click login URL so the browser lands signed in.
    try:
        response = requests.post(
            f"{api_url}/auth/browser-session",
            headers={"X-Skua-Token": session_id},
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as http_err:
        err_resp = http_err.response if http_err.response is not None else response
        detail = _extract_error_detail(err_resp)
        raise UploadError(f"Failed to open profile: {detail}")
    except requests.exceptions.RequestException as e:
        raise UploadError(f"Failed to open profile: {e}")

    body: dict[str, Any] = response.json()
    url: str = body["url"]

    print(f"Opening your profile: {url}")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            # Headless environments: user can still click the printed URL.
            pass

    return url


