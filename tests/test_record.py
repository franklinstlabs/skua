"""Tests for the record() function.

This module tests the main user-facing record() function that ties together
serializers and client to upload records to Skua.

Tests are organized by functionality:
- Basic record() flow
- Parameter handling
- Integration with serializers
- Integration with client
- URL construction
- RecordResult return value
- Error handling
- Edge cases
"""

import pytest
from unittest.mock import patch, MagicMock

from skua.record import record
from skua.result import RecordResult
from skua.exceptions import ConfigurationError, UploadError, SerializationError


class TestRecordVisibilityKwarg:
    """record() accepts an explicit three-way visibility= kwarg."""

    def _run_with_visibility(self, **kwargs):
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_auth_status") as mock_status:
            mock_status.return_value = {"verified": True}
            mock_upload.return_value = {"id": "x", "visibility": "public"}
            record("test", title="T", **kwargs)
            return mock_upload.call_args[0][0]["visibility"]

    def test_visibility_public(self):
        assert self._run_with_visibility(visibility="public") == "public"

    def test_visibility_unlisted(self):
        assert self._run_with_visibility(visibility="unlisted") == "unlisted"

    def test_visibility_private(self):
        assert self._run_with_visibility(visibility="private") == "private"

    def test_invalid_visibility_raises(self):
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Invalid visibility"):
            record("test", title="T", visibility="secret")  # type: ignore[arg-type]


class TestRecordAnonPrivateFailFast:
    """visibility='private' requires a verified account at the SDK boundary.

    The backend rejects the same shape with the same message — this check is
    pure fail-fast: avoids serializing + uploading 10MB before getting 422.
    Only fires when the caller explicitly passes visibility='private', so the
    common path (no visibility kwarg → server-side 'unlisted' default) stays
    network-cheap.
    """

    def test_anon_private_raises_before_upload(self):
        with patch("skua.record.get_auth_status") as mock_status, \
             patch("skua.record.upload_record") as mock_upload:
            mock_status.return_value = {"verified": False, "username": "anon-1"}
            with pytest.raises(UploadError, match="verified"):
                record("test", title="T", visibility="private")
            mock_upload.assert_not_called()

    def test_verified_private_uploads(self):
        with patch("skua.record.get_auth_status") as mock_status, \
             patch("skua.record.upload_record") as mock_upload:
            mock_status.return_value = {"verified": True, "username": "verified-1"}
            mock_upload.return_value = {"id": "x", "visibility": "private"}
            record("test", title="T", visibility="private")
            mock_upload.assert_called_once()

    def test_unlisted_skips_status_check(self):
        """visibility='unlisted' is fine for anon — no status network call."""
        with patch("skua.record.get_auth_status") as mock_status, \
             patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "x", "visibility": "unlisted"}
            record("test", title="T", visibility="unlisted")
            mock_status.assert_not_called()

    def test_public_skips_status_check(self):
        with patch("skua.record.get_auth_status") as mock_status, \
             patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "x", "visibility": "public"}
            record("test", title="T", visibility="public")
            mock_status.assert_not_called()

    def test_no_visibility_kwarg_skips_status_check(self):
        """Common path: no visibility kwarg → no /auth/status roundtrip."""
        with patch("skua.record.get_auth_status") as mock_status, \
             patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "x", "visibility": "unlisted"}
            record("test", title="T")
            mock_status.assert_not_called()


class TestRecordBasicFlow:
    """Test basic record() function flow."""

    def test_record_returns_record_result(self):
        """Test that record() returns a RecordResult object."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record("test string", title="Test")

            assert isinstance(result, RecordResult)

    def test_record_calls_serialize_object(self):
        """Test that record() calls serialize_object with the input."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.serialize_object") as mock_serialize:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_serialize.return_value = {
                "type": "text",
                "format": "plain",
                "data": "test",
                "metadata": {}
            }

            record("test string", title="Test")

            mock_serialize.assert_called_once_with("test string")

    def test_record_calls_upload_record(self):
        """Test that record() calls upload_record with serialized data."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            record("test string", title="Test Title")

            mock_upload.assert_called_once()
            call_args = mock_upload.call_args
            data = call_args[0][0]

            assert data["title"] == "Test Title"
            assert data["content"]["type"] == "text"
            assert data["content"]["format"] == "plain"

    def test_record_prints_url(self, capsys):
        """Test that record() prints the URL to stdout."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "abc123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "http://localhost:5173"

            record("test", title="Test")

            captured = capsys.readouterr()
            assert "abc123" in captured.out
            assert "✓" in captured.out


