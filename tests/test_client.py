"""Tests for the Skua HTTP client module.

Covers:
- upload_finding() - main upload function
- get_session_id() - session management
- request_verification() - email verification flow
- get_auth_status() - authentication status check
- Error handling for network and HTTP errors
- Client-side validation (visibility, file size)
- URL construction and request formatting
"""

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
import requests

from skua.client import (
    get_session_id,
    upload_finding,
    login,
    set_token,
    request_verification,
    get_auth_status,
)
from skua.exceptions import UploadError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_session_dir(tmp_path):
    """Provide a temporary directory for session file.

    Patches get_session_file() to use a temp directory,
    preventing tests from touching the real ~/.skua/ directory.
    """
    session_file = tmp_path / "session"
    with patch("skua.client.get_session_file", return_value=session_file):
        yield session_file


@pytest.fixture
def mock_session_id():
    """Patch get_session_id to return a predictable value."""
    with patch("skua.client.get_session_id", return_value="anon_test123456") as mock:
        yield mock


@pytest.fixture
def mock_verified_session_id():
    """Patch get_session_id to return a verified (non-anonymous) session."""
    with patch("skua.client.get_session_id", return_value="verified_user_abc") as mock:
        yield mock


@pytest.fixture
def sample_image_data():
    """Provide sample base64-encoded image data for testing."""
    # 1x1 transparent PNG
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return {
        "content": {
            "type": "matplotlib.figure",
            "format": "png",
            "data": base64.b64encode(png_bytes).decode("utf-8"),
            "metadata": {"width": 1, "height": 1},
        },
        "title": "Test Image",
        "tags": ["test"],
    }


@pytest.fixture
def sample_json_data():
    """Provide sample JSON data (DataFrame format) for testing."""
    return {
        "content": {
            "type": "pandas.dataframe",
            "format": "json",
            "data": '{"columns":["a","b"],"index":[0,1],"data":[[1,2],[3,4]]}',
            "metadata": {"shape": [2, 2]},
        },
        "title": "Test DataFrame",
        "tags": ["data", "test"],
    }


@pytest.fixture
def sample_text_data():
    """Provide sample text data for testing."""
    return {
        "content": {
            "type": "text",
            "format": "text",
            "data": "Hello, world!",
            "metadata": {},
        },
        "title": "Test Text",
        "tags": [],
    }


# =============================================================================
# Tests: get_session_id()
# =============================================================================


class TestGetSessionId:
    """Tests for session ID retrieval and generation."""

    def test_creates_new_session_when_file_missing(self, temp_session_dir):
        """Test that a new session ID is created when file doesn't exist."""
        session_id = get_session_id()

        assert session_id.startswith("anon_")
        assert len(session_id) == 21  # "anon_" + 16 hex chars
        assert temp_session_dir.exists()
        assert temp_session_dir.read_text() == session_id

    def test_reads_existing_session(self, temp_session_dir):
        """Test that existing session ID is read from file."""
        existing_id = "anon_existingsession"
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text(existing_id)

        session_id = get_session_id()

        assert session_id == existing_id

    def test_creates_new_session_when_file_empty(self, temp_session_dir):
        """Test that a new session ID is created when file is empty."""
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text("")

        session_id = get_session_id()

        assert session_id.startswith("anon_")
        assert len(session_id) == 21

    def test_creates_new_session_when_file_whitespace(self, temp_session_dir):
        """Test that a new session ID is created when file is whitespace only."""
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text("   \n\t  ")

        session_id = get_session_id()

        assert session_id.startswith("anon_")
        assert len(session_id) == 21

    def test_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created if missing."""
        nested_path = tmp_path / "deep" / "nested" / "session"
        with patch("skua.client.get_session_file", return_value=nested_path):
            session_id = get_session_id()

        assert nested_path.parent.exists()
        assert nested_path.exists()
        assert session_id.startswith("anon_")

    def test_session_id_format_is_hex(self, temp_session_dir):
        """Test that generated session ID uses hex characters."""
        session_id = get_session_id()

        # Extract the random part after "anon_"
        random_part = session_id[5:]
        assert len(random_part) == 16
        # All characters should be valid hex
        int(random_part, 16)  # This will raise if not valid hex

    def test_token_takes_priority_over_file(self, temp_session_dir):
        """Test that a configured token is used instead of the session file."""
        # Write a session file that should be ignored
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text("anon_file_session")

        with patch("skua.client.get_token", return_value="my-api-token"):
            session_id = get_session_id()

        assert session_id == "my-api-token"

    def test_no_token_falls_back_to_file(self, temp_session_dir):
        """Test that None token falls back to file-based session."""
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text("anon_from_file")

        with patch("skua.client.get_token", return_value=None):
            session_id = get_session_id()

        assert session_id == "anon_from_file"


# =============================================================================
# Tests: upload_finding() - Successful Uploads
# =============================================================================


class TestUploadFindingSuccess:
    """Tests for successful upload_finding() calls."""

    def test_successful_image_upload(
        self, mock_session_id, sample_image_data, temp_session_dir
    ):
        """Test successful upload of image data."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "abc123", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_finding(sample_image_data)

            assert result["id"] == "abc123"
            mock_post.assert_called_once()

    def test_successful_json_upload(
        self, mock_session_id, sample_json_data, temp_session_dir
    ):
        """Test successful upload of JSON/DataFrame data."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "def456", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_finding(sample_json_data)

            assert result["id"] == "def456"

    def test_successful_text_upload(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test successful upload of text data."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "ghi789", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_finding(sample_text_data)

            assert result["id"] == "ghi789"

    def test_upload_with_description(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test upload with description parameter."""
        sample_text_data["description"] = "A test description"

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "desc123", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_finding(sample_text_data)

            assert result["id"] == "desc123"
            call_kwargs = mock_post.call_args.kwargs
            assert "description" in call_kwargs["data"]


