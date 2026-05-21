"""Tests for the Skua CLI.

Covers:
- skua record: file upload, stdin, auto-detection, --json output
- skua status: auth status display
- skua login: browser open
- skua verify: token activation
- skua list: record listing
- skua open: browser open for record
- Exit codes: 0 success, 1 auth, 2 validation, 3 server, 4 rate limited
- File type auto-detection from extension
"""

import base64
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from skua.cli import (
    EXIT_AUTH,
    EXIT_OK,
    EXIT_RATE_LIMITED,
    EXIT_SERVER,
    EXIT_VALIDATION,
    _build_content,
    _detect_type,
    main,
)
from skua.exceptions import UploadError, ValidationError


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_upload():
    """Mock upload_record to return a successful response."""
    with patch("skua.cli.upload_record") as mock:
        mock.return_value = {
            "id": "abc123",
            "creator_username": "test-user",
            "visibility": "public",
        }
        yield mock


@pytest.fixture
def mock_upload_private():
    """Mock upload_record returning private visibility."""
    with patch("skua.cli.upload_record") as mock:
        mock.return_value = {
            "id": "abc123",
            "creator_username": "test-user",
            "visibility": "private",
        }
        yield mock


@pytest.fixture
def png_file(tmp_path):
    """Create a tiny PNG file for testing."""
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
        "DUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    path = tmp_path / "chart.png"
    path.write_bytes(png_bytes)
    return path


@pytest.fixture
def csv_file(tmp_path):
    """Create a CSV file for testing."""
    path = tmp_path / "data.csv"
    path.write_text("name,value\nalice,10\nbob,20\n")
    return path


@pytest.fixture
def json_file(tmp_path):
    """Create a JSON file for testing."""
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"key": "value", "count": 42}))
    return path


@pytest.fixture
def plotly_json_file(tmp_path):
    """Create a Plotly JSON file for testing."""
    plotly_data = {
        "data": [{"x": [1, 2, 3], "y": [4, 5, 6], "type": "scatter"}],
        "layout": {"title": "Test"},
    }
    path = tmp_path / "plot.json"
    path.write_text(json.dumps(plotly_data))
    return path


@pytest.fixture
def text_file(tmp_path):
    """Create a text file for testing."""
    path = tmp_path / "notes.txt"
    path.write_text("Hello, world!")
    return path


# =============================================================================
# Type detection
# =============================================================================


class TestDetectType:
    def test_png(self):
        assert _detect_type("chart.png") == "png"

    def test_jpg(self):
        assert _detect_type("photo.jpg") == "jpg"

    def test_jpeg(self):
        assert _detect_type("photo.jpeg") == "jpg"

    def test_csv(self):
        assert _detect_type("data.csv") == "csv"

    def test_json(self):
        assert _detect_type("config.json") == "json"

    def test_txt(self):
        assert _detect_type("notes.txt") == "text"

    def test_unknown(self):
        assert _detect_type("data.parquet") is None

    def test_case_insensitive(self):
        assert _detect_type("CHART.PNG") == "png"


# =============================================================================
# Build content
# =============================================================================


class TestBuildContent:
    def test_png_content(self):
        raw = b"\x89PNG\r\n\x1a\nfake"
        result = _build_content(raw, "png")
        assert result["type"] == "pil.image"
        assert result["format"] == "png"
        assert result["data"] == base64.b64encode(raw).decode("utf-8")

    def test_jpg_content(self):
        raw = b"\xff\xd8\xff\xe0fake"
        result = _build_content(raw, "jpg")
        assert result["type"] == "pil.image"
        assert result["format"] == "jpg"

    def test_csv_content(self):
        raw = b"name,value\nalice,10\nbob,20\n"
        result = _build_content(raw, "csv")
        assert result["type"] == "pandas.dataframe"
        assert result["format"] == "json"
        parsed = json.loads(result["data"])
        assert parsed["columns"] == ["name", "value"]
        assert len(parsed["data"]) == 2

    def test_csv_numeric_conversion(self):
        raw = b"x,y\n1,2.5\n3,4.0\n"
        result = _build_content(raw, "csv")
        parsed = json.loads(result["data"])
        assert parsed["data"][0] == [1, 2.5]
        assert parsed["data"][1] == [3, 4.0]

    def test_json_dict(self):
        data = {"key": "value"}
        raw = json.dumps(data).encode()
        result = _build_content(raw, "json")
        assert result["type"] == "dict"
        assert result["format"] == "json"

    def test_json_plotly(self):
        data = {"data": [{"x": [1], "type": "scatter"}], "layout": {}}
        raw = json.dumps(data).encode()
        result = _build_content(raw, "json")
        assert result["type"] == "plotly.figure"
        assert result["format"] == "json"

    def test_text_content(self):
        raw = b"Hello, world!"
        result = _build_content(raw, "text")
        assert result["type"] == "text"
        assert result["format"] == "plain"
        assert result["data"] == "Hello, world!"