class TestRecordParameters:
    """Test record() parameter handling."""

    def test_record_with_title(self):
        """Test that title parameter is passed through."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            record("test", title="My Title")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["title"] == "My Title"

    def test_record_requires_title(self):
        """Test that record() raises ValidationError without a title."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Title is required"):
            record("test", title="")

    def test_record_with_description(self):
        """Test that description parameter is passed through."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            record("test", title="Test", description="A description")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["description"] == "A description"

    def test_record_with_no_description_passes_none(self):
        """Test that no description defaults to None."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            record("test", title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["description"] is None


class TestRecordResultContents:
    """Test the contents of the returned RecordResult."""

    def test_record_result_has_correct_url(self):
        """Test that RecordResult.url is constructed correctly."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "abc123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "http://localhost:5173"

            result = record("test", title="Test")

            assert result.url == "http://localhost:5173/r/abc123"

    def test_record_result_has_metadata_with_id(self):
        """Test that RecordResult.metadata contains the record ID."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "xyz789", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record("test", title="Test")

            assert result.metadata["id"] == "xyz789"

    def test_record_result_has_metadata_with_title(self):
        """Test that RecordResult.metadata contains the title."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record("test", title="My Custom Title")

            assert result.metadata["title"] == "My Custom Title"

    def test_record_result_has_metadata_with_creator_username(self):
        """RecordResult.metadata exposes creator_username when the server returns it.

        Users need this to build profile URLs without round-tripping to the web UI,
        e.g. f"https://skua.dev/u/{result.metadata['creator_username']}".
        """
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record("test", title="Test")

            assert result.metadata["creator_username"] == "swift-gannet-4291"

    def test_record_result_omits_creator_username_when_absent(self):
        """Anonymous records (server doesn't return creator_username) should not
        surface the key at all rather than setting it to None."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public"}

            result = record("test", title="Test")

            assert "creator_username" not in result.metadata

    def test_record_result_has_raw_url_pointing_at_api(self):
        """RecordResult.metadata.raw_url hits the API directly, not the web origin.

        Frontend proxy used to serve /raw but tripped CF Pages bot filter for
        Python UAs. API handles it directly and skips that edge.
        """
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_api_url") as mock_api_url, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "raw123", "visibility": "public"}
            mock_api_url.return_value = "https://api.skua.dev"
            mock_web_url.return_value = "https://skua.dev"

            result = record("test", title="Test")

            assert result.metadata["raw_url"] == "https://api.skua.dev/records/raw123/raw"

    def test_record_result_wraps_original_object(self):
        """Test that RecordResult wraps the original object."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            original = {"key": "value", "number": 42}
            result = record(original, title="Test")

            # RecordResult should delegate operations to the wrapped object
            assert result["key"] == "value"
            assert result["number"] == 42


class TestRecordURLConstruction:
    """Test URL construction for different API configurations."""

    def test_url_for_production_api(self):
        """Test URL construction for production API."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "abc123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "https://skua.dev"

            result = record("test", title="Test")

            assert result.url == "https://skua.dev/r/abc123"

    def test_url_for_localhost_api(self):
        """Test URL construction for localhost API."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "abc123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "http://localhost:5173"

            result = record("test", title="Test")

            assert result.url == "http://localhost:5173/r/abc123"

    def test_url_for_custom_api(self):
        """Test URL construction for custom API (fallback behavior)."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "abc123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "https://custom.example.com"

            result = record("test", title="Test")

            # Fallback: use API URL as app URL
            assert result.url == "https://custom.example.com/r/abc123"


class TestRecordWithDifferentObjectTypes:
    """Test record() with various object types."""

    def test_record_with_string(self):
        """Test recording a plain string."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record("Hello, World!", title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert data["content"]["data"] == "Hello, World!"

    def test_record_with_dict(self):
        """Test recording a dictionary uses DictSerializer."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record({"key": "value"}, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "dict"
            assert data["content"]["format"] == "json"

    def test_record_with_list(self):
        """Test recording a list (falls back to string serializer)."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record([1, 2, 3, 4, 5], title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert data["content"]["metadata"]["original_type"] == "list"

    def test_record_with_integer(self):
        """Test recording an integer."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(42, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert data["content"]["data"] == "42"


