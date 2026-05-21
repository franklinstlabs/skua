"""Tests for the Skua HTTP client module.

Covers:
- upload_record() - main upload function
- get_client_token() - session management
(request_verification removed in 0.13 — use login() directly)
- get_auth_status() - authentication status check
- Error handling for network and HTTP errors
- Client-side validation (visibility, file size)
- URL construction and request formatting
"""

import base64
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, mock_open

import pytest
import requests

from skua.client import (
    _extract_error_detail,
    get_client_token,
    upload_record,
    login,
    set_token,
    get_auth_status,
)
from skua.exceptions import UploadError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_session_dir(tmp_path):
    """Provide a temporary directory for the on-disk client token file.

    Patches get_client_token_file() to use a temp directory and get_token()
    to return None, preventing tests from touching ~/.skua/. Yields the
    file path that the client code will read/write — historically named
    `session` but now actually `client` on disk.
    """
    client_file = tmp_path / "client"
    with patch("skua.client.get_client_token_file", return_value=client_file), \
         patch("skua.client.get_token", return_value=None):
        yield client_file


@pytest.fixture
def mock_session_id():
    """Patch the client-token getter to return a predictable value.

    Both names are patched so callers using either the new
    `get_client_token` or the back-compat `get_client_token` see the same
    value (the alias path forwards to get_client_token, but tests that
    patch only the alias would otherwise miss).
    """
    with patch("skua.client.get_client_token", return_value="anon_test123456"), \
         patch("skua.client.get_client_token", return_value="anon_test123456") as mock:
        yield mock


@pytest.fixture
def mock_verified_session_id():
    """Patch the client-token getter to return a verified value."""
    with patch("skua.client.get_client_token", return_value="verified_user_abc"), \
         patch("skua.client.get_client_token", return_value="verified_user_abc") as mock:
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
# Tests: _extract_error_detail()
# =============================================================================


class TestExtractErrorDetail:
    """Unit tests for the shared error-detail extractor."""

    def _mock_response(self, status_code: int, body: Any) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = body
        return resp

    def _mock_response_bad_json(self, status_code: int) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.side_effect = Exception("not json")
        return resp

    def test_skua_error_envelope(self):
        """{"error": {"message": "..."}} returns the message."""
        resp = self._mock_response(422, {
            "error": {
                "message": "Anonymous usage limit reached (10 records).",
                "code": "ValidationError",
                "details": {},
            }
        })
        assert _extract_error_detail(resp) == "Anonymous usage limit reached (10 records)."

    def test_fastapi_detail_list(self):
        """{"detail": [{...msg...}]} joins the msg fields."""
        resp = self._mock_response(422, {
            "detail": [
                {"loc": ["body", "title"], "msg": "field required", "type": "value_error"},
                {"loc": ["body", "data"], "msg": "none is not allowed", "type": "type_error"},
            ]
        })
        result = _extract_error_detail(resp)
        assert "field required" in result
        assert "none is not allowed" in result

    def test_fastapi_detail_string(self):
        """{"detail": "some string"} returns it directly."""
        resp = self._mock_response(403, {"detail": "Permission denied"})
        assert _extract_error_detail(resp) == "Permission denied"

    def test_malformed_json_falls_back_to_status(self):
        """Non-JSON body falls back to 'HTTP <status>'."""
        resp = self._mock_response_bad_json(500)
        assert _extract_error_detail(resp) == "HTTP 500"

    def test_empty_body_falls_back_to_status(self):
        """Empty dict body falls back to 'HTTP <status>'."""
        resp = self._mock_response(503, {})
        assert _extract_error_detail(resp) == "HTTP 503"

    def test_non_dict_body_falls_back_to_status(self):
        """Non-dict JSON body falls back to 'HTTP <status>'."""
        resp = self._mock_response(500, ["error", "list"])
        assert _extract_error_detail(resp) == "HTTP 500"

    def test_error_envelope_missing_message(self):
        """{"error": {"code": "..."}} without message falls back to status."""
        resp = self._mock_response(500, {"error": {"code": "SomeError"}})
        assert _extract_error_detail(resp) == "HTTP 500"

    def test_detail_list_no_msg_fields(self):
        """detail list with no msg fields falls back to status."""
        resp = self._mock_response(422, {"detail": [{"loc": ["x"]}]})
        assert _extract_error_detail(resp) == "HTTP 422"

    def test_rate_limit_shape(self):
        """Rate-limit shape {"error": "Rate limit exceeded", "detail": "..."} — detail string wins."""
        resp = self._mock_response(429, {
            "error": "Rate limit exceeded",
            "detail": "5 per 1 minute",
        })
        # "error" is a plain string not a dict, so falls through to "detail"
        assert _extract_error_detail(resp) == "5 per 1 minute"