# =============================================================================
# snap command
# =============================================================================


class TestRecordCommand:
    def test_record_png(self, runner, png_file, mock_upload):
        result = runner.invoke(main, ["record", str(png_file), "--title", "My Chart"])
        assert result.exit_code == EXIT_OK
        assert "abc123" in result.output
        assert "\u2713" in result.output
        mock_upload.assert_called_once()

    def test_record_csv(self, runner, csv_file, mock_upload):
        result = runner.invoke(main, ["record", str(csv_file), "--title", "Data"])
        assert result.exit_code == EXIT_OK
        assert "abc123" in result.output
        call_data = mock_upload.call_args[0][0]
        assert call_data["content"]["type"] == "pandas.dataframe"

    def test_record_json(self, runner, json_file, mock_upload):
        result = runner.invoke(main, ["record", str(json_file), "--title", "Config"])
        assert result.exit_code == EXIT_OK
        call_data = mock_upload.call_args[0][0]
        assert call_data["content"]["type"] == "dict"

    def test_record_plotly_json(self, runner, plotly_json_file, mock_upload):
        result = runner.invoke(main, ["record", str(plotly_json_file), "--title", "Plot"])
        assert result.exit_code == EXIT_OK
        call_data = mock_upload.call_args[0][0]
        assert call_data["content"]["type"] == "plotly.figure"

    def test_record_text(self, runner, text_file, mock_upload):
        result = runner.invoke(main, ["record", str(text_file), "--title", "Notes"])
        assert result.exit_code == EXIT_OK
        call_data = mock_upload.call_args[0][0]
        assert call_data["content"]["type"] == "text"

    def test_record_json_output(self, runner, png_file, mock_upload):
        result = runner.invoke(main, [
            "record", str(png_file), "--title", "Chart", "--json"
        ])
        assert result.exit_code == EXIT_OK
        parsed = json.loads(result.output)
        assert parsed["url"] == "https://skua.dev/r/abc123"
        assert parsed["id"] == "abc123"
        assert parsed["visibility"] == "public"

    def test_record_public_flag(self, runner, png_file, mock_upload):
        result = runner.invoke(main, [
            "record", str(png_file), "--title", "Chart", "--public"
        ])
        assert result.exit_code == EXIT_OK
        call_data = mock_upload.call_args[0][0]
        assert call_data["visibility"] == "public"

    def test_record_description(self, runner, png_file, mock_upload):
        result = runner.invoke(main, [
            "record", str(png_file), "--title", "Chart",
            "--description", "Q3 revenue chart"
        ])
        assert result.exit_code == EXIT_OK
        call_data = mock_upload.call_args[0][0]
        assert call_data["description"] == "Q3 revenue chart"

    def test_record_stdin_requires_type(self, runner):
        result = runner.invoke(main, ["record", "-", "--title", "X"], input=b"data")
        assert result.exit_code == EXIT_VALIDATION

    def test_record_stdin_with_type(self, runner, mock_upload):
        result = runner.invoke(
            main,
            ["record", "-", "--title", "Piped", "--type", "text"],
            input="hello from stdin",
        )
        assert result.exit_code == EXIT_OK
        call_data = mock_upload.call_args[0][0]
        assert call_data["content"]["type"] == "text"

    def test_record_file_not_found(self, runner):
        result = runner.invoke(main, [
            "record", "/nonexistent/file.png", "--title", "X"
        ])
        assert result.exit_code == EXIT_VALIDATION

    def test_record_unknown_extension(self, runner, tmp_path):
        path = tmp_path / "data.parquet"
        path.write_bytes(b"fake")
        result = runner.invoke(main, ["record", str(path), "--title", "X"])
        assert result.exit_code == EXIT_VALIDATION

    def test_record_unknown_extension_with_type(self, runner, tmp_path, mock_upload):
        path = tmp_path / "data.parquet"
        path.write_bytes(b"fake text content")
        result = runner.invoke(main, [
            "record", str(path), "--title", "X", "--type", "text"
        ])
        assert result.exit_code == EXIT_OK

    def test_record_visibility_in_output(self, runner, png_file, mock_upload):
        result = runner.invoke(main, [
            "record", str(png_file), "--title", "Chart"
        ])
        assert "(public)" in result.output