class TestRecordWithMatplotlib:
    """Test record() with matplotlib figures."""

    @pytest.fixture
    def matplotlib_figure(self):
        """Create a matplotlib figure for testing."""
        try:
            import matplotlib
            matplotlib.use("Agg")  # Use non-GUI backend
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            ax.plot([1, 2, 3], [1, 4, 9])
            ax.set_title("Test Plot")
            yield fig
            plt.close(fig)
        except ImportError:
            pytest.skip("matplotlib not installed")

    def test_record_matplotlib_figure(self, matplotlib_figure):
        """Test recording a matplotlib figure."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(matplotlib_figure, title="Test Plot")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "matplotlib.figure"
            assert data["content"]["format"] == "png"
            # Data should be base64 encoded
            assert len(data["content"]["data"]) > 0

    def test_record_matplotlib_figure_metadata(self, matplotlib_figure):
        """Test that matplotlib figure metadata is included."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(matplotlib_figure, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert "dpi" in data["content"]["metadata"]
            assert "size_bytes" in data["content"]["metadata"]


class TestRecordWithPandas:
    """Test record() with pandas DataFrames."""

    @pytest.fixture
    def sample_dataframe(self):
        """Create a pandas DataFrame for testing."""
        try:
            import pandas as pd
            return pd.DataFrame({
                "a": [1, 2, 3],
                "b": [4, 5, 6],
                "c": ["x", "y", "z"]
            })
        except ImportError:
            pytest.skip("pandas not installed")

    def test_record_dataframe(self, sample_dataframe):
        """Test recording a pandas DataFrame."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(sample_dataframe, title="Test DataFrame")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "pandas.dataframe"
            assert data["content"]["format"] == "json"

    def test_record_dataframe_metadata(self, sample_dataframe):
        """Test that DataFrame metadata is included."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(sample_dataframe, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            metadata = data["content"]["metadata"]
            assert metadata["shape"] == (3, 3)
            assert "a" in metadata["columns"]
            assert "b" in metadata["columns"]
            assert "c" in metadata["columns"]


class TestRecordWithPIL:
    """Test record() with PIL/Pillow images."""

    @pytest.fixture
    def pil_image(self):
        """Create a PIL Image for testing."""
        try:
            from PIL import Image
            return Image.new("RGB", (100, 100), color="red")
        except ImportError:
            pytest.skip("PIL/Pillow not installed")

    def test_record_pil_image(self, pil_image):
        """Test recording a PIL Image."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(pil_image, title="Test Image")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "pil.image"
            assert data["content"]["format"] == "png"

    def test_record_pil_image_metadata(self, pil_image):
        """Test that PIL Image metadata is included."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(pil_image, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            metadata = data["content"]["metadata"]
            assert metadata["size"] == (100, 100)
            assert metadata["mode"] == "RGB"