# =============================================================================
# Tests: get_client_token()
# =============================================================================


class TestGetSessionId:
    """Tests for session ID retrieval and generation."""

    def test_creates_new_session_when_file_missing(self, temp_session_dir):
        """Test that a new session ID is created when file doesn't exist."""
        session_id = get_client_token()

        assert session_id.startswith("anon_")
        assert len(session_id) == 21  # "anon_" + 16 hex chars
        assert temp_session_dir.exists()
        assert temp_session_dir.read_text() == session_id

    def test_reads_existing_session(self, temp_session_dir):
        """Test that existing session ID is read from file."""
        existing_id = "anon_existingsession"
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text(existing_id)

        session_id = get_client_token()

        assert session_id == existing_id

    def test_creates_new_session_when_file_empty(self, temp_session_dir):
        """Test that a new session ID is created when file is empty."""
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text("")

        session_id = get_client_token()

        assert session_id.startswith("anon_")
        assert len(session_id) == 21

    def test_creates_new_session_when_file_whitespace(self, temp_session_dir):
        """Test that a new session ID is created when file is whitespace only."""
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text("   \n\t  ")

        session_id = get_client_token()

        assert session_id.startswith("anon_")
        assert len(session_id) == 21

    def test_creates_parent_directories(self, tmp_path):
        """Test that parent directories are created if missing."""
        nested_path = tmp_path / "deep" / "nested" / "client"
        with patch("skua.client.get_client_token_file", return_value=nested_path), \
             patch("skua.client.get_token", return_value=None):
            session_id = get_client_token()

        assert nested_path.parent.exists()
        assert nested_path.exists()
        assert session_id.startswith("anon_")

    def test_session_id_format_is_hex(self, temp_session_dir):
        """Test that generated session ID uses hex characters."""
        session_id = get_client_token()

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
            session_id = get_client_token()

        assert session_id == "my-api-token"

    def test_no_token_falls_back_to_file(self, temp_session_dir):
        """Test that None token falls back to file-based session."""
        temp_session_dir.parent.mkdir(parents=True, exist_ok=True)
        temp_session_dir.write_text("anon_from_file")

        with patch("skua.client.get_token", return_value=None):
            session_id = get_client_token()

        assert session_id == "anon_from_file"


# =============================================================================
# Tests: upload_record() - Successful Uploads
# =============================================================================