# =============================================================================
# Tests: upload_finding() - Request Formatting
# =============================================================================


class TestUploadFindingRequestFormat:
    """Tests for correct request formatting in upload_finding()."""

    def test_sends_correct_headers(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that correct headers are sent with request."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            assert "headers" in call_kwargs
            assert call_kwargs["headers"]["X-Skua-Token"] == "anon_test123456"

    def test_sends_correct_form_data(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that form data is correctly structured."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]

            # Verify form fields (tuple format: (None, value))
            assert form_data["title"] == (None, "Test Text")
            assert form_data["content_type"] == (None, "text")
            assert form_data["tags"] == (None, "[]")

    def test_sends_file_data(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that file data is correctly formatted."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            files = call_kwargs["files"]

            # files["data"] is a tuple of (filename, content)
            assert "data" in files
            filename, content = files["data"]
            assert filename == "data.txt"
            assert content == b"Hello, world!"

    def test_json_data_wraps_with_metadata(
        self, mock_session_id, sample_json_data, temp_session_dir
    ):
        """Test that JSON data is wrapped with metadata."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_json_data)

            call_kwargs = mock_post.call_args.kwargs
            files = call_kwargs["files"]
            filename, content = files["data"]

            assert filename == "data.json"
            parsed = json.loads(content)
            assert "data" in parsed
            assert "metadata" in parsed
            assert parsed["metadata"]["shape"] == [2, 2]

    def test_image_data_decoded_from_base64(
        self, mock_session_id, sample_image_data, temp_session_dir
    ):
        """Test that image data is decoded from base64."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_image_data)

            call_kwargs = mock_post.call_args.kwargs
            files = call_kwargs["files"]
            filename, content = files["data"]

            assert filename == "image.png"
            # Should be bytes, not base64 string
            assert isinstance(content, bytes)
            # PNG magic number
            assert content[:4] == b"\x89PNG"

    def test_uses_correct_api_endpoint(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that the correct API endpoint is used."""
        with patch("skua.client.get_api_url", return_value="https://api.test.com"):
            with patch("skua.client.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
                mock_post.return_value.raise_for_status = MagicMock()

                upload_finding(sample_text_data)

                call_url = mock_post.call_args.args[0]
                assert call_url == "https://api.test.com/api/findings"

    def test_request_timeout_is_set(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that request timeout is properly set."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["timeout"] == 30

    def test_visibility_included_when_set(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that visibility is included in form data when provided."""
        sample_text_data["visibility"] = "private"

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "private", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            assert "visibility" in form_data
            assert form_data["visibility"] == (None, "private")

    def test_visibility_excluded_when_none(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that visibility is not sent when None (server decides)."""
        sample_text_data["visibility"] = None

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            assert "visibility" not in form_data


# =============================================================================
# Tests: upload_finding() - File Size Validation
# =============================================================================


class TestUploadFindingFileSizeValidation:
    """Tests for client-side file size validation."""

    def test_file_under_limit_allowed(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that files under the limit are allowed."""
        # Small data, well under 10MB
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_finding(sample_text_data)

            assert result["id"] == "test"

    def test_file_over_limit_raises_error(
        self, mock_session_id, temp_session_dir
    ):
        """Test that files over 10MB raise UploadError without making request."""
        # Create data over 10MB
        large_data = {
            "content": {
                "type": "text",
                "format": "text",
                "data": "x" * (11 * 1024 * 1024),  # 11MB
                "metadata": {},
            },
            "title": "Large File",
            "tags": [],
        }

        with patch("skua.client.requests.post") as mock_post:
            with pytest.raises(UploadError) as exc_info:
                upload_finding(large_data)

            # Verify error message
            assert "too large" in str(exc_info.value).lower()
            assert "11.0MB" in str(exc_info.value)
            assert "10.0MB" in str(exc_info.value)

            # Verify no HTTP request was made
            mock_post.assert_not_called()

    def test_file_exactly_at_limit_allowed(
        self, mock_session_id, temp_session_dir
    ):
        """Test that files exactly at 10MB are allowed."""
        # Create data exactly at 10MB
        exact_data = {
            "content": {
                "type": "text",
                "format": "text",
                "data": "x" * (10 * 1024 * 1024),  # Exactly 10MB
                "metadata": {},
            },
            "title": "Exact Size",
            "tags": [],
        }

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_finding(exact_data)

            assert result["id"] == "test"
            mock_post.assert_called_once()


# =============================================================================
# Tests: upload_finding() - HTTP Error Handling
# =============================================================================


class TestUploadFindingHttpErrors:
    """Tests for HTTP error handling in upload_finding()."""

    @pytest.mark.parametrize(
        "status_code,expected_in_message",
        [
            (400, "400"),
            (401, "401"),
            (403, "403"),
            (404, "404"),
            (413, "413"),
            (429, "429"),
            (500, "500"),
            (502, "502"),
            (503, "503"),
        ],
    )
    def test_http_error_responses(
        self,
        mock_session_id,
        sample_text_data,
        temp_session_dir,
        status_code,
        expected_in_message,
    ):
        """Test that HTTP error responses raise UploadError with status code."""
        with patch("skua.client.requests.post") as mock_post:
            # Create a proper HTTPError
            response = MagicMock()
            response.status_code = status_code
            http_error = requests.exceptions.HTTPError(
                f"{status_code} Error", response=response
            )
            mock_post.return_value.raise_for_status.side_effect = http_error

            with pytest.raises(UploadError) as exc_info:
                upload_finding(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)
            assert expected_in_message in str(exc_info.value)


# =============================================================================
# Tests: upload_finding() - Network Error Handling
# =============================================================================


class TestUploadFindingNetworkErrors:
    """Tests for network error handling in upload_finding()."""

    def test_connection_refused_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of connection refused error."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError(
                "Connection refused"
            )

            with pytest.raises(UploadError) as exc_info:
                upload_finding(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)

    def test_timeout_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of timeout error."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

            with pytest.raises(UploadError) as exc_info:
                upload_finding(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)

    def test_dns_failure_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of DNS resolution failure."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError(
                "Failed to resolve 'api.skua.dev'"
            )

            with pytest.raises(UploadError) as exc_info:
                upload_finding(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)

    def test_ssl_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of SSL/TLS error."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.SSLError("SSL certificate error")

            with pytest.raises(UploadError) as exc_info:
                upload_finding(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)

    def test_generic_request_exception(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of generic RequestException."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.RequestException(
                "Something went wrong"
            )

            with pytest.raises(UploadError) as exc_info:
                upload_finding(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)


# =============================================================================
# Tests: upload_finding() - Edge Cases
# =============================================================================


class TestUploadFindingEdgeCases:
    """Tests for edge cases in upload_finding()."""

    def test_empty_title(
        self, mock_session_id, temp_session_dir
    ):
        """Test upload with empty title."""
        data = {
            "content": {
                "type": "text",
                "format": "text",
                "data": "content",
                "metadata": {},
            },
            "title": "",
            "tags": [],
        }

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_finding(data)

            assert result["id"] == "test"

    def test_empty_tags_list(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test upload with empty tags list."""
        sample_text_data["tags"] = []

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            assert form_data["tags"] == (None, "[]")

    def test_tags_always_empty(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that tags are always sent as empty list (not yet exposed)."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            parsed_tags = json.loads(form_data["tags"][1])
            assert parsed_tags == []

    def test_special_characters_in_title(
        self, mock_session_id, temp_session_dir
    ):
        """Test upload with special characters in title."""
        data = {
            "content": {
                "type": "text",
                "format": "text",
                "data": "content",
                "metadata": {},
            },
            "title": "Test <script>alert('xss')</script> & \"quotes\"",
            "tags": [],
        }

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            # Title should be passed as-is (server handles sanitization)
            assert "script" in form_data["title"][1]

    def test_unicode_in_content(
        self, mock_session_id, temp_session_dir
    ):
        """Test upload with unicode characters in content."""
        # Use valid Unicode characters (avoid surrogates like \ud83c\udf1f)
        # For emoji, use the full codepoint or the actual character
        data = {
            "content": {
                "type": "text",
                "format": "text",
                "data": "Hello \u4e16\u754c symbols \u00e9\u00e8\u00e0",
                "metadata": {},
            },
            "title": "Unicode Test",
            "tags": [],
        }

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_finding(data)

            call_kwargs = mock_post.call_args.kwargs
            files = call_kwargs["files"]
            filename, content = files["data"]
            # Content should be properly encoded
            assert b"\xe4\xb8\x96\xe7\x95\x8c" in content  # UTF-8 encoded Chinese chars


# =============================================================================
# Tests: request_verification()
# =============================================================================


class TestLogin:
    """Tests for login() function."""

    def test_returns_verification_url(self, mock_session_id, temp_session_dir):
        """Test that verification URL is returned."""
        with patch("skua.client.get_web_url", return_value="https://skua.dev"):
            with patch("webbrowser.open"):
                url = login()

        assert url == "https://skua.dev/verify"

    def test_opens_browser(self, mock_session_id, temp_session_dir):
        """Test that browser is opened with correct URL."""
        with patch("skua.client.get_web_url", return_value="https://skua.dev"):
            with patch("webbrowser.open") as mock_open:
                login()

        mock_open.assert_called_once_with("https://skua.dev/verify")

    def test_handles_browser_open_failure(self, mock_session_id, temp_session_dir):
        """Test that browser failure doesn't raise exception."""
        with patch("skua.client.get_web_url", return_value="https://skua.dev"):
            with patch("webbrowser.open") as mock_open:
                mock_open.side_effect = Exception("No browser found")
                url = login()

        assert "verify" in url

    def test_prints_helpful_messages(
        self, mock_session_id, temp_session_dir, capsys
    ):
        """Test that helpful messages are printed."""
        with patch("skua.client.get_web_url", return_value="https://skua.dev"):
            with patch("webbrowser.open"):
                login()

        captured = capsys.readouterr()
        assert "Opening browser" in captured.out
        assert "verify" in captured.out.lower()

    def test_backward_compat_alias(self):
        """Test that request_verification is an alias for login."""
        assert request_verification is login


class TestSetToken:
    """Tests for set_token() function."""

    def test_successful_activation(self, mock_session_id, temp_session_dir, tmp_path):
        """Test successful token activation persists token."""
        token_file = tmp_path / ".skua" / "token"

        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.ok = True
                mock_post.return_value.json.return_value = {
                    "success": True,
                    "email": "user@example.com",
                    "retention_days": 90,
                }
                mock_post.return_value.raise_for_status = MagicMock()

                with patch("pathlib.Path.home", return_value=tmp_path):
                    set_token("sk_test123")

        # Verify API call
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["token"] == "sk_test123"
        assert call_kwargs["headers"]["X-Skua-Token"] == "anon_test123456"

        # Verify token was persisted
        assert token_file.exists()
        assert token_file.read_text() == "sk_test123"

    def test_rejects_token_without_sk_prefix(self, mock_session_id, temp_session_dir):
        """Test that tokens without sk_ prefix are rejected."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="must start with"):
            set_token("bad_token_no_prefix")

    def test_rejects_empty_token(self, mock_session_id, temp_session_dir):
        """Test that empty token is rejected."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="must start with"):
            set_token("")

    def test_rejects_sk_prefix_only(self, mock_session_id, temp_session_dir):
        """Test that bare sk_ prefix without payload is rejected."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="too short"):
            set_token("sk_")

    def test_activation_failure_raises(self, mock_session_id, temp_session_dir):
        """Test that activation failure raises UploadError."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.post") as mock_post:
                response = MagicMock()
                response.status_code = 404
                response.ok = False
                response.json.return_value = {"detail": "Invalid token"}
                http_error = requests.exceptions.HTTPError("404", response=response)
                mock_post.return_value = response
                response.raise_for_status.side_effect = http_error

                with pytest.raises(UploadError, match="Token activation failed"):
                    set_token("sk_bad_token")

    def test_prints_success_message(self, mock_session_id, temp_session_dir, tmp_path, capsys):
        """Test that success message is printed."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.ok = True
                mock_post.return_value.json.return_value = {
                    "success": True,
                    "email": "test@example.com",
                    "retention_days": 90,
                }
                mock_post.return_value.raise_for_status = MagicMock()

                with patch("pathlib.Path.home", return_value=tmp_path):
                    set_token("sk_test")

        captured = capsys.readouterr()
        assert "test@example.com" in captured.out
        assert "90" in captured.out


# =============================================================================
# Tests: get_auth_status()
# =============================================================================


class TestGetAuthStatus:
    """Tests for get_auth_status() function."""

    def test_returns_auth_status(self, mock_session_id, temp_session_dir):
        """Test that authentication status is returned."""
        expected_response = {
            "authenticated": False,
            "email": None,
            "session_id": "anon_test123456",
            "retention_days": 7,
        }

        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = expected_response
                mock_get.return_value.raise_for_status = MagicMock()

                result = get_auth_status()

        assert result == expected_response

    def test_sends_correct_headers(self, mock_session_id, temp_session_dir):
        """Test that correct headers are sent."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {}
                mock_get.return_value.raise_for_status = MagicMock()

                get_auth_status()

        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["headers"]["X-Skua-Token"] == "anon_test123456"

    def test_uses_correct_endpoint(self, mock_session_id, temp_session_dir):
        """Test that correct API endpoint is used."""
        with patch("skua.client.get_api_url", return_value="https://api.test.com"):
            with patch("skua.client.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {}
                mock_get.return_value.raise_for_status = MagicMock()

                get_auth_status()

        call_url = mock_get.call_args.args[0]
        assert call_url == "https://api.test.com/api/auth/status"

    def test_handles_network_error(self, mock_session_id, temp_session_dir):
        """Test that network errors raise UploadError."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.get") as mock_get:
                mock_get.side_effect = requests.exceptions.ConnectionError(
                    "Connection refused"
                )

                with pytest.raises(UploadError) as exc_info:
                    get_auth_status()

        assert "Failed to get authentication status" in str(exc_info.value)

    def test_handles_http_error(self, mock_session_id, temp_session_dir):
        """Test that HTTP errors raise UploadError."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.get") as mock_get:
                response = MagicMock()
                response.status_code = 500
                http_error = requests.exceptions.HTTPError("500 Error", response=response)
                mock_get.return_value.raise_for_status.side_effect = http_error

                with pytest.raises(UploadError) as exc_info:
                    get_auth_status()

        assert "Failed to get authentication status" in str(exc_info.value)


# =============================================================================
# Tests: URL Construction
# =============================================================================


class TestUrlConstruction:
    """Tests for URL construction with different base URLs."""

    @pytest.mark.parametrize(
        "api_url,expected_endpoint",
        [
            ("https://api.skua.dev", "https://api.skua.dev/api/findings"),
            ("http://localhost:8000", "http://localhost:8000/api/findings"),
            ("https://api.staging.skua.dev", "https://api.staging.skua.dev/api/findings"),
            # Trailing slash should not cause double slashes
            # Note: Current implementation doesn't handle trailing slashes
        ],
    )
    def test_api_endpoint_construction(
        self,
        mock_session_id,
        sample_text_data,
        temp_session_dir,
        api_url,
        expected_endpoint,
    ):
        """Test that API endpoint is constructed correctly for different base URLs."""
        with patch("skua.client.get_api_url", return_value=api_url):
            with patch("skua.client.requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
                mock_post.return_value.raise_for_status = MagicMock()

                upload_finding(sample_text_data)

                call_url = mock_post.call_args.args[0]
                assert call_url == expected_endpoint


# =============================================================================
# Tests: Response Parsing
# =============================================================================


class TestResponseParsing:
    """Tests for API response parsing."""

    def test_extracts_id_from_response(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that finding ID is correctly extracted from response."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "id": "unique-finding-id-123",
                "url": "https://skua.dev/f/unique-finding-id-123",
                "extra_field": "ignored",
            }
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_finding(sample_text_data)

            assert result["id"] == "unique-finding-id-123"

    def test_handles_json_decode_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of invalid JSON response."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.side_effect = json.JSONDecodeError(
                "Invalid JSON", "", 0
            )
            mock_post.return_value.raise_for_status = MagicMock()

            with pytest.raises(json.JSONDecodeError):
                upload_finding(sample_text_data)

    def test_handles_missing_id_in_response(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of response without 'id' field."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"url": "https://skua.dev/f/x"}
            mock_post.return_value.raise_for_status = MagicMock()

            with pytest.raises(KeyError):
                upload_finding(sample_text_data)