class TestRecordErrorHandling:
    """Test error handling in record()."""

    def test_record_propagates_upload_error(self):
        """Test that UploadError from client propagates."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.side_effect = UploadError("Upload failed: 500 Internal Server Error")

            with pytest.raises(UploadError) as exc_info:
                record("test", title="Test")

            assert "Upload failed" in str(exc_info.value)

    def test_record_propagates_serialization_error(self):
        """Test that SerializationError propagates."""
        with patch("skua.record.serialize_object") as mock_serialize:
            mock_serialize.side_effect = SerializationError("Cannot serialize")

            with pytest.raises(SerializationError) as exc_info:
                record("test", title="Test")

            assert "Cannot serialize" in str(exc_info.value)

    def test_record_with_api_connection_error(self):
        """Test handling of connection errors from client."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.side_effect = UploadError(
                "Failed to upload record: Connection refused"
            )

            with pytest.raises(UploadError) as exc_info:
                record("test", title="Test")

            assert "Connection refused" in str(exc_info.value)

    def test_record_with_api_timeout(self):
        """Test handling of timeout errors from client."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.side_effect = UploadError(
                "Failed to upload record: Request timeout"
            )

            with pytest.raises(UploadError) as exc_info:
                record("test", title="Test")

            assert "timeout" in str(exc_info.value).lower()


class TestRecordEdgeCases:
    """Test edge cases and special scenarios."""

    def test_record_with_none_raises_validation_error(self):
        """Test that recording None raises ValidationError."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Cannot record None"):
            record(None, title="Test")

    def test_record_with_empty_string_raises(self):
        """Empty string is rejected before serialization/upload."""
        from skua.exceptions import ValidationError
        with patch("skua.record.upload_record") as mock_upload:
            with pytest.raises(ValidationError, match="empty str"):
                record("", title="Test")
            mock_upload.assert_not_called()

    def test_record_with_empty_dict_raises(self):
        """Empty dict is rejected before serialization/upload."""
        from skua.exceptions import ValidationError
        with patch("skua.record.upload_record") as mock_upload:
            with pytest.raises(ValidationError, match="empty dict"):
                record({}, title="Test")
            mock_upload.assert_not_called()

    def test_record_with_empty_list_raises(self):
        """Empty list is rejected before serialization/upload."""
        from skua.exceptions import ValidationError
        with patch("skua.record.upload_record") as mock_upload:
            with pytest.raises(ValidationError, match="empty list"):
                record([], title="Test")
            mock_upload.assert_not_called()

    def test_record_with_unicode(self):
        """Test recording unicode content."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record("Hello\u4e16\u754c! \U0001F680", title="Test")  # Chinese + rocket emoji

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert "Hello" in data["content"]["data"]
            assert "\u4e16\u754c" in data["content"]["data"]

    def test_record_with_multiline_string(self):
        """Test recording multiline text."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            multiline = """Line 1
Line 2
Line 3"""
            result = record(multiline, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert "Line 1" in data["content"]["data"]
            assert "Line 2" in data["content"]["data"]

    def test_record_with_special_characters_in_title(self):
        """Test recording with special characters in title."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record("test", title="Test <script>alert('xss')</script>")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert "<script>" in data["title"]

    def test_record_with_very_long_title_raises_error(self):
        """Test recording with a title over 500 chars raises ValidationError."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Title too long"):
            record("test", title="x" * 501)

class TestRecordTitleValidation:
    """Test title validation in record()."""

    def test_empty_title_raises_validation_error(self):
        """Test that empty string title raises ValidationError."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Title is required"):
            record("test", title="")

    def test_whitespace_title_raises_validation_error(self):
        """Test that whitespace-only title raises ValidationError."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Title is required"):
            record("test", title="   ")

    def test_title_over_500_chars_raises_validation_error(self):
        """Test that title over 500 characters raises ValidationError."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Title too long"):
            record("test", title="x" * 501)

    def test_non_string_title_raises_validation_error(self):
        """Defensive guard: passing a non-string title (e.g. a Mock left over
        from a test fixture, or accidentally an int) is rejected at the SDK
        boundary instead of silently uploading repr(obj) as the title."""
        from skua.exceptions import ValidationError
        from unittest.mock import MagicMock
        with pytest.raises(ValidationError, match="Title must be a string"):
            record("test", title=MagicMock())  # type: ignore[arg-type]
        with pytest.raises(ValidationError, match="Title must be a string"):
            record("test", title=42)  # type: ignore[arg-type]

    def test_title_at_500_chars_succeeds(self):
        """Test that title at exactly 500 characters succeeds."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            record("test", title="x" * 500)

    def test_title_is_stripped(self):
        """Test that title whitespace is stripped."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            record("test", title="  My Title  ")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["title"] == "My Title"