class TestUploadRecordSuccess:
    """Tests for successful upload_record() calls."""

    def test_successful_image_upload(
        self, mock_session_id, sample_image_data, temp_session_dir
    ):
        """Test successful upload of image data."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "abc123", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_image_data)

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

            result = upload_record(sample_json_data)

            assert result["id"] == "def456"

    def test_successful_text_upload(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test successful upload of text data."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "ghi789", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_text_data)

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

            result = upload_record(sample_text_data)

            assert result["id"] == "desc123"
            call_kwargs = mock_post.call_args.kwargs
            assert "description" in call_kwargs["data"]

    def test_warns_on_type_change(
        self, mock_session_id, sample_text_data, temp_session_dir, capsys
    ):
        """When the backend reports the prior snap was a different type, print a warning to stderr."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "id": "changed1",
                "visibility": "public",
                "creator_username": None,
                "type_changed_from": "pandas.dataframe",
            }
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_text_data)

        assert result["id"] == "changed1"
        captured = capsys.readouterr()
        assert "pandas.dataframe" in captured.err
        assert sample_text_data["content"]["type"] in captured.err

    def test_no_warning_when_type_unchanged(
        self, mock_session_id, sample_text_data, temp_session_dir, capsys
    ):
        """No warning when type_changed_from is null/missing in the response."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "id": "same1",
                "visibility": "public",
                "creator_username": None,
                "type_changed_from": None,
            }
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

        captured = capsys.readouterr()
        assert captured.err == ""


# =============================================================================
# Tests: upload_record() - Request Formatting
# =============================================================================


class TestUploadRecordRequestFormat:
    """Tests for correct request formatting in upload_record()."""

    def test_sends_correct_headers(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that correct headers are sent with request."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

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

            upload_record(sample_text_data)

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

            upload_record(sample_text_data)

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

            upload_record(sample_json_data)

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

            upload_record(sample_image_data)

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

                upload_record(sample_text_data)

                call_url = mock_post.call_args.args[0]
                assert call_url == "https://api.test.com/records"

    def test_sends_preview_png_sidecar_when_present(
        self, mock_session_id, temp_session_dir
    ):
        # When the serializer produced a preview_png_b64 (plotly with kaleido),
        # the uploader adds a second multipart file `preview_png` so the
        # backend can stash it for OpenGraph rendering.
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"fake-png-data"
        plotly_data = {
            "content": {
                "type": "plotly.figure",
                "format": "json",
                "data": '{"data":[]}',
                "metadata": {},
                "preview_png_b64": base64.b64encode(png_bytes).decode("utf-8"),
            },
            "title": "Plotly with preview",
            "tags": [],
        }
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(plotly_data)

            files = mock_post.call_args.kwargs["files"]
            assert "preview_png" in files
            filename, content, content_type = files["preview_png"]
            assert filename == "preview.png"
            assert content == png_bytes
            assert content_type == "image/png"

    def test_omits_preview_png_sidecar_when_absent(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        # Serializers that don't produce a preview (everything except plotly,
        # or plotly without kaleido) must not add the sidecar file at all —
        # the backend endpoint treats it as optional.
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

            files = mock_post.call_args.kwargs["files"]
            assert "preview_png" not in files

    def test_request_timeout_is_set(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that request timeout is properly set."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["timeout"] == 30

    def test_visibility_included_when_set(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Visibility is included in form data when provided — anon or verified."""
        sample_text_data["visibility"] = "private"

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "private", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            assert "visibility" in form_data
            assert form_data["visibility"] == (None, "private")

    def test_anon_can_upload_private(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Client no longer rejects anon + private — backend handles cookie-gating."""
        sample_text_data["visibility"] = "private"

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "private", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_text_data)

        assert mock_post.call_count == 1
        assert result["visibility"] == "private"

    def test_anon_can_upload_unlisted(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Client no longer rejects anon + unlisted — backend handles cookie-gating."""
        sample_text_data["visibility"] = "unlisted"

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "unlisted", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_text_data)

        assert mock_post.call_count == 1
        assert result["visibility"] == "unlisted"

    def test_upload_sends_collection_name_in_form(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """upload_record sends collection_name to the backend, not session_name."""
        sample_text_data["collection_name"] = "Q3 Review"

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "id": "abc123",
                "creator_username": "testbird-42",
                "visibility": "public",
                "collection_id": "coll1",
                "collection_name": "Q3 Review",
                "collection_url": "http://localhost:5173/u/testbird-42/c/q3-review",
            }
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            assert "collection_name" in form_data
            assert form_data["collection_name"] == (None, "Q3 Review")
            assert "session_name" not in form_data

        assert result["id"] == "abc123"
        assert result["collection_name"] == "Q3 Review"
        assert result["collection_id"] == "coll1"
        assert result["collection_url"] == "http://localhost:5173/u/testbird-42/c/q3-review"

    def test_upload_omits_collection_name_when_not_in_data(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """When the data dict has no collection_name, the form body must not contain it."""
        # sample_text_data has no collection_name key
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "abc123", "creator_username": None, "visibility": "public"}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            assert "collection_name" not in form_data
            assert "session_name" not in form_data

    def test_upload_returns_collection_fields_from_response(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """upload_record surfaces collection_id, collection_name, collection_url."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "id": "xyz789",
                "creator_username": "alice",
                "visibility": "public",
                "collection_id": "collA",
                "collection_name": "My Notebook",
                "collection_url": "http://localhost:5173/u/alice/c/my-notebook",
            }
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_text_data)

        assert result["collection_id"] == "collA"
        assert result["collection_name"] == "My Notebook"
        assert result["collection_url"] == "http://localhost:5173/u/alice/c/my-notebook"

    def test_upload_returns_none_collection_fields_when_absent(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """When server doesn't return collection fields, they are None in result."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {
                "id": "xyz789",
                "creator_username": None,
                "visibility": "public",
            }
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_text_data)

        assert result["collection_id"] is None
        assert result["collection_name"] is None
        assert result["collection_url"] is None

    def test_unlisted_allowed_for_any_session(
        self, mock_verified_session_id, sample_text_data, temp_session_dir
    ):
        """Verified session + visibility=unlisted passes through to the server."""
        sample_text_data["visibility"] = "unlisted"

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "unlisted", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

            assert mock_post.call_count == 1

    def test_visibility_excluded_when_none(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that visibility is not sent when None (server decides)."""
        sample_text_data["visibility"] = None

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 201
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            assert "visibility" not in form_data


# =============================================================================
# Tests: upload_record() - File Size Validation
# =============================================================================


class TestUploadRecordFileSizeValidation:
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

            result = upload_record(sample_text_data)

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
                upload_record(large_data)

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

            result = upload_record(exact_data)

            assert result["id"] == "test"
            mock_post.assert_called_once()


# =============================================================================
# Tests: upload_record() - HTTP Error Handling
# =============================================================================


class TestUploadRecordHttpErrors:
    """Tests for HTTP error handling in upload_record()."""

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
                upload_record(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)
            assert expected_in_message in str(exc_info.value)


# =============================================================================
# Tests: upload_record() - Network Error Handling
# =============================================================================


class TestUploadRecordNetworkErrors:
    """Tests for network error handling in upload_record()."""

    def test_connection_refused_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of connection refused error."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.ConnectionError(
                "Connection refused"
            )

            with pytest.raises(UploadError) as exc_info:
                upload_record(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)

    def test_timeout_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of timeout error."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

            with pytest.raises(UploadError) as exc_info:
                upload_record(sample_text_data)

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
                upload_record(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)

    def test_ssl_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of SSL/TLS error."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.side_effect = requests.exceptions.SSLError("SSL certificate error")

            with pytest.raises(UploadError) as exc_info:
                upload_record(sample_text_data)

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
                upload_record(sample_text_data)

            assert "Failed to upload" in str(exc_info.value)


# =============================================================================
# Tests: upload_record() - Edge Cases
# =============================================================================


class TestUploadRecordEdgeCases:
    """Tests for edge cases in upload_record()."""

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

            result = upload_record(data)

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

            upload_record(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            assert form_data["tags"] == (None, "[]")

    def test_tags_passed_through_to_form_data(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test that tags from data dict are sent as JSON in form data."""
        sample_text_data["tags"] = ["ml", "analysis"]

        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"id": "test", "visibility": "public", "creator_username": None}
            mock_post.return_value.raise_for_status = MagicMock()

            upload_record(sample_text_data)

            call_kwargs = mock_post.call_args.kwargs
            form_data = call_kwargs["data"]
            parsed_tags = json.loads(form_data["tags"][1])
            assert parsed_tags == ["ml", "analysis"]

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

            upload_record(data)

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

            upload_record(data)

            call_kwargs = mock_post.call_args.kwargs
            files = call_kwargs["files"]
            filename, content = files["data"]
            # Content should be properly encoded
            assert b"\xe4\xb8\x96\xe7\x95\x8c" in content  # UTF-8 encoded Chinese chars


