"""Tests for skua.open_profile().

Covers:
- Verified user: one-click login URL, webbrowser.open() called
- Anonymous user: plain public profile URL, no browser-session flow
- open_browser=False returns URL without opening
- Network errors surface as UploadError
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from skua.exceptions import UploadError
from skua.profile import open_profile


@pytest.fixture
def mock_session_id():
    with patch("skua.profile.get_client_token", return_value="sk_cli_token"):
        yield


@pytest.fixture
def mock_api_url():
    with patch("skua.profile.get_api_url", return_value="https://api.skua.dev"):
        yield


@pytest.fixture
def mock_web_url():
    with patch("skua.profile.get_web_url", return_value="https://skua.dev"):
        yield


@pytest.fixture
def fake_response():
    """Factory for a fake requests.Response."""

    def _make(status_code: int, json_body: dict) -> MagicMock:
        resp = MagicMock(spec=requests.Response)
        resp.status_code = status_code
        resp.json.return_value = json_body
        if status_code >= 400:
            err = requests.exceptions.HTTPError(response=resp)
            resp.raise_for_status.side_effect = err
        else:
            resp.raise_for_status.return_value = None
        return resp

    return _make


def _status(verified: bool, username: str = "swift-gannet-4291") -> dict:
    """Shape of the /auth/status payload we care about."""
    return {
        "verified": verified,
        "authenticated": verified,
        "username": username,
        "email": "me@example.com" if verified else None,
    }


class TestOpenProfileVerified:
    def test_happy_path_opens_browser(
        self, mock_session_id, mock_api_url, mock_web_url, fake_response
    ):
        url = "https://skua.dev/auth/browser?t=abcd"
        with patch(
            "skua.profile.requests.get",
            return_value=fake_response(200, _status(verified=True)),
        ), patch(
            "skua.profile.requests.post",
            return_value=fake_response(200, {"url": url, "expires_in_seconds": 300}),
        ), patch(
            "skua.profile.webbrowser.open"
        ) as mock_open:
            result = open_profile()

        assert result == url
        mock_open.assert_called_once_with(url)

    def test_open_browser_false_skips_webbrowser(
        self, mock_session_id, mock_api_url, mock_web_url, fake_response
    ):
        url = "https://skua.dev/auth/browser?t=abcd"
        with patch(
            "skua.profile.requests.get",
            return_value=fake_response(200, _status(verified=True)),
        ), patch(
            "skua.profile.requests.post",
            return_value=fake_response(200, {"url": url, "expires_in_seconds": 300}),
        ), patch(
            "skua.profile.webbrowser.open"
        ) as mock_open:
            result = open_profile(open_browser=False)

        assert result == url
        mock_open.assert_not_called()

    def test_sends_session_token_header(
        self, mock_session_id, mock_api_url, mock_web_url, fake_response
    ):
        with patch(
            "skua.profile.requests.get",
            return_value=fake_response(200, _status(verified=True)),
        ) as mock_get, patch(
            "skua.profile.requests.post",
            return_value=fake_response(
                200, {"url": "https://skua.dev/auth/browser?t=x", "expires_in_seconds": 300}
            ),
        ) as mock_post, patch(
            "skua.profile.webbrowser.open"
        ):
            open_profile(open_browser=False)

        assert mock_get.call_args.kwargs["headers"]["X-Skua-Token"] == "sk_cli_token"
        assert mock_post.call_args.kwargs["headers"]["X-Skua-Token"] == "sk_cli_token"


class TestOpenProfileAnonymous:
    def test_anon_returns_public_url_without_login_flow(
        self, mock_session_id, mock_api_url, mock_web_url, fake_response
    ):
        """Anonymous client → plain /u/<username>, no browser-session POST."""
        with patch(
            "skua.profile.requests.get",
            return_value=fake_response(200, _status(verified=False, username="swift-gannet-4291")),
        ), patch("skua.profile.requests.post") as mock_post, patch(
            "skua.profile.webbrowser.open"
        ) as mock_open:
            result = open_profile()

        assert result == "https://skua.dev/u/swift-gannet-4291"
        mock_open.assert_called_once_with("https://skua.dev/u/swift-gannet-4291")
        mock_post.assert_not_called()

    def test_anon_respects_open_browser_false(
        self, mock_session_id, mock_api_url, mock_web_url, fake_response
    ):
        with patch(
            "skua.profile.requests.get",
            return_value=fake_response(200, _status(verified=False)),
        ), patch("skua.profile.webbrowser.open") as mock_open:
            result = open_profile(open_browser=False)

        assert result.startswith("https://skua.dev/u/")
        mock_open.assert_not_called()

    def test_anon_without_username_raises(
        self, mock_session_id, mock_api_url, mock_web_url, fake_response
    ):
        """A status response missing `username` is a server bug; fail loudly."""
        with patch(
            "skua.profile.requests.get",
            return_value=fake_response(
                200, {"verified": False, "authenticated": False, "username": None}
            ),
        ):
            with pytest.raises(UploadError) as exc:
                open_profile(open_browser=False)

        assert "username" in str(exc.value).lower()


class TestOpenProfileErrors:
    def test_status_network_error_raises(self, mock_session_id, mock_api_url, mock_web_url):
        with patch(
            "skua.profile.requests.get",
            side_effect=requests.exceptions.ConnectionError("boom"),
        ):
            with pytest.raises(UploadError) as exc:
                open_profile(open_browser=False)

        assert "boom" in str(exc.value)

    def test_verified_browser_session_error_raises(
        self, mock_session_id, mock_api_url, mock_web_url, fake_response
    ):
        """If /auth/status says verified but /auth/browser-session fails, surface it."""
        with patch(
            "skua.profile.requests.get",
            return_value=fake_response(200, _status(verified=True)),
        ), patch(
            "skua.profile.requests.post",
            return_value=fake_response(
                500, {"error": {"message": "Internal error", "code": "ServerError"}}
            ),
        ):
            with pytest.raises(UploadError):
                open_profile(open_browser=False)