class TestRecordTagsParameter:
    """Test tags parameter in record()."""

    def test_tags_passed_through_to_upload(self):
        """Test that tags are included in the upload data."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "user1"}

            record("test", title="Test", tags=["ml", "analysis"])

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["tags"] == ["ml", "analysis"]

    def test_no_tags_defaults_to_empty_list(self):
        """Test that omitting tags defaults to empty list."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "user1"}

            record("test", title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["tags"] == []

    def test_too_many_tags_raises_validation_error(self):
        """Test that more than 20 tags raises ValidationError."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Too many tags"):
            record("test", title="Test", tags=[f"tag{i}" for i in range(21)])

    def test_tag_over_30_chars_raises_validation_error(self):
        """Test that a tag over 30 characters raises ValidationError."""
        from skua.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Tag too long"):
            record("test", title="Test", tags=["x" * 31])

    def test_empty_tags_are_filtered(self):
        """Test that empty string tags are removed."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "user1"}

            record("test", title="Test", tags=["ml", "", "  ", "analysis"])

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["tags"] == ["ml", "analysis"]

    def test_tags_are_stripped(self):
        """Test that tag whitespace is stripped."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "user1"}

            record("test", title="Test", tags=["  ml  ", "analysis  "])

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["tags"] == ["ml", "analysis"]

    def test_exactly_20_tags_succeeds(self):
        """Test that exactly 20 tags is allowed."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "user1"}

            record("test", title="Test", tags=[f"tag{i}" for i in range(20)])

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert len(data["tags"]) == 20

    def test_tag_at_30_chars_succeeds(self):
        """Test that a tag at exactly 30 characters is allowed."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "user1"}

            record("test", title="Test", tags=["x" * 30])

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["tags"] == ["x" * 30]


class TestRecordIntegrationWithSerializers:
    """Test record() integration with the serializer registry."""

    def test_serializer_priority_matplotlib_over_fallback(self):
        """Test that matplotlib serializer takes priority over fallback."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            pytest.skip("matplotlib not installed")

        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            fig, ax = plt.subplots()
            try:
                record(fig, title="Test")

                call_args = mock_upload.call_args
                data = call_args[0][0]
                # Should use matplotlib serializer, not string fallback
                assert data["content"]["type"] == "matplotlib.figure"
                assert data["content"]["format"] == "png"
            finally:
                plt.close(fig)

    def test_serializer_priority_pandas_over_fallback(self):
        """Test that pandas serializer takes priority over fallback."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")

        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            df = pd.DataFrame({"a": [1]})
            record(df, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            # Should use pandas serializer, not string fallback
            assert data["content"]["type"] == "pandas.dataframe"
            assert data["content"]["format"] == "json"

    def test_fallback_to_string_serializer(self):
        """Test fallback to string serializer for unknown types."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            # Custom class that no serializer handles specifically
            class CustomObject:
                def __str__(self):
                    return "CustomObject()"

            record(CustomObject(), title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert data["content"]["data"] == "CustomObject()"
            assert data["content"]["metadata"]["original_type"] == "CustomObject"


class TestRecordWithCustomObjects:
    """Test record() with custom objects."""

    def test_record_custom_object_with_str(self):
        """Test recording a custom object with __str__."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            class Point:
                def __init__(self, x, y):
                    self.x = x
                    self.y = y

                def __str__(self):
                    return f"Point({self.x}, {self.y})"

            result = record(Point(3, 4), title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["data"] == "Point(3, 4)"

    def test_record_custom_object_without_str(self):
        """Test recording a custom object without __str__ uses default repr."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            class Plain:
                pass

            result = record(Plain(), title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert "Plain" in data["content"]["data"]


class TestRecordConcurrency:
    """Test record() behavior in concurrent scenarios."""

    def test_multiple_records_in_sequence(self):
        """Test multiple sequential record() calls."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.side_effect = [
                {"id": "id1", "visibility": "public", "creator_username": None},
                {"id": "id2", "visibility": "public", "creator_username": None},
                {"id": "id3", "visibility": "public", "creator_username": None},
            ]

            r1 = record("first", title="Test")
            r2 = record("second", title="Test")
            r3 = record("third", title="Test")

            assert r1.metadata["id"] == "id1"
            assert r2.metadata["id"] == "id2"
            assert r3.metadata["id"] == "id3"

    def test_record_does_not_modify_input(self):
        """Test that record() does not modify the input object."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            original_list = [1, 2, 3]
            original_copy = original_list.copy()

            record(original_list, title="Test")

            assert original_list == original_copy


class TestRecordAllParametersCombined:
    """Test record() with all parameters specified at once."""

    def test_all_parameters_passed_correctly(self):
        """Test that all parameters work together correctly."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "test-id-123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "http://localhost:5173"

            result = record(
                {"test": "data"},
                title="Complete Test",
                description="A test description",
            )

            call_args = mock_upload.call_args
            data = call_args[0][0]

            assert data["title"] == "Complete Test"
            assert data["description"] == "A test description"

            assert result.metadata["id"] == "test-id-123"
            assert result.metadata["title"] == "Complete Test"


class TestRecordFileSizeLimits:
    """Test file size limit enforcement (client-side validation)."""

    def test_large_file_raises_upload_error(self):
        """Test that files exceeding 10MB raise UploadError."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.side_effect = UploadError(
                "File too large (15.0MB). Maximum allowed: 10MB."
            )

            with pytest.raises(UploadError) as exc_info:
                record("x" * (15 * 1024 * 1024), title="Test")  # 15MB of data

            assert "too large" in str(exc_info.value).lower()
            assert "10MB" in str(exc_info.value)

    def test_file_at_limit_succeeds(self):
        """Test that files at the limit (10MB) succeed."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            # This should not raise - mock allows it through
            result = record("test data at reasonable size", title="Test")

            assert result.metadata["id"] == "test123"


class TestRecordSerializationOutput:
    """Test the structure of serialized content."""

    def test_serialized_content_has_required_fields(self):
        """Test that serialized content has all required fields."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            record("test string", title="Test")

            call_args = mock_upload.call_args
            content = call_args[0][0]["content"]

            # All serialized content must have these fields
            assert "type" in content
            assert "format" in content
            assert "data" in content
            assert "metadata" in content

    def test_serialized_content_types_are_strings(self):
        """Test that type and format are strings."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            record("test", title="Test")

            call_args = mock_upload.call_args
            content = call_args[0][0]["content"]

            assert isinstance(content["type"], str)
            assert isinstance(content["format"], str)


class TestRecordResultIntegrity:
    """Test RecordResult maintains data integrity."""

    def test_result_url_matches_id(self):
        """Test that result URL contains the correct ID."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "unique-id-789", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "http://localhost:5173"

            result = record("test", title="Test")

            assert "unique-id-789" in result.url
            assert result.metadata["id"] == "unique-id-789"

    def test_result_metadata_matches_input(self):
        """Test that result metadata matches input parameters."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record("test", title="Exact Title")

            assert result.metadata["title"] == "Exact Title"

    def test_result_allows_iteration_on_list(self):
        """Test RecordResult allows iteration when wrapping a list."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record([1, 2, 3, 4, 5], title="Test")

            # Should be iterable
            items = list(result)
            assert items == [1, 2, 3, 4, 5]

    def test_result_allows_key_access_on_dict(self):
        """Test RecordResult allows key access when wrapping a dict."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record({"a": 1, "b": 2}, title="Test")

            assert result["a"] == 1
            assert result["b"] == 2
            assert "a" in result


class TestRecordPrintBehavior:
    """Test stdout print behavior of record()."""

    def test_print_format_includes_checkmark(self, capsys):
        """Test that printed output includes checkmark symbol."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "http://localhost:5173"

            record("test", title="Test")

            captured = capsys.readouterr()
            assert "✓" in captured.out
            assert "test123" in captured.out

    def test_print_includes_full_url(self, capsys):
        """Test that printed output includes the full URL."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "abc123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "https://skua.dev"

            record("test", title="Test")

            captured = capsys.readouterr()
            assert "https://skua.dev/r/abc123" in captured.out

    def test_print_goes_to_stdout(self, capsys):
        """Test that output goes to stdout, not stderr."""
        with patch("skua.record.upload_record") as mock_upload, \
             patch("skua.record.get_web_url") as mock_web_url:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}
            mock_web_url.return_value = "http://localhost:5173"

            record("test", title="Test")

            captured = capsys.readouterr()
            assert len(captured.out) > 0
            assert captured.err == ""


class TestRecordNumericTypes:
    """Test record() with various numeric types."""

    def test_record_float(self):
        """Test recording a float."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(3.14159, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert "3.14159" in data["content"]["data"]

    def test_record_complex(self):
        """Test recording a complex number."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(3 + 4j, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert "3" in data["content"]["data"]
            assert "4" in data["content"]["data"]

    def test_record_boolean(self):
        """Test recording a boolean."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            result = record(True, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert data["content"]["data"] == "True"


class TestRecordNestedStructures:
    """Test record() with nested data structures."""

    def test_record_nested_dict(self):
        """Test recording a nested dictionary."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            nested = {
                "level1": {
                    "level2": {
                        "level3": "deep value"
                    }
                }
            }
            result = record(nested, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "dict"
            assert "deep value" in data["content"]["data"]

    def test_record_list_of_dicts(self):
        """Test recording a list of dictionaries."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            list_of_dicts = [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
            result = record(list_of_dicts, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert "Alice" in data["content"]["data"]
            assert "Bob" in data["content"]["data"]


class TestRecordSpecialStrings:
    """Test record() with special string content."""

    def test_record_json_string(self):
        """Test recording a JSON string (should be treated as text)."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            json_str = '{"key": "value"}'
            result = record(json_str, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert data["content"]["data"] == json_str

    def test_record_html_string(self):
        """Test recording HTML content."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            html = "<html><body><h1>Title</h1></body></html>"
            result = record(html, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["type"] == "text"
            assert "<html>" in data["content"]["data"]

    def test_record_sql_string(self):
        """Test recording SQL content."""
        with patch("skua.record.upload_record") as mock_upload:
            mock_upload.return_value = {"id": "test123", "visibility": "public", "creator_username": "swift-gannet-4291"}

            sql = "SELECT * FROM users WHERE id = 1;"
            result = record(sql, title="Test")

            call_args = mock_upload.call_args
            data = call_args[0][0]
            assert data["content"]["data"] == sql


# Append below — module-level call routes to the user's per-server Default
# collection (no collection_name on the wire). Per-call visibility= still wins.
# RecordResult exposes collection_name / collection_id / collection_url in metadata.

import skua
from skua.exceptions import ValidationError


@pytest.fixture
def fake_upload():
    """Patch upload_record so we can inspect the payload."""
    with patch("skua.record.upload_record") as upload:
        upload.return_value = {
            "id": "rec1234567890",
            "creator_username": "testbird-42",
            "visibility": "public",
            "collection_id": "coll12345678",
            "collection_name": "Default",
            "collection_url": "https://skua.dev/u/testbird-42/c/default",
        }
        yield upload


class TestRecordPayload:
    def test_bare_record_omits_collection_name(self, fake_upload):
        skua.record("hi", title="x")
        payload = fake_upload.call_args.args[0]
        assert "collection_name" not in payload

    def test_record_includes_title_and_content(self, fake_upload):
        skua.record("hi", title="My Note")
        payload = fake_upload.call_args.args[0]
        assert payload["title"] == "My Note"
        assert "content" in payload

    def test_record_visibility_passes_through(self, fake_upload):
        skua.record("hi", title="x", visibility="unlisted")
        payload = fake_upload.call_args.args[0]
        assert payload["visibility"] == "unlisted"

    def test_record_validates_visibility_value(self, fake_upload):
        with pytest.raises(ValidationError, match="Invalid visibility"):
            skua.record("hi", title="x", visibility="secret")


class TestRecordResultMetadata:
    def test_metadata_contains_collection_fields(self, fake_upload):
        result = skua.record("hi", title="x")
        assert result.metadata["collection_name"] == "Default"
        assert result.metadata["collection_id"] == "coll12345678"
        assert result.metadata["collection_url"] == "https://skua.dev/u/testbird-42/c/default"

    def test_metadata_contains_record_id_and_url(self, fake_upload):
        result = skua.record("hi", title="x")
        assert result.metadata["id"] == "rec1234567890"
        assert "/r/rec1234567890" in result.url

    def test_metadata_does_not_contain_session_aliases(self, fake_upload):
        """0.12 is a clean break — no session_name / session_id in user-visible metadata."""
        result = skua.record("hi", title="x")
        assert "session_name" not in result.metadata
        assert "session_id" not in result.metadata


class TestRecordValidation:
    def test_record_none_raises(self):
        with pytest.raises(ValidationError, match="None"):
            skua.record(None, title="x")

    def test_record_empty_title_raises(self):
        with pytest.raises(ValidationError, match="[Tt]itle"):
            skua.record("hi", title="")


class TestInitIsRemoved:
    """`skua.init()` was a deprecation cushion in 0.12 (raised ConfigurationError
    with a migration snippet); removed entirely in 0.13. Calling it now
    fails with AttributeError — the standard Python error for a missing
    symbol. Pre-0.12 notebooks that survived 0.12 with the custom message
    have had a release cycle to migrate; nothing left to cushion."""

    def test_init_is_gone(self):
        with pytest.raises(AttributeError):
            skua.init("anything")  # type: ignore[attr-defined]