# =============================================================================
# (request_verification was a back-compat alias for login(); removed in 0.13)
# =============================================================================


class TestLogin:
    """Tests for login() function (browser-based flow)."""

    def test_opens_verify_url_in_browser_with_session(self, mock_session_id, temp_session_dir, tmp_path):
        """login() opens {web_url}/verify?client=<token> in the browser when not already verified."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"), \
             patch("skua.client.get_web_url", return_value="https://skua.dev"), \
             patch("webbrowser.open") as mock_open, \
             patch("skua.client.requests.get") as mock_get, \
             patch("time.sleep"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            mock_get.return_value.ok = True
            # First call is the fast-path pre-check (unauthenticated → fall through),
            # then polling picks up the verification.
            mock_get.return_value.json.side_effect = [
                {"authenticated": False},
                {
                    "authenticated": True,
                    "email": "user@example.com",
                    "retention_days": 90,
                },
            ]
            login(timeout=5)

        mock_open.assert_called_once()
        opened_url = mock_open.call_args.args[0]
        assert opened_url.startswith("https://skua.dev/verify?client=")
        assert "anon_test123456" in opened_url

    def test_fast_path_skips_browser_if_already_verified(
        self, mock_session_id, temp_session_dir, tmp_path, capsys
    ):
        """If session is already verified (late-click recovery), skip browser + polling."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"), \
             patch("skua.client.get_web_url", return_value="https://skua.dev"), \
             patch("webbrowser.open") as mock_open, \
             patch("skua.client.requests.get") as mock_get, \
             patch("time.sleep") as mock_sleep, \
             patch("pathlib.Path.home", return_value=tmp_path):
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = {
                "authenticated": True,
                "email": "user@example.com",
                "retention_days": 90,
            }
            login(timeout=5)

        mock_open.assert_not_called()
        mock_sleep.assert_not_called()
        # Token persisted to the canonical client file (was ~/.skua/token
        # historically; now ~/.skua/client — see get_client_token()).
        assert temp_session_dir.read_text() == "anon_test123456"
        assert "Verified as user@example.com" in capsys.readouterr().out

    def test_polls_until_authenticated(self, mock_session_id, temp_session_dir, tmp_path):
        """login() polls /auth/status until authenticated."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"), \
             patch("skua.client.get_web_url", return_value="https://skua.dev"), \
             patch("webbrowser.open"), \
             patch("skua.client.requests.get") as mock_get, \
             patch("time.sleep"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            mock_get.return_value.ok = True
            mock_get.return_value.json.side_effect = [
                {"authenticated": False},
                {"authenticated": False},
                {"authenticated": True, "email": "user@example.com", "retention_days": 90},
            ]
            login(timeout=30)

        assert mock_get.call_count == 3

    def test_persists_token_on_success(self, mock_session_id, temp_session_dir, tmp_path):
        """On successful verification, the client token is persisted to ~/.skua/client."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"), \
             patch("skua.client.get_web_url", return_value="https://skua.dev"), \
             patch("webbrowser.open"), \
             patch("skua.client.requests.get") as mock_get, \
             patch("time.sleep"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = {
                "authenticated": True,
                "email": "user@example.com",
                "retention_days": 90,
            }
            login(timeout=5)

        assert temp_session_dir.exists()
        assert temp_session_dir.read_text() == "anon_test123456"

    def test_timeout_prints_paste_instructions(self, mock_session_id, temp_session_dir, tmp_path, capsys):
        """If polling times out, login() tells the user they can still paste skua.token()."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"), \
             patch("skua.client.get_web_url", return_value="https://skua.dev"), \
             patch("webbrowser.open"), \
             patch("skua.client.requests.get") as mock_get, \
             patch("time.sleep"), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("time.time", side_effect=[0, 1000, 2000]):
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = {"authenticated": False}
            login(timeout=5)

        captured = capsys.readouterr()
        assert "Timed out" in captured.out
        assert "skua.token" in captured.out

    def test_browser_open_failure_does_not_crash(self, mock_session_id, temp_session_dir, tmp_path):
        """If webbrowser.open() raises, login still proceeds to polling."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"), \
             patch("skua.client.get_web_url", return_value="https://skua.dev"), \
             patch("webbrowser.open", side_effect=RuntimeError("no display")), \
             patch("skua.client.requests.get") as mock_get, \
             patch("time.sleep"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            mock_get.return_value.ok = True
            mock_get.return_value.json.return_value = {
                "authenticated": True,
                "email": "user@example.com",
                "retention_days": 90,
            }
            login(timeout=5)  # should not raise


class TestSetToken:
    """Tests for set_token() function."""

    def test_successful_activation(self, mock_session_id, temp_session_dir, tmp_path):
        """Test successful token activation persists token to client file."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"), \
             patch("skua.client.get_web_url", return_value="https://skua.dev"):
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

        # Token is now persisted to the canonical client file (was
        # ~/.skua/token historically; now the same file we read from).
        assert temp_session_dir.exists()
        assert temp_session_dir.read_text() == "sk_test123"

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

    def test_activation_failure_raises_with_detail(self, mock_session_id, temp_session_dir):
        """HTTP error with FastAPI detail string surfaces the message."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.post") as mock_post:
                response = MagicMock()
                response.status_code = 404
                response.ok = False
                response.json.return_value = {"detail": "Invalid token"}
                http_error = requests.exceptions.HTTPError("404", response=response)
                mock_post.return_value = response
                response.raise_for_status.side_effect = http_error

                with pytest.raises(UploadError, match="Invalid token"):
                    set_token("sk_bad_token")

    def test_activation_failure_raises_with_error_envelope(self, mock_session_id, temp_session_dir):
        """HTTP error with SkuaError envelope surfaces the message."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.post") as mock_post:
                response = MagicMock()
                response.status_code = 422
                response.ok = False
                response.json.return_value = {
                    "error": {"message": "Token already used", "code": "ValidationError", "details": {}}
                }
                http_error = requests.exceptions.HTTPError("422", response=response)
                mock_post.return_value = response
                response.raise_for_status.side_effect = http_error

                with pytest.raises(UploadError, match="Token already used"):
                    set_token("sk_used_token")

    def test_activation_network_error_raises(self, mock_session_id, temp_session_dir):
        """Network error (no response body) raises UploadError with message."""
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.post") as mock_post:
                mock_post.side_effect = requests.exceptions.ConnectionError("No route to host")

                with pytest.raises(UploadError, match="Token activation failed"):
                    set_token("sk_test_net")

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
        """Test that authentication status returns the redesigned payload."""
        backend_response = {
            "verified": False,
            "authenticated": False,
            "email": None,
            "username": "brave-otter-42",
            "retention_days": 90,
        }

        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = backend_response
                mock_get.return_value.raise_for_status = MagicMock()

                result = get_auth_status()

        # Public SDK shape — no internal ids
        assert "session_id" not in result
        assert "client_id" not in result
        assert "user_id" not in result
        assert "authenticated" not in result
        # session_name / session_default_visibility were removed in the
        # collection API upgrade — session.py is no longer referenced here
        assert "session_name" not in result
        assert "session_default_visibility" not in result
        # Positive assertions on the redesigned shape
        assert result["verified"] is False
        assert result["email"] is None
        assert result["username"] == "brave-otter-42"
        assert result["retention_days"] == 90

    def test_verified_shape(self, mock_session_id, temp_session_dir):
        """Verified flag flows through correctly when backend reports verified."""
        backend_response = {
            "verified": True,
            "authenticated": True,
            "email": "alice@example.com",
            "username": "alice",
            "retention_days": 365,
        }

        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = backend_response
                mock_get.return_value.raise_for_status = MagicMock()

                result = get_auth_status()

        assert result["verified"] is True
        assert result["username"] == "alice"
        assert result["email"] == "alice@example.com"

    def test_legacy_backend_falls_back_to_authenticated(self, mock_session_id, temp_session_dir):
        """If the backend is old and only returns `authenticated`, SDK still exposes `verified`."""
        backend_response = {
            "authenticated": True,
            "email": "bob@example.com",
            "username": "bob",
            "retention_days": 365,
        }

        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = backend_response
                mock_get.return_value.raise_for_status = MagicMock()

                result = get_auth_status()

        assert result["verified"] is True

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
        assert call_url == "https://api.test.com/auth/status"

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

    def test_works_without_init(self, mock_session_id, temp_session_dir):
        """status() is a read-only check and must work before (no setup needed).

        get_auth_status() no longer imports from skua.session, so there's
        no ConfigurationError risk from calling status() on a fresh kernel.
        """
        with patch("skua.client.get_api_url", return_value="https://api.skua.dev"):
            with patch("skua.client.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "verified": False,
                    "authenticated": False,
                    "email": None,
                    "username": "brave-otter-42",
                    "retention_days": 90,
                }
                mock_get.return_value.raise_for_status = MagicMock()

                result = get_auth_status()

        assert result["verified"] is False
        assert result["username"] == "brave-otter-42"
        assert "session_name" not in result
        assert "session_default_visibility" not in result


# =============================================================================
# Tests: URL Construction
# =============================================================================


class TestUrlConstruction:
    """Tests for URL construction with different base URLs."""

    @pytest.mark.parametrize(
        "api_url,expected_endpoint",
        [
            ("https://api.skua.dev", "https://api.skua.dev/records"),
            ("http://localhost:8000", "http://localhost:8000/records"),
            ("https://api.staging.skua.dev", "https://api.staging.skua.dev/records"),
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

                upload_record(sample_text_data)

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
        """Test that record ID is correctly extracted from response."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "id": "unique-record-id-123",
                "url": "https://skua.dev/f/unique-record-id-123",
                "extra_field": "ignored",
            }
            mock_post.return_value.raise_for_status = MagicMock()

            result = upload_record(sample_text_data)

            assert result["id"] == "unique-record-id-123"

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
                upload_record(sample_text_data)

    def test_handles_missing_id_in_response(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Test handling of response without 'id' field."""
        with patch("skua.client.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"url": "https://skua.dev/f/x"}
            mock_post.return_value.raise_for_status = MagicMock()

            with pytest.raises(KeyError):
                upload_record(sample_text_data)

    def test_extracts_message_from_error_envelope(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """Backend wraps SkuaError in {"error": {"message": ...}}; the SDK should surface the message."""
        import requests as _requests
        with patch("skua.client.requests.post") as mock_post:
            err_response = MagicMock()
            err_response.status_code = 422
            err_response.json.return_value = {
                "error": {
                    "message": "Anonymous usage limit reached (10 records). Verify your email to upload more.",
                    "code": "ValidationError",
                    "details": {},
                }
            }
            err = _requests.exceptions.HTTPError(response=err_response)
            mock_post.return_value.raise_for_status.side_effect = err
            mock_post.return_value = mock_post.return_value

            with pytest.raises(UploadError, match="Anonymous usage limit reached"):
                upload_record(sample_text_data)

    def test_extracts_detail_from_fastapi_validation_error(
        self, mock_session_id, sample_text_data, temp_session_dir
    ):
        """FastAPI's auto-422 has shape {"detail": [...]}; the SDK should still surface it."""
        import requests as _requests
        with patch("skua.client.requests.post") as mock_post:
            err_response = MagicMock()
            err_response.status_code = 422
            err_response.json.return_value = {
                "detail": [{"loc": ["body", "title"], "msg": "field required", "type": "value_error"}]
            }
            err = _requests.exceptions.HTTPError(response=err_response)
            mock_post.return_value.raise_for_status.side_effect = err

            # The detail is a list; the SDK passes it through to the error message.
            with pytest.raises(UploadError, match="field required"):
                upload_record(sample_text_data)