# =============================================================================
# snap error handling
# =============================================================================


class TestRecordErrors:
    def test_upload_error_server(self, runner, png_file):
        with patch("skua.cli.upload_record", side_effect=UploadError("500 Server Error")):
            result = runner.invoke(main, [
                "record", str(png_file), "--title", "X"
            ])
            assert result.exit_code == EXIT_SERVER

    def test_upload_error_auth(self, runner, png_file):
        with patch("skua.cli.upload_record", side_effect=UploadError("401 Unauthorized")):
            result = runner.invoke(main, [
                "record", str(png_file), "--title", "X"
            ])
            assert result.exit_code == EXIT_AUTH

    def test_upload_error_rate_limited(self, runner, png_file):
        with patch("skua.cli.upload_record", side_effect=UploadError("429 rate limited")):
            result = runner.invoke(main, [
                "record", str(png_file), "--title", "X"
            ])
            assert result.exit_code == EXIT_RATE_LIMITED

    def test_upload_error_json_output(self, runner, png_file):
        with patch("skua.cli.upload_record", side_effect=UploadError("500 Error")):
            result = runner.invoke(main, [
                "record", str(png_file), "--title", "X", "--json"
            ])
            assert result.exit_code == EXIT_SERVER
            parsed = json.loads(result.output)
            assert "error" in parsed


# =============================================================================
# status command
# =============================================================================


class TestStatusCommand:
    def test_status_authenticated(self, runner):
        with patch("skua.cli.get_auth_status", return_value={
            "verified": True,
            "email": "user@example.com",
            "username": "alice",
            "retention_days": 365,
        }):
            result = runner.invoke(main, ["status"])
            assert result.exit_code == EXIT_OK
            assert "user@example.com" in result.output
            assert "alice" in result.output
            assert "365" in result.output

    def test_status_anonymous(self, runner):
        with patch("skua.cli.get_auth_status", return_value={
            "verified": False,
            "email": None,
            "username": "brave-otter-42",
            "retention_days": 90,
        }):
            result = runner.invoke(main, ["status"])
            assert result.exit_code == EXIT_OK
            assert "Anonymous" in result.output
            assert "brave-otter-42" in result.output
            assert "skua login" in result.output

    def test_status_server_error(self, runner):
        with patch("skua.cli.get_auth_status", side_effect=UploadError("Connection refused")):
            result = runner.invoke(main, ["status"])
            assert result.exit_code == EXIT_SERVER


# =============================================================================
# login command
# =============================================================================


class TestLoginCommand:
    def test_login(self, runner):
        with patch("skua.cli.login") as mock_login:
            mock_login.return_value = "https://skua.dev/verify"
            result = runner.invoke(main, ["login"])
            assert result.exit_code == EXIT_OK
            mock_login.assert_called_once()


# =============================================================================
# verify command
# =============================================================================


class TestVerifyCommand:
    def test_verify_success(self, runner):
        with patch("skua.cli.set_token") as mock_set:
            result = runner.invoke(main, ["verify", "sk_abc123"])
            assert result.exit_code == EXIT_OK
            mock_set.assert_called_once_with("sk_abc123")

    def test_verify_invalid_token(self, runner):
        with patch("skua.cli.set_token", side_effect=ValidationError("Invalid token format")):
            result = runner.invoke(main, ["verify", "bad_token"])
            assert result.exit_code == EXIT_VALIDATION

    def test_verify_activation_failure(self, runner):
        with patch("skua.cli.set_token", side_effect=UploadError("Activation failed")):
            result = runner.invoke(main, ["verify", "sk_abc123"])
            assert result.exit_code == EXIT_AUTH


# =============================================================================
# list command
# =============================================================================


class TestListCommand:
    def test_list_with_items(self, runner):
        items = [
            {"id": "abc123", "title": "Chart 1", "visibility": "public"},
            {"id": "def456", "title": "Data 2", "visibility": "private"},
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = items
        mock_resp.raise_for_status.return_value = None

        with patch("skua.cli.requests.get", return_value=mock_resp), \
             patch("skua.cli.get_client_token", return_value="anon_test"), \
             patch("skua.cli.get_api_url", return_value="https://api.skua.dev"):
            result = runner.invoke(main, ["list"])
            assert result.exit_code == EXIT_OK
            assert "abc123" in result.output
            assert "Chart 1" in result.output
            assert "def456" in result.output

    def test_list_empty(self, runner):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status.return_value = None

        with patch("skua.cli.requests.get", return_value=mock_resp), \
             patch("skua.cli.get_client_token", return_value="anon_test"), \
             patch("skua.cli.get_api_url", return_value="https://api.skua.dev"):
            result = runner.invoke(main, ["list"])
            assert result.exit_code == EXIT_OK
            assert "No records" in result.output

    def test_list_json_output(self, runner):
        items = [{"id": "abc123", "title": "Chart", "visibility": "public"}]
        mock_resp = MagicMock()
        mock_resp.json.return_value = items
        mock_resp.raise_for_status.return_value = None

        with patch("skua.cli.requests.get", return_value=mock_resp), \
             patch("skua.cli.get_client_token", return_value="anon_test"), \
             patch("skua.cli.get_api_url", return_value="https://api.skua.dev"):
            result = runner.invoke(main, ["list", "--json"])
            assert result.exit_code == EXIT_OK
            parsed = json.loads(result.output)
            assert len(parsed) == 1
            assert parsed[0]["id"] == "abc123"

    def test_list_rate_limited(self, runner):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        http_err = __import__("requests").exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err

        with patch("skua.cli.requests.get", return_value=mock_resp), \
             patch("skua.cli.get_client_token", return_value="anon_test"), \
             patch("skua.cli.get_api_url", return_value="https://api.skua.dev"):
            result = runner.invoke(main, ["list"])
            assert result.exit_code == EXIT_RATE_LIMITED

    def test_list_auth_error(self, runner):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        http_err = __import__("requests").exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err

        with patch("skua.cli.requests.get", return_value=mock_resp), \
             patch("skua.cli.get_client_token", return_value="anon_test"), \
             patch("skua.cli.get_api_url", return_value="https://api.skua.dev"):
            result = runner.invoke(main, ["list"])
            assert result.exit_code == EXIT_AUTH


# =============================================================================
# open command
# =============================================================================


class TestOpenCommand:
    def test_open(self, runner):
        with patch("webbrowser.open") as mock_open:
            result = runner.invoke(main, ["open", "abc123"])
            assert result.exit_code == EXIT_OK
            mock_open.assert_called_once_with("https://skua.dev/r/abc123")
            assert "abc123" in result.output


# =============================================================================
# version
# =============================================================================


class TestVersion:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == EXIT_OK
        # Should contain version info
        assert "version" in result.output.lower() or "." in result.output


# =============================================================================
# --collection flag
# =============================================================================


class TestCollectionFlag:
    def test_record_subcommand_accepts_collection_flag(self, monkeypatch, tmp_path):
        """`skua record --collection NAME path` sends collection_name on the wire."""
        captured_payload = {}

        def fake_upload_record(payload):
            captured_payload.update(payload)
            return {
                "id": "rec1",
                "creator_username": "testbird-42",
                "visibility": "public",
                "collection_id": "coll1",
                "collection_name": "Q3 Review",
                "collection_url": "https://skua.dev/u/testbird-42/c/q3-review",
            }

        monkeypatch.setattr("skua.cli.upload_record", fake_upload_record)

        sample = tmp_path / "data.txt"
        sample.write_text("hello")

        runner = CliRunner()
        result = runner.invoke(main, ["record", "--collection", "Q3 Review", "--title", "X", str(sample)])
        assert result.exit_code == 0, result.output
        assert captured_payload.get("collection_name") == "Q3 Review"

    def test_record_subcommand_omits_collection_when_flag_not_passed(self, monkeypatch, tmp_path):
        """No --collection → no collection_name on the wire (Default routing)."""
        captured_payload = {}

        def fake_upload_record(payload):
            captured_payload.update(payload)
            return {"id": "rec1", "creator_username": None, "visibility": "public"}

        monkeypatch.setattr("skua.cli.upload_record", fake_upload_record)

        sample = tmp_path / "data.txt"
        sample.write_text("hello")

        runner = CliRunner()
        result = runner.invoke(main, ["record", "--title", "X", str(sample)])
        assert result.exit_code == 0, result.output
        assert "collection_name" not in captured_payload
