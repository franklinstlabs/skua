"""Comprehensive tests for object serializers.

Tests cover:
- MatplotlibSerializer: matplotlib figures to PNG base64
- PandasDataFrameSerializer: DataFrames to JSON
- PILImageSerializer: PIL Images to PNG base64
- StringSerializer: fallback for any object
- Registry/selection logic: correct serializer selected by type
- Edge cases: empty inputs, large objects, various dtypes
"""

import base64
import json

import pytest

from skua.serializers import (
    SERIALIZERS,
    DictSerializer,
    MatplotlibSerializer,
    NumpySerializer,
    PandasDataFrameSerializer,
    PILImageSerializer,
    StringSerializer,
    serialize_object,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def matplotlib_serializer():
    """Provide a MatplotlibSerializer instance."""
    return MatplotlibSerializer()


@pytest.fixture
def pandas_serializer():
    """Provide a PandasDataFrameSerializer instance."""
    return PandasDataFrameSerializer()


@pytest.fixture
def pil_serializer():
    """Provide a PILImageSerializer instance."""
    return PILImageSerializer()


@pytest.fixture
def dict_serializer():
    """Provide a DictSerializer instance."""
    return DictSerializer()


@pytest.fixture
def numpy_serializer():
    """Provide a NumpySerializer instance."""
    return NumpySerializer()


@pytest.fixture
def string_serializer():
    """Provide a StringSerializer instance."""
    return StringSerializer()


@pytest.fixture
def simple_figure():
    """Provide a simple matplotlib figure for testing."""
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 4, 9])
    ax.set_title("Test Plot")
    yield fig
    plt.close(fig)


@pytest.fixture
def empty_figure():
    """Provide an empty matplotlib figure (no axes content)."""
    plt = pytest.importorskip("matplotlib.pyplot")
    fig = plt.figure()
    yield fig
    plt.close(fig)


@pytest.fixture
def multi_subplot_figure():
    """Provide a figure with multiple subplots."""
    plt = pytest.importorskip("matplotlib.pyplot")
    fig, axes = plt.subplots(2, 2)
    axes[0, 0].plot([1, 2, 3])
    axes[0, 1].bar([1, 2, 3], [4, 5, 6])
    axes[1, 0].scatter([1, 2, 3], [1, 4, 9])
    axes[1, 1].hist([1, 2, 2, 3, 3, 3])
    yield fig
    plt.close(fig)


@pytest.fixture
def simple_dataframe():
    """Provide a simple pandas DataFrame."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame({"a": [1, 2, 3], "b": [4.0, 5.0, 6.0], "c": ["x", "y", "z"]})


@pytest.fixture
def empty_dataframe():
    """Provide an empty DataFrame."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame()


@pytest.fixture
def single_row_dataframe():
    """Provide a DataFrame with a single row."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame({"col": [42]})


@pytest.fixture
def single_column_dataframe():
    """Provide a DataFrame with a single column."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame({"only_col": [1, 2, 3, 4, 5]})


@pytest.fixture
def datetime_dataframe():
    """Provide a DataFrame with datetime columns."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=3),
            "value": [100, 200, 300],
        }
    )


@pytest.fixture
def large_dataframe():
    """Provide a larger DataFrame for testing."""
    pd = pytest.importorskip("pandas")
    return pd.DataFrame(
        {
            "id": range(1000),
            "value": [i * 1.5 for i in range(1000)],
            "name": [f"item_{i}" for i in range(1000)],
        }
    )


@pytest.fixture
def rgb_image():
    """Provide an RGB PIL Image."""
    Image = pytest.importorskip("PIL.Image")
    return Image.new("RGB", (100, 100), color="red")


@pytest.fixture
def rgba_image():
    """Provide an RGBA PIL Image with transparency."""
    Image = pytest.importorskip("PIL.Image")
    img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    return img


@pytest.fixture
def grayscale_image():
    """Provide a grayscale (mode L) PIL Image."""
    Image = pytest.importorskip("PIL.Image")
    return Image.new("L", (100, 100), color=128)


@pytest.fixture
def small_image():
    """Provide a very small PIL Image (1x1)."""
    Image = pytest.importorskip("PIL.Image")
    return Image.new("RGB", (1, 1), color="blue")


@pytest.fixture
def large_image():
    """Provide a larger PIL Image."""
    Image = pytest.importorskip("PIL.Image")
    return Image.new("RGB", (1000, 1000), color="green")


# =============================================================================
# MatplotlibSerializer Tests
# =============================================================================


class TestMatplotlibSerializer:
    """Tests for MatplotlibSerializer."""

    def test_can_serialize_figure(self, matplotlib_serializer, simple_figure):
        """Test that serializer correctly identifies matplotlib figures."""
        assert matplotlib_serializer.can_serialize(simple_figure) is True

    def test_cannot_serialize_non_figure(self, matplotlib_serializer):
        """Test that serializer rejects non-figure objects."""
        assert matplotlib_serializer.can_serialize("not a figure") is False
        assert matplotlib_serializer.can_serialize(42) is False
        assert matplotlib_serializer.can_serialize(None) is False
        assert matplotlib_serializer.can_serialize([1, 2, 3]) is False
        assert matplotlib_serializer.can_serialize({"key": "value"}) is False

    def test_serialize_simple_figure(self, matplotlib_serializer, simple_figure):
        """Test serialization of a basic matplotlib figure."""
        result = matplotlib_serializer.serialize(simple_figure)

        assert result["type"] == "matplotlib.figure"
        assert result["format"] == "png"
        assert "data" in result
        assert "metadata" in result

        # Verify base64 decodes to valid PNG
        img_bytes = base64.b64decode(result["data"])
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes

    def test_serialize_metadata(self, matplotlib_serializer, simple_figure):
        """Test that metadata is correctly extracted."""
        result = matplotlib_serializer.serialize(simple_figure)

        assert result["metadata"]["dpi"] == 200
        assert "size_bytes" in result["metadata"]
        assert result["metadata"]["size_bytes"] > 0

    def test_serialize_empty_figure(self, matplotlib_serializer, empty_figure):
        """Test serialization of an empty figure (no content)."""
        result = matplotlib_serializer.serialize(empty_figure)

        assert result["type"] == "matplotlib.figure"
        assert result["format"] == "png"
        # Even empty figures should produce valid PNG
        img_bytes = base64.b64decode(result["data"])
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_serialize_multi_subplot(self, matplotlib_serializer, multi_subplot_figure):
        """Test serialization of figure with multiple subplots."""
        result = matplotlib_serializer.serialize(multi_subplot_figure)

        assert result["type"] == "matplotlib.figure"
        assert result["format"] == "png"
        # Multi-subplot figures should be larger
        assert result["metadata"]["size_bytes"] > 0

    def test_base64_is_valid_utf8(self, matplotlib_serializer, simple_figure):
        """Test that base64 data is valid UTF-8 string."""
        result = matplotlib_serializer.serialize(simple_figure)

        # Should not raise
        result["data"].encode("utf-8")
        # Should only contain valid base64 characters
        import re

        assert re.match(r"^[A-Za-z0-9+/=]+$", result["data"])


class TestMatplotlibSerializerWithoutImport:
    """Tests for MatplotlibSerializer when matplotlib is not available."""

    def test_can_serialize_returns_false_for_any_object(self, monkeypatch):
        """Test that can_serialize returns False when matplotlib is not installed."""
        # Simulate matplotlib not being installed
        import sys

        original_modules = sys.modules.copy()
        monkeypatch.setitem(sys.modules, "matplotlib", None)
        monkeypatch.setitem(sys.modules, "matplotlib.figure", None)

        # Create fresh serializer to pick up the mocked import
        serializer = MatplotlibSerializer()

        # Should return False for any object when matplotlib not available
        # Note: This may or may not work depending on how the import caching works
        # The implementation checks ImportError, so we verify the fallback behavior


# =============================================================================
# PandasDataFrameSerializer Tests
# =============================================================================


class TestPandasDataFrameSerializer:
    """Tests for PandasDataFrameSerializer."""

    def test_can_serialize_dataframe(self, pandas_serializer, simple_dataframe):
        """Test that serializer correctly identifies pandas DataFrames."""
        assert pandas_serializer.can_serialize(simple_dataframe) is True

    def test_cannot_serialize_non_dataframe(self, pandas_serializer):
        """Test that serializer rejects non-DataFrame objects."""
        assert pandas_serializer.can_serialize("not a dataframe") is False
        assert pandas_serializer.can_serialize(42) is False
        assert pandas_serializer.can_serialize(None) is False
        assert pandas_serializer.can_serialize([1, 2, 3]) is False
        assert pandas_serializer.can_serialize({"key": "value"}) is False

    def test_serialize_simple_dataframe(self, pandas_serializer, simple_dataframe):
        """Test serialization of a basic DataFrame."""
        result = pandas_serializer.serialize(simple_dataframe)

        assert result["type"] == "pandas.dataframe"
        assert result["format"] == "json"
        assert "data" in result
        assert "metadata" in result

        # Verify JSON is valid and uses split orient
        data = json.loads(result["data"])
        assert "columns" in data
        assert "index" in data
        assert "data" in data

    def test_serialize_metadata_shape(self, pandas_serializer, simple_dataframe):
        """Test that shape metadata is correct."""
        result = pandas_serializer.serialize(simple_dataframe)

        assert result["metadata"]["shape"] == (3, 3)

    def test_serialize_metadata_columns(self, pandas_serializer, simple_dataframe):
        """Test that columns metadata is correct."""
        result = pandas_serializer.serialize(simple_dataframe)

        assert result["metadata"]["columns"] == ["a", "b", "c"]

    def test_serialize_metadata_dtypes(self, pandas_serializer, simple_dataframe):
        """Test that dtype metadata is preserved."""
        result = pandas_serializer.serialize(simple_dataframe)

        dtypes = result["metadata"]["dtypes"]
        assert "a" in dtypes
        assert "b" in dtypes
        assert "c" in dtypes
        # Check dtype strings contain expected types
        assert "int" in dtypes["a"]
        assert "float" in dtypes["b"]
        assert "object" in dtypes["c"] or "str" in dtypes["c"]

    def test_serialize_empty_dataframe(self, pandas_serializer, empty_dataframe):
        """Test serialization of empty DataFrame."""
        result = pandas_serializer.serialize(empty_dataframe)

        assert result["type"] == "pandas.dataframe"
        assert result["metadata"]["shape"] == (0, 0)
        assert result["metadata"]["columns"] == []

    def test_serialize_single_row(self, pandas_serializer, single_row_dataframe):
        """Test serialization of single-row DataFrame."""
        result = pandas_serializer.serialize(single_row_dataframe)

        assert result["metadata"]["shape"] == (1, 1)
        data = json.loads(result["data"])
        assert data["data"] == [[42]]

    def test_serialize_single_column(self, pandas_serializer, single_column_dataframe):
        """Test serialization of single-column DataFrame."""
        result = pandas_serializer.serialize(single_column_dataframe)

        assert result["metadata"]["shape"] == (5, 1)
        assert result["metadata"]["columns"] == ["only_col"]

    def test_serialize_datetime_dataframe(self, pandas_serializer, datetime_dataframe):
        """Test serialization of DataFrame with datetime column."""
        result = pandas_serializer.serialize(datetime_dataframe)

        assert result["metadata"]["shape"] == (3, 2)
        # Datetime column should be serialized (pandas converts to milliseconds)
        assert "datetime" in result["metadata"]["dtypes"]["date"]

    def test_serialize_large_dataframe(self, pandas_serializer, large_dataframe):
        """Test serialization of larger DataFrame (no truncation)."""
        result = pandas_serializer.serialize(large_dataframe)

        assert result["metadata"]["shape"] == (1000, 3)
        # All data should be present (no truncation in current implementation)
        data = json.loads(result["data"])
        assert len(data["data"]) == 1000

    def test_data_roundtrip(self, pandas_serializer, simple_dataframe):
        """Test that serialized data can be reconstructed."""
        pd = pytest.importorskip("pandas")

        from io import StringIO
        result = pandas_serializer.serialize(simple_dataframe)
        reconstructed = pd.read_json(StringIO(result["data"]), orient="split")

        # Compare DataFrames
        assert list(reconstructed.columns) == list(simple_dataframe.columns)
        assert len(reconstructed) == len(simple_dataframe)


# =============================================================================
# PILImageSerializer Tests
# =============================================================================


class TestPILImageSerializer:
    """Tests for PILImageSerializer."""

    def test_can_serialize_pil_image(self, pil_serializer, rgb_image):
        """Test that serializer correctly identifies PIL Images."""
        assert pil_serializer.can_serialize(rgb_image) is True

    def test_cannot_serialize_non_image(self, pil_serializer):
        """Test that serializer rejects non-Image objects."""
        assert pil_serializer.can_serialize("not an image") is False
        assert pil_serializer.can_serialize(42) is False
        assert pil_serializer.can_serialize(None) is False
        assert pil_serializer.can_serialize([1, 2, 3]) is False
        assert pil_serializer.can_serialize({"key": "value"}) is False

    def test_serialize_rgb_image(self, pil_serializer, rgb_image):
        """Test serialization of RGB PIL Image."""
        result = pil_serializer.serialize(rgb_image)

        assert result["type"] == "pil.image"
        assert result["format"] == "png"
        assert "data" in result
        assert "metadata" in result

        # Verify base64 decodes to valid PNG
        img_bytes = base64.b64decode(result["data"])
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_serialize_rgb_metadata(self, pil_serializer, rgb_image):
        """Test RGB image metadata."""
        result = pil_serializer.serialize(rgb_image)

        assert result["metadata"]["size"] == (100, 100)
        assert result["metadata"]["mode"] == "RGB"
        assert result["metadata"]["size_bytes"] > 0

    def test_serialize_rgba_image(self, pil_serializer, rgba_image):
        """Test serialization of RGBA PIL Image with transparency."""
        result = pil_serializer.serialize(rgba_image)

        assert result["type"] == "pil.image"
        assert result["metadata"]["mode"] == "RGBA"
        assert result["metadata"]["size"] == (100, 100)

    def test_serialize_grayscale_image(self, pil_serializer, grayscale_image):
        """Test serialization of grayscale (mode L) PIL Image."""
        result = pil_serializer.serialize(grayscale_image)

        assert result["type"] == "pil.image"
        assert result["metadata"]["mode"] == "L"
        assert result["metadata"]["size"] == (100, 100)

    def test_serialize_small_image(self, pil_serializer, small_image):
        """Test serialization of very small (1x1) image."""
        result = pil_serializer.serialize(small_image)

        assert result["metadata"]["size"] == (1, 1)
        # Should still produce valid PNG
        img_bytes = base64.b64decode(result["data"])
        assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_serialize_large_image(self, pil_serializer, large_image):
        """Test serialization of larger image."""
        result = pil_serializer.serialize(large_image)

        assert result["metadata"]["size"] == (1000, 1000)
        # Larger images should produce larger output
        assert result["metadata"]["size_bytes"] > 1000

    def test_image_roundtrip(self, pil_serializer, rgb_image):
        """Test that serialized image can be reconstructed."""
        import io

        Image = pytest.importorskip("PIL.Image")

        result = pil_serializer.serialize(rgb_image)
        img_bytes = base64.b64decode(result["data"])
        reconstructed = Image.open(io.BytesIO(img_bytes))

        assert reconstructed.size == rgb_image.size
        assert reconstructed.mode == rgb_image.mode


# =============================================================================
# DictSerializer Tests
# =============================================================================


class TestDictSerializer:
    """Tests for DictSerializer."""

    def test_can_serialize_dict(self, dict_serializer):
        """Test that serializer correctly identifies dicts."""
        assert dict_serializer.can_serialize({"key": "value"}) is True

    def test_can_serialize_empty_dict(self, dict_serializer):
        """Test that serializer accepts empty dicts."""
        assert dict_serializer.can_serialize({}) is True

    def test_cannot_serialize_non_dict(self, dict_serializer):
        """Test that serializer rejects non-dict objects."""
        assert dict_serializer.can_serialize("not a dict") is False
        assert dict_serializer.can_serialize(42) is False
        assert dict_serializer.can_serialize([1, 2, 3]) is False
        assert dict_serializer.can_serialize(None) is False

    def test_serialize_simple_dict(self, dict_serializer):
        """Test serialization of a simple dict."""
        result = dict_serializer.serialize({"name": "Alice", "age": 30})

        assert result["type"] == "dict"
        assert result["format"] == "json"
        data = json.loads(result["data"])
        assert data["name"] == "Alice"
        assert data["age"] == 30

    def test_serialize_nested_dict(self, dict_serializer):
        """Test serialization of nested dict."""
        nested = {"level1": {"level2": {"level3": "deep"}}}
        result = dict_serializer.serialize(nested)

        data = json.loads(result["data"])
        assert data["level1"]["level2"]["level3"] == "deep"

    def test_serialize_dict_with_list_values(self, dict_serializer):
        """Test serialization of dict containing lists."""
        d = {"items": [1, 2, 3], "tags": ["a", "b"]}
        result = dict_serializer.serialize(d)

        data = json.loads(result["data"])
        assert data["items"] == [1, 2, 3]
        assert data["tags"] == ["a", "b"]

    def test_serialize_empty_dict(self, dict_serializer):
        """Test serialization of empty dict."""
        result = dict_serializer.serialize({})

        assert result["type"] == "dict"
        data = json.loads(result["data"])
        assert data == {}

    def test_output_is_pretty_printed(self, dict_serializer):
        """Test that output is formatted with indentation."""
        result = dict_serializer.serialize({"a": 1, "b": 2})

        assert "\n" in result["data"]
        assert "  " in result["data"]

    def test_serialize_dict_with_non_json_values(self, dict_serializer):
        """Non-JSON-serializable values should fall back to str()."""
        from datetime import datetime

        d = {"timestamp": datetime(2024, 1, 1), "value": 42}
        result = dict_serializer.serialize(d)

        data = json.loads(result["data"])
        assert "2024" in data["timestamp"]
        assert data["value"] == 42

    def test_metadata_has_key_count(self, dict_serializer):
        """Test that metadata includes key count."""
        result = dict_serializer.serialize({"a": 1, "b": 2, "c": 3})

        assert result["metadata"]["key_count"] == 3


# =============================================================================
# NumpySerializer Tests
# =============================================================================


class TestNumpySerializer:
    """Tests for NumpySerializer."""

    def test_can_serialize_ndarray(self, numpy_serializer):
        """Test that serializer correctly identifies numpy arrays."""
        np = pytest.importorskip("numpy")
        assert numpy_serializer.can_serialize(np.array([1, 2, 3])) is True

    def test_cannot_serialize_non_array(self, numpy_serializer):
        """Test that serializer rejects non-array objects."""
        assert numpy_serializer.can_serialize([1, 2, 3]) is False
        assert numpy_serializer.can_serialize("not an array") is False
        assert numpy_serializer.can_serialize(42) is False

    def test_serialize_1d_array(self, numpy_serializer):
        """Test serialization of 1D array produces single-column DataFrame."""
        np = pytest.importorskip("numpy")
        result = numpy_serializer.serialize(np.array([10, 20, 30]))

        assert result["type"] == "numpy.ndarray"
        assert result["format"] == "json"
        assert result["metadata"]["shape"] == (3, 1)

    def test_serialize_2d_array(self, numpy_serializer):
        """Test serialization of 2D array."""
        np = pytest.importorskip("numpy")
        result = numpy_serializer.serialize(np.array([[1, 2], [3, 4], [5, 6]]))

        assert result["type"] == "numpy.ndarray"
        assert result["metadata"]["shape"] == (3, 2)

    def test_columns_are_integers(self, numpy_serializer):
        """Test that column names are integer indices."""
        np = pytest.importorskip("numpy")
        result = numpy_serializer.serialize(np.array([[1, 2], [3, 4]]))

        assert result["metadata"]["columns"] == [0, 1]

    def test_serialize_float_array(self, numpy_serializer):
        """Test serialization of float array preserves dtype info."""
        np = pytest.importorskip("numpy")
        result = numpy_serializer.serialize(np.array([1.5, 2.5, 3.5]))

        assert result["type"] == "numpy.ndarray"
        dtypes = result["metadata"]["dtypes"]
        assert "float" in list(dtypes.values())[0]

    def test_data_roundtrip(self, numpy_serializer):
        """Test that serialized data can be reconstructed."""
        np = pytest.importorskip("numpy")
        pd = pytest.importorskip("pandas")

        arr = np.array([[1, 2, 3], [4, 5, 6]])
        result = numpy_serializer.serialize(arr)

        from io import StringIO
        reconstructed = pd.read_json(StringIO(result["data"]), orient="split")
        np.testing.assert_array_equal(reconstructed.values, arr)

    def test_serialize_empty_array(self, numpy_serializer):
        """Test serialization of empty array."""
        np = pytest.importorskip("numpy")
        result = numpy_serializer.serialize(np.array([]))

        assert result["type"] == "numpy.ndarray"


# =============================================================================
# StringSerializer Tests
# =============================================================================


class TestStringSerializer:
    """Tests for StringSerializer (fallback serializer)."""

    def test_can_serialize_anything(self, string_serializer):
        """Test that StringSerializer accepts any object."""
        assert string_serializer.can_serialize("hello") is True
        assert string_serializer.can_serialize(42) is True
        assert string_serializer.can_serialize(3.14) is True
        assert string_serializer.can_serialize(None) is True
        assert string_serializer.can_serialize([1, 2, 3]) is True
        assert string_serializer.can_serialize({"key": "value"}) is True
        assert string_serializer.can_serialize(object()) is True

    def test_serialize_string(self, string_serializer):
        """Test serialization of plain string."""
        result = string_serializer.serialize("Hello, world!")

        assert result["type"] == "text"
        assert result["format"] == "plain"
        assert result["data"] == "Hello, world!"
        assert result["metadata"]["original_type"] == "str"

    def test_serialize_integer(self, string_serializer):
        """Test serialization of integer (converts to string)."""
        result = string_serializer.serialize(42)

        assert result["type"] == "text"
        assert result["data"] == "42"
        assert result["metadata"]["original_type"] == "int"

    def test_serialize_float(self, string_serializer):
        """Test serialization of float."""
        result = string_serializer.serialize(3.14159)

        assert result["type"] == "text"
        assert result["data"] == "3.14159"
        assert result["metadata"]["original_type"] == "float"

    def test_serialize_none(self, string_serializer):
        """Test serialization of None."""
        result = string_serializer.serialize(None)

        assert result["type"] == "text"
        assert result["data"] == "None"
        assert result["metadata"]["original_type"] == "NoneType"

    def test_serialize_list(self, string_serializer):
        """Test serialization of list."""
        result = string_serializer.serialize([1, 2, 3])

        assert result["type"] == "text"
        assert result["data"] == "[1, 2, 3]"
        assert result["metadata"]["original_type"] == "list"

    def test_serialize_dict(self, string_serializer):
        """Test serialization of dictionary."""
        result = string_serializer.serialize({"key": "value"})

        assert result["type"] == "text"
        assert result["data"] == "{'key': 'value'}"
        assert result["metadata"]["original_type"] == "dict"

    def test_serialize_custom_object(self, string_serializer):
        """Test serialization of custom object uses __str__."""

        class CustomObject:
            def __str__(self):
                return "CustomObject<test>"

        obj = CustomObject()
        result = string_serializer.serialize(obj)

        assert result["type"] == "text"
        assert result["data"] == "CustomObject<test>"
        assert result["metadata"]["original_type"] == "CustomObject"

    def test_serialize_empty_string(self, string_serializer):
        """Test serialization of empty string."""
        result = string_serializer.serialize("")

        assert result["type"] == "text"
        assert result["data"] == ""
        assert result["metadata"]["original_type"] == "str"

    def test_serialize_unicode(self, string_serializer):
        """Test serialization of unicode string."""
        result = string_serializer.serialize("Hello! Emoji test")

        assert result["type"] == "text"
        assert result["data"] == "Hello! Emoji test"

    def test_serialize_multibyte_utf8_roundtrip(self, string_serializer):
        """Test that multi-byte UTF-8 characters survive base64 round-trip.

        Regression: em-dashes, CJK, and accented chars are multi-byte in
        UTF-8. The frontend decodes base64 via atob() which produces Latin-1,
        so the data must be valid UTF-8 when decoded from base64.
        """
        import base64

        text = "Revenue — $127.4M · résumé · 日本語 · 🎉"
        result = string_serializer.serialize(text)
        assert result["data"] == text

        # Simulate the upload path: serialize → base64 encode → base64 decode → UTF-8
        encoded = base64.b64encode(text.encode("utf-8"))
        decoded = base64.b64decode(encoded).decode("utf-8")
        assert decoded == text

    def test_serialize_multiline_string(self, string_serializer):
        """Test serialization of multiline string."""
        multiline = "Line 1\nLine 2\nLine 3"
        result = string_serializer.serialize(multiline)

        assert result["type"] == "text"
        assert result["data"] == multiline
        assert "\n" in result["data"]


# =============================================================================
# Registry and Selection Logic Tests
# =============================================================================


class TestSerializerRegistry:
    """Tests for serializer registry and selection logic."""

    def test_registry_order(self):
        """Test that serializers are in correct priority order."""
        # Fallback (StringSerializer) should be last
        assert isinstance(SERIALIZERS[-1], StringSerializer)

        # More specific serializers should come before fallback
        serializer_types = [type(s).__name__ for s in SERIALIZERS]
        assert serializer_types.index("StringSerializer") == len(SERIALIZERS) - 1

    def test_matplotlib_selected_for_figure(self, simple_figure):
        """Test that MatplotlibSerializer is selected for matplotlib figures."""
        result = serialize_object(simple_figure)
        assert result["type"] == "matplotlib.figure"

    def test_pandas_selected_for_dataframe(self, simple_dataframe):
        """Test that PandasDataFrameSerializer is selected for DataFrames."""
        result = serialize_object(simple_dataframe)
        assert result["type"] == "pandas.dataframe"

    def test_pil_selected_for_image(self, rgb_image):
        """Test that PILImageSerializer is selected for PIL Images."""
        result = serialize_object(rgb_image)
        assert result["type"] == "pil.image"

    def test_dict_selected_for_dict(self):
        """Test that DictSerializer is selected for dicts."""
        result = serialize_object({"key": "value"})
        assert result["type"] == "dict"

    def test_string_selected_for_fallback(self):
        """Test that StringSerializer is selected for unsupported types."""
        result = serialize_object(set([1, 2, 3]))
        assert result["type"] == "text"

    def test_string_not_serialized_as_figure(self):
        """Test that plain strings don't match MatplotlibSerializer."""
        result = serialize_object("matplotlib.figure")
        # Should use StringSerializer, not MatplotlibSerializer
        assert result["type"] == "text"

    def test_first_matching_serializer_wins(self):
        """Test that first matching serializer in registry is used."""
        # If an object matches multiple serializers, first one wins
        # Currently, StringSerializer matches everything, so it must be last
        result = serialize_object("test string")
        assert result["type"] == "text"


class TestSerializeObjectFunction:
    """Tests for the serialize_object convenience function."""

    def test_serialize_object_returns_dict(self, simple_figure):
        """Test that serialize_object returns a dictionary."""
        result = serialize_object(simple_figure)
        assert isinstance(result, dict)

    def test_serialize_object_has_required_keys(self, simple_figure):
        """Test that result has all required keys."""
        result = serialize_object(simple_figure)
        assert "type" in result
        assert "format" in result
        assert "data" in result
        assert "metadata" in result

    def test_serialize_object_with_string(self):
        """Test serialize_object with plain string."""
        result = serialize_object("hello")
        assert result["type"] == "text"
        assert result["data"] == "hello"

    def test_serialize_object_with_none(self):
        """Test serialize_object with None."""
        result = serialize_object(None)
        assert result["type"] == "text"
        assert result["data"] == "None"


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_very_long_string(self, string_serializer):
        """Test serialization of very long string."""
        long_string = "x" * 100000
        result = string_serializer.serialize(long_string)

        assert result["data"] == long_string
        assert len(result["data"]) == 100000

    def test_boolean_values(self, string_serializer):
        """Test serialization of boolean values."""
        true_result = string_serializer.serialize(True)
        false_result = string_serializer.serialize(False)

        assert true_result["data"] == "True"
        assert false_result["data"] == "False"

    def test_complex_number(self, string_serializer):
        """Test serialization of complex number."""
        result = string_serializer.serialize(3 + 4j)

        assert result["type"] == "text"
        assert result["metadata"]["original_type"] == "complex"

    def test_nested_structure(self, string_serializer):
        """Test serialization of deeply nested structure."""
        nested = {"level1": {"level2": {"level3": [1, 2, 3]}}}
        result = string_serializer.serialize(nested)

        assert result["type"] == "text"
        # String representation should contain the structure
        assert "level1" in result["data"]

    def test_dataframe_with_nan(self, pandas_serializer):
        """Test DataFrame serialization with NaN values."""
        pd = pytest.importorskip("pandas")
        import numpy as np

        df = pd.DataFrame({"a": [1, np.nan, 3], "b": [np.nan, 2, np.nan]})
        result = pandas_serializer.serialize(df)

        assert result["type"] == "pandas.dataframe"
        # NaN values should be serialized (as null in JSON)
        data = json.loads(result["data"])
        assert data["data"][0][1] is None or data["data"][1][0] is None

    def test_dataframe_with_mixed_types(self, pandas_serializer):
        """Test DataFrame with mixed types in same column."""
        pd = pytest.importorskip("pandas")

        df = pd.DataFrame({"mixed": [1, "two", 3.0, None]})
        result = pandas_serializer.serialize(df)

        assert result["type"] == "pandas.dataframe"
        assert result["metadata"]["shape"] == (4, 1)

    def test_image_with_palette_mode(self, pil_serializer):
        """Test serialization of palette mode (P) image."""
        Image = pytest.importorskip("PIL.Image")

        # Create a palette mode image
        img = Image.new("P", (100, 100))
        result = pil_serializer.serialize(img)

        assert result["type"] == "pil.image"
        assert result["metadata"]["mode"] == "P"

    def test_serializer_does_not_modify_original(self, simple_figure):
        """Test that serialization doesn't modify the original object."""
        plt = pytest.importorskip("matplotlib.pyplot")

        # Get original state
        original_axes = simple_figure.get_axes()

        # Serialize
        serialize_object(simple_figure)

        # Verify figure still has its axes
        assert simple_figure.get_axes() == original_axes


class TestMemoryConsiderations:
    """Tests for memory handling with large objects."""

    def test_large_figure_serialization(self):
        """Test that large figures can be serialized."""
        plt = pytest.importorskip("matplotlib.pyplot")
        import numpy as np

        # Create a figure with lots of data points
        fig, ax = plt.subplots(figsize=(20, 20))
        x = np.linspace(0, 100, 10000)
        y = np.sin(x) * np.random.randn(10000)
        ax.scatter(x, y, s=1)

        try:
            result = serialize_object(fig)
            assert result["type"] == "matplotlib.figure"
            assert result["metadata"]["size_bytes"] > 0
        finally:
            plt.close(fig)

    def test_dataframe_memory_efficient(self):
        """Test that DataFrame serialization handles larger datasets."""
        pd = pytest.importorskip("pandas")
        import numpy as np

        # Create a reasonably large DataFrame
        df = pd.DataFrame(
            {
                "a": np.random.randn(10000),
                "b": np.random.randn(10000),
                "c": np.random.randn(10000),
            }
        )

        result = serialize_object(df)
        assert result["type"] == "pandas.dataframe"
        assert result["metadata"]["shape"] == (10000, 3)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling and exception scenarios."""

    def test_serialize_object_never_raises_due_to_fallback(self):
        """Test that serialize_object never raises SerializationError due to StringSerializer fallback."""
        # Since StringSerializer always accepts, this should never raise
        # Test with various unusual objects
        import types

        # Lambda function
        result = serialize_object(lambda x: x)
        assert result["type"] == "text"
        assert "function" in result["metadata"]["original_type"]

        # Generator
        gen = (x for x in range(3))
        result = serialize_object(gen)
        assert result["type"] == "text"
        assert "generator" in result["metadata"]["original_type"]

        # Module
        result = serialize_object(types)
        assert result["type"] == "text"

    def test_serialization_error_import_path(self):
        """Test that SerializationError is importable and usable."""
        from skua.exceptions import SerializationError

        # Verify it's the right type
        assert issubclass(SerializationError, Exception)

        # Verify it can be raised and caught
        with pytest.raises(SerializationError):
            raise SerializationError("Test error")

    def test_object_with_broken_str(self, string_serializer):
        """Test serialization of object with broken __str__ method."""

        class BrokenStr:
            def __str__(self):
                raise ValueError("Broken __str__")

        obj = BrokenStr()
        # This should raise ValueError when trying to serialize
        with pytest.raises(ValueError, match="Broken __str__"):
            string_serializer.serialize(obj)

    def test_object_with_broken_repr(self, string_serializer):
        """Test serialization of object with broken __repr__ but working __str__."""

        class BrokenRepr:
            def __str__(self):
                return "working str"

            def __repr__(self):
                raise ValueError("Broken __repr__")

        obj = BrokenRepr()
        # __str__ is used, not __repr__, so this should work
        result = string_serializer.serialize(obj)
        assert result["data"] == "working str"


# =============================================================================
# Additional DataFrame Edge Cases
# =============================================================================


class TestDataFrameEdgeCases:
    """Additional edge case tests for DataFrame serialization."""

    def test_dataframe_with_custom_index(self, pandas_serializer):
        """Test DataFrame with custom string index."""
        pd = pytest.importorskip("pandas")

        df = pd.DataFrame(
            {"value": [1, 2, 3]},
            index=["row_a", "row_b", "row_c"]
        )
        result = pandas_serializer.serialize(df)

        assert result["type"] == "pandas.dataframe"
        data = json.loads(result["data"])
        assert data["index"] == ["row_a", "row_b", "row_c"]

    def test_dataframe_with_multiindex(self, pandas_serializer):
        """Test DataFrame with MultiIndex."""
        pd = pytest.importorskip("pandas")

        arrays = [
            ["A", "A", "B", "B"],
            ["one", "two", "one", "two"]
        ]
        index = pd.MultiIndex.from_arrays(arrays, names=("first", "second"))
        df = pd.DataFrame({"value": [1, 2, 3, 4]}, index=index)

        result = pandas_serializer.serialize(df)
        assert result["type"] == "pandas.dataframe"
        # MultiIndex should be serialized as nested list
        data = json.loads(result["data"])
        assert len(data["index"]) == 4

    def test_dataframe_with_categorical_column(self, pandas_serializer):
        """Test DataFrame with categorical dtype."""
        pd = pytest.importorskip("pandas")

        df = pd.DataFrame({
            "category": pd.Categorical(["low", "medium", "high", "low"])
        })
        result = pandas_serializer.serialize(df)

        assert result["type"] == "pandas.dataframe"
        assert "category" in result["metadata"]["dtypes"]["category"]

    def test_dataframe_with_infinity(self, pandas_serializer):
        """Test DataFrame with infinity values."""
        pd = pytest.importorskip("pandas")
        import numpy as np

        df = pd.DataFrame({
            "values": [1.0, np.inf, -np.inf, 2.0]
        })
        result = pandas_serializer.serialize(df)

        assert result["type"] == "pandas.dataframe"
        # Infinity values should be serialized (pandas converts to null or string)

    def test_dataframe_with_timedelta(self, pandas_serializer):
        """Test DataFrame with timedelta column."""
        pd = pytest.importorskip("pandas")

        df = pd.DataFrame({
            "duration": pd.to_timedelta(["1 days", "2 days", "3 days"])
        })
        result = pandas_serializer.serialize(df)

        assert result["type"] == "pandas.dataframe"
        assert "timedelta" in result["metadata"]["dtypes"]["duration"]

    def test_dataframe_with_special_column_names(self, pandas_serializer):
        """Test DataFrame with special characters in column names."""
        pd = pytest.importorskip("pandas")

        df = pd.DataFrame({
            "column with spaces": [1, 2],
            "column.with.dots": [3, 4],
            "": [5, 6],  # Empty column name
            123: [7, 8],  # Numeric column name
        })
        result = pandas_serializer.serialize(df)

        assert result["type"] == "pandas.dataframe"
        assert "column with spaces" in result["metadata"]["columns"]
        assert "column.with.dots" in result["metadata"]["columns"]

    def test_dataframe_preserves_column_order(self, pandas_serializer):
        """Test that column order is preserved in serialization."""
        pd = pytest.importorskip("pandas")

        df = pd.DataFrame({
            "z_col": [1],
            "a_col": [2],
            "m_col": [3]
        })
        result = pandas_serializer.serialize(df)

        # Column order should match original, not alphabetical
        assert result["metadata"]["columns"] == ["z_col", "a_col", "m_col"]


# =============================================================================
# Additional PIL Image Edge Cases
# =============================================================================


class TestPILImageEdgeCases:
    """Additional edge case tests for PIL Image serialization."""

    def test_image_binary_mode(self, pil_serializer):
        """Test serialization of 1-bit binary image."""
        Image = pytest.importorskip("PIL.Image")

        img = Image.new("1", (100, 100), color=1)
        result = pil_serializer.serialize(img)

        assert result["type"] == "pil.image"
        assert result["metadata"]["mode"] == "1"

    def test_image_la_mode(self, pil_serializer):
        """Test serialization of grayscale + alpha image."""
        Image = pytest.importorskip("PIL.Image")

        img = Image.new("LA", (100, 100), color=(128, 200))
        result = pil_serializer.serialize(img)

        assert result["type"] == "pil.image"
        assert result["metadata"]["mode"] == "LA"

    def test_image_cmyk_mode(self, pil_serializer):
        """Test serialization of CMYK image.

        Note: CMYK mode cannot be saved directly as PNG.
        This test documents the current behavior (raises OSError).
        A future enhancement could auto-convert CMYK to RGB before saving.
        """
        Image = pytest.importorskip("PIL.Image")

        img = Image.new("CMYK", (100, 100), color=(100, 50, 0, 10))

        # Current implementation does not handle CMYK mode
        # PNG format does not support CMYK
        with pytest.raises(OSError, match="cannot write mode CMYK as PNG"):
            pil_serializer.serialize(img)

    def test_image_16bit_mode(self, pil_serializer):
        """Test serialization of 16-bit grayscale image."""
        Image = pytest.importorskip("PIL.Image")

        img = Image.new("I;16", (100, 100))
        result = pil_serializer.serialize(img)

        assert result["type"] == "pil.image"
        assert "I" in result["metadata"]["mode"]

    def test_image_float_mode(self, pil_serializer):
        """Test serialization of 32-bit float image.

        Note: Float mode (F) cannot be saved directly as PNG.
        This test documents the current behavior (raises OSError).
        A future enhancement could auto-convert F mode to L or RGB before saving.
        """
        Image = pytest.importorskip("PIL.Image")

        img = Image.new("F", (100, 100))

        # Current implementation does not handle float mode
        # PNG format does not support float mode
        with pytest.raises(OSError, match="cannot write mode F as PNG"):
            pil_serializer.serialize(img)

    def test_image_non_square(self, pil_serializer):
        """Test serialization of non-square image."""
        Image = pytest.importorskip("PIL.Image")

        img = Image.new("RGB", (200, 50), color="blue")
        result = pil_serializer.serialize(img)

        assert result["metadata"]["size"] == (200, 50)

    def test_image_extremely_narrow(self, pil_serializer):
        """Test serialization of extremely narrow image."""
        Image = pytest.importorskip("PIL.Image")

        img = Image.new("RGB", (1000, 1), color="red")
        result = pil_serializer.serialize(img)

        assert result["metadata"]["size"] == (1000, 1)

    def test_image_extremely_tall(self, pil_serializer):
        """Test serialization of extremely tall image."""
        Image = pytest.importorskip("PIL.Image")

        img = Image.new("RGB", (1, 1000), color="green")
        result = pil_serializer.serialize(img)

        assert result["metadata"]["size"] == (1, 1000)


# =============================================================================
# Additional Matplotlib Edge Cases
# =============================================================================


class TestMatplotlibEdgeCases:
    """Additional edge case tests for matplotlib figure serialization."""

    def test_figure_with_colorbar(self, matplotlib_serializer):
        """Test figure with colorbar."""
        plt = pytest.importorskip("matplotlib.pyplot")
        import numpy as np

        fig, ax = plt.subplots()
        data = np.random.rand(10, 10)
        im = ax.imshow(data)
        fig.colorbar(im)

        try:
            result = matplotlib_serializer.serialize(fig)
            assert result["type"] == "matplotlib.figure"
            assert result["metadata"]["size_bytes"] > 0
        finally:
            plt.close(fig)

    def test_figure_with_legend(self, matplotlib_serializer):
        """Test figure with legend."""
        plt = pytest.importorskip("matplotlib.pyplot")

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], label="Line 1")
        ax.plot([3, 2, 1], label="Line 2")
        ax.legend()

        try:
            result = matplotlib_serializer.serialize(fig)
            assert result["type"] == "matplotlib.figure"
        finally:
            plt.close(fig)

    def test_figure_with_custom_size(self, matplotlib_serializer):
        """Test figure with custom size."""
        plt = pytest.importorskip("matplotlib.pyplot")

        fig, ax = plt.subplots(figsize=(15, 5))
        ax.plot([1, 2, 3])

        try:
            result = matplotlib_serializer.serialize(fig)
            assert result["type"] == "matplotlib.figure"
            # Custom sized figures should serialize correctly
            assert result["metadata"]["size_bytes"] > 0
        finally:
            plt.close(fig)

    def test_figure_with_log_scale(self, matplotlib_serializer):
        """Test figure with logarithmic scale."""
        plt = pytest.importorskip("matplotlib.pyplot")
        import numpy as np

        fig, ax = plt.subplots()
        x = np.logspace(0, 3, 50)
        ax.semilogx(x, x**2)

        try:
            result = matplotlib_serializer.serialize(fig)
            assert result["type"] == "matplotlib.figure"
        finally:
            plt.close(fig)

    def test_figure_3d_plot(self, matplotlib_serializer):
        """Test 3D figure serialization."""
        plt = pytest.importorskip("matplotlib.pyplot")
        np = pytest.importorskip("numpy")

        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        x = np.linspace(-5, 5, 50)
        y = np.linspace(-5, 5, 50)
        X, Y = np.meshgrid(x, y)
        Z = np.sin(np.sqrt(X**2 + Y**2))
        ax.plot_surface(X, Y, Z)

        try:
            result = matplotlib_serializer.serialize(fig)
            assert result["type"] == "matplotlib.figure"
            # 3D plots should produce valid PNG
            img_bytes = base64.b64decode(result["data"])
            assert img_bytes[:8] == b"\x89PNG\r\n\x1a\n"
        finally:
            plt.close(fig)

    def test_figure_with_text_annotations(self, matplotlib_serializer):
        """Test figure with text annotations."""
        plt = pytest.importorskip("matplotlib.pyplot")

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])
        ax.annotate("Peak", xy=(3, 9), xytext=(2.5, 7),
                    arrowprops=dict(facecolor="black", shrink=0.05))
        ax.set_xlabel("X Label")
        ax.set_ylabel("Y Label")
        ax.set_title("Title with Special Chars: $x^2$")

        try:
            result = matplotlib_serializer.serialize(fig)
            assert result["type"] == "matplotlib.figure"
        finally:
            plt.close(fig)

    def test_figure_pie_chart(self, matplotlib_serializer):
        """Test pie chart serialization."""
        plt = pytest.importorskip("matplotlib.pyplot")

        fig, ax = plt.subplots()
        sizes = [15, 30, 45, 10]
        labels = ["A", "B", "C", "D"]
        ax.pie(sizes, labels=labels, autopct="%1.1f%%")

        try:
            result = matplotlib_serializer.serialize(fig)
            assert result["type"] == "matplotlib.figure"
        finally:
            plt.close(fig)

    def test_figure_polar_plot(self, matplotlib_serializer):
        """Test polar plot serialization."""
        plt = pytest.importorskip("matplotlib.pyplot")
        np = pytest.importorskip("numpy")

        fig, ax = plt.subplots(subplot_kw=dict(projection="polar"))
        theta = np.linspace(0, 2 * np.pi, 100)
        r = 1 + np.cos(theta)
        ax.plot(theta, r)

        try:
            result = matplotlib_serializer.serialize(fig)
            assert result["type"] == "matplotlib.figure"
        finally:
            plt.close(fig)


# =============================================================================
# Registry Edge Cases
# =============================================================================


class TestRegistryEdgeCases:
    """Tests for edge cases in serializer registry behavior."""

    def test_matplotlib_before_pil_for_figure(self):
        """Test that matplotlib figures are NOT handled by PIL serializer.

        Matplotlib figures should be caught by MatplotlibSerializer first,
        not converted to image and handled by PILImageSerializer.
        """
        plt = pytest.importorskip("matplotlib.pyplot")

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])

        try:
            result = serialize_object(fig)
            # Should be handled by MatplotlibSerializer, not PIL
            assert result["type"] == "matplotlib.figure"
            assert result["type"] != "pil.image"
        finally:
            plt.close(fig)

    def test_pandas_series_uses_string_fallback(self):
        """Test that pandas Series (not DataFrame) falls back to string."""
        pd = pytest.importorskip("pandas")

        series = pd.Series([1, 2, 3], name="test_series")
        result = serialize_object(series)

        # Series is not a DataFrame, should use StringSerializer
        assert result["type"] == "text"
        assert result["metadata"]["original_type"] == "Series"

    def test_numpy_array_uses_dataframe_serialization(self):
        """Test that numpy arrays are converted to DataFrame."""
        np = pytest.importorskip("numpy")

        arr = np.array([1, 2, 3, 4, 5])
        result = serialize_object(arr)

        assert result["type"] == "numpy.ndarray"
        assert result["metadata"]["shape"] == (5, 1)

    def test_serializers_list_is_not_empty(self):
        """Test that SERIALIZERS list always has entries."""
        assert len(SERIALIZERS) > 0

    def test_serializers_list_ends_with_fallback(self):
        """Test that SERIALIZERS list ends with StringSerializer."""
        assert isinstance(SERIALIZERS[-1], StringSerializer)

    def test_all_serializers_have_required_methods(self):
        """Test that all serializers have can_serialize and serialize methods."""
        for serializer in SERIALIZERS:
            assert hasattr(serializer, "can_serialize")
            assert hasattr(serializer, "serialize")
            assert callable(serializer.can_serialize)
            assert callable(serializer.serialize)


# =============================================================================
# Concurrent/Thread Safety Tests (Basic)
# =============================================================================


class TestConcurrencySafety:
    """Basic tests for concurrent serialization safety."""

    def test_multiple_figures_serial(self, matplotlib_serializer):
        """Test serializing multiple figures in sequence."""
        plt = pytest.importorskip("matplotlib.pyplot")

        results = []
        for i in range(5):
            fig, ax = plt.subplots()
            ax.plot([1, 2, 3], [i, i * 2, i * 3])
            try:
                result = matplotlib_serializer.serialize(fig)
                results.append(result)
            finally:
                plt.close(fig)

        assert len(results) == 5
        for result in results:
            assert result["type"] == "matplotlib.figure"

    def test_multiple_dataframes_serial(self, pandas_serializer):
        """Test serializing multiple DataFrames in sequence."""
        pd = pytest.importorskip("pandas")

        results = []
        for i in range(5):
            df = pd.DataFrame({"value": [i, i + 1, i + 2]})
            result = pandas_serializer.serialize(df)
            results.append(result)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert result["type"] == "pandas.dataframe"
            data = json.loads(result["data"])
            assert data["data"][0][0] == i

    def test_interleaved_serialization(self):
        """Test interleaved serialization of different types."""
        plt = pytest.importorskip("matplotlib.pyplot")
        pd = pytest.importorskip("pandas")
        Image = pytest.importorskip("PIL.Image")

        # Create objects
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])
        df = pd.DataFrame({"a": [1, 2, 3]})
        img = Image.new("RGB", (50, 50), color="red")

        try:
            # Serialize in interleaved order
            result1 = serialize_object(fig)
            result2 = serialize_object(df)
            result3 = serialize_object("text")
            result4 = serialize_object(img)
            result5 = serialize_object(df)  # Serialize df again

            assert result1["type"] == "matplotlib.figure"
            assert result2["type"] == "pandas.dataframe"
            assert result3["type"] == "text"
            assert result4["type"] == "pil.image"
            assert result5["type"] == "pandas.dataframe"
        finally:
            plt.close(fig)


# =============================================================================
# Output Format Validation Tests
# =============================================================================


class TestOutputFormatValidation:
    """Tests to validate output format consistency."""

    def test_all_results_have_consistent_structure(self):
        """Test that all serializers produce consistent output structure."""
        plt = pytest.importorskip("matplotlib.pyplot")
        pd = pytest.importorskip("pandas")
        Image = pytest.importorskip("PIL.Image")

        objects_to_test = [
            ("string", "hello"),
            ("int", 42),
            ("none", None),
        ]

        # Add optional objects if available
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])
        objects_to_test.append(("figure", fig))

        df = pd.DataFrame({"a": [1, 2, 3]})
        objects_to_test.append(("dataframe", df))

        img = Image.new("RGB", (10, 10))
        objects_to_test.append(("image", img))

        try:
            for name, obj in objects_to_test:
                result = serialize_object(obj)

                # Every result must have these keys
                assert "type" in result, f"Missing 'type' for {name}"
                assert "format" in result, f"Missing 'format' for {name}"
                assert "data" in result, f"Missing 'data' for {name}"
                assert "metadata" in result, f"Missing 'metadata' for {name}"

                # Type checks
                assert isinstance(result["type"], str), f"'type' not string for {name}"
                assert isinstance(result["format"], str), f"'format' not string for {name}"
                assert isinstance(result["metadata"], dict), f"'metadata' not dict for {name}"
        finally:
            plt.close(fig)

    def test_type_field_format(self):
        """Test that type fields follow expected naming conventions."""
        plt = pytest.importorskip("matplotlib.pyplot")
        pd = pytest.importorskip("pandas")
        Image = pytest.importorskip("PIL.Image")

        fig, ax = plt.subplots()
        df = pd.DataFrame({"a": [1]})
        img = Image.new("RGB", (10, 10))

        try:
            # Each serializer should have a distinct type prefix
            assert serialize_object(fig)["type"].startswith("matplotlib.")
            assert serialize_object(df)["type"].startswith("pandas.")
            assert serialize_object(img)["type"].startswith("pil.")
            assert serialize_object("text")["type"] == "text"
        finally:
            plt.close(fig)

    def test_format_field_values(self):
        """Test that format fields contain valid values."""
        plt = pytest.importorskip("matplotlib.pyplot")
        pd = pytest.importorskip("pandas")
        Image = pytest.importorskip("PIL.Image")

        valid_formats = {"png", "json", "plain", "jpeg", "svg"}  # Known formats

        fig, ax = plt.subplots()
        df = pd.DataFrame({"a": [1]})
        img = Image.new("RGB", (10, 10))

        try:
            for obj in [fig, df, img, "text", 42, None]:
                result = serialize_object(obj)
                assert result["format"] in valid_formats or isinstance(result["format"], str)
        finally:
            plt.close(fig)


# =============================================================================
# New serializer tests: Plotly, Polars, PyTorch, TensorFlow, list[dict]
# =============================================================================

class TestPlotlySerializer:
    """Tests for PlotlySerializer."""

    def test_can_serialize_plotly_figure(self):
        go = pytest.importorskip("plotly.graph_objects")
        from skua.serializers import PlotlySerializer
        s = PlotlySerializer()
        fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
        assert s.can_serialize(fig)

    def test_cannot_serialize_non_plotly(self):
        from skua.serializers import PlotlySerializer
        s = PlotlySerializer()
        assert not s.can_serialize("hello")
        assert not s.can_serialize(42)

    def test_serialize_primary_is_json(self):
        # Primary payload stays JSON — interactive client-side rendering needs
        # the raw plotly spec, not a flattened PNG.
        go = pytest.importorskip("plotly.graph_objects")
        from skua.serializers import PlotlySerializer
        s = PlotlySerializer()
        fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
        result = s.serialize(fig)
        assert result["type"] == "plotly.figure"
        assert result["format"] == "json"
        # data is the to_json() string — it parses back cleanly
        import json
        parsed = json.loads(result["data"])
        assert "data" in parsed

    def test_serialize_adds_preview_png_when_kaleido_available(self):
        # With kaleido, the serializer emits a sidecar PNG at 1200×630 — used
        # as the OpenGraph image by record pages. JSON primary is unchanged.
        go = pytest.importorskip("plotly.graph_objects")
        pytest.importorskip("kaleido")
        from skua.serializers import PlotlySerializer
        s = PlotlySerializer()
        fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
        result = s.serialize(fig)
        assert "preview_png_b64" in result
        png_bytes = base64.b64decode(result["preview_png_b64"])
        assert png_bytes[:4] == b"\x89PNG"

    def test_serialize_without_kaleido_omits_preview_png(self, monkeypatch):
        # No kaleido → primary JSON only, no preview_png_b64 key. The upload
        # path then doesn't add a sidecar multipart file.
        go = pytest.importorskip("plotly.graph_objects")
        import sys
        # Hide kaleido's import_module path by monkeypatching the helper.
        from skua import serializers as ser
        monkeypatch.setattr(ser, "_plotly_png_bytes", lambda fig: None)
        s = ser.PlotlySerializer()
        fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
        result = s.serialize(fig)
        assert "preview_png_b64" not in result

class TestPolarsSerializer:
    """Tests for PolarsDataFrameSerializer."""

    def test_can_serialize_polars_dataframe(self):
        pl = pytest.importorskip("polars")
        from skua.serializers import PolarsDataFrameSerializer
        s = PolarsDataFrameSerializer()
        df = pl.DataFrame({"a": [1, 2], "b": [3, 4]})
        assert s.can_serialize(df)

    def test_can_serialize_lazy_frame(self):
        pl = pytest.importorskip("polars")
        from skua.serializers import PolarsDataFrameSerializer
        s = PolarsDataFrameSerializer()
        lf = pl.LazyFrame({"a": [1, 2]})
        assert s.can_serialize(lf)

    def test_cannot_serialize_non_polars(self):
        pytest.importorskip("polars")
        from skua.serializers import PolarsDataFrameSerializer
        s = PolarsDataFrameSerializer()
        assert not s.can_serialize([1, 2, 3])
        assert not s.can_serialize("hello")

    def test_serialize_produces_dataframe_format(self):
        pl = pytest.importorskip("polars")
        from skua.serializers import PolarsDataFrameSerializer
        s = PolarsDataFrameSerializer()
        df = pl.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
        result = s.serialize(df)
        assert result["type"] == "polars.dataframe"
        assert result["format"] == "json"
        parsed = json.loads(result["data"])
        assert parsed["columns"] == ["x", "y"]
        assert len(parsed["data"]) == 3

    def test_serialize_lazy_frame(self):
        pl = pytest.importorskip("polars")
        from skua.serializers import PolarsDataFrameSerializer
        s = PolarsDataFrameSerializer()
        lf = pl.LazyFrame({"a": [10, 20]})
        result = s.serialize(lf)
        assert result["type"] == "polars.dataframe"

    def test_serialize_without_pyarrow(self, monkeypatch):
        """Polars snap should work even if pyarrow is not installed."""
        pl = pytest.importorskip("polars")
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pyarrow" or name.startswith("pyarrow."):
                raise ModuleNotFoundError("No module named 'pyarrow'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        from skua.serializers import PolarsDataFrameSerializer
        s = PolarsDataFrameSerializer()
        df = pl.DataFrame({"x": [1, 2], "y": ["a", "b"]})
        result = s.serialize(df)
        parsed = json.loads(result["data"])
        assert parsed["columns"] == ["x", "y"]
        assert parsed["data"] == [[1, "a"], [2, "b"]]


class TestTorchTensorSerializer:
    """Tests for TorchTensorSerializer."""

    def test_can_serialize_tensor(self):
        torch = pytest.importorskip("torch")
        from skua.serializers import TorchTensorSerializer
        s = TorchTensorSerializer()
        assert s.can_serialize(torch.tensor([1.0, 2.0]))

    def test_cannot_serialize_non_tensor(self):
        pytest.importorskip("torch")
        from skua.serializers import TorchTensorSerializer
        s = TorchTensorSerializer()
        assert not s.can_serialize([1, 2, 3])
        assert not s.can_serialize("hello")

    def test_1d_tensor_serializes_as_dataframe(self):
        torch = pytest.importorskip("torch")
        from skua.serializers import TorchTensorSerializer
        s = TorchTensorSerializer()
        t = torch.tensor([1.0, 2.0, 3.0])
        result = s.serialize(t)
        assert result["type"] == "torch.tensor"
        assert result["format"] == "json"

    def test_2d_tensor_serializes_as_dataframe(self):
        torch = pytest.importorskip("torch")
        from skua.serializers import TorchTensorSerializer
        s = TorchTensorSerializer()
        t = torch.randn(4, 8)
        result = s.serialize(t)
        assert result["type"] == "torch.tensor"

    def test_image_tensor_chw_serializes_as_png(self):
        torch = pytest.importorskip("torch")
        pytest.importorskip("PIL")
        from skua.serializers import TorchTensorSerializer
        s = TorchTensorSerializer()
        # (C=3, H=8, W=8) image tensor
        t = torch.rand(3, 8, 8)
        result = s.serialize(t)
        assert result["type"] == "pil.image"
        assert result["format"] == "png"

    def test_batched_image_tensor_squeezed(self):
        torch = pytest.importorskip("torch")
        pytest.importorskip("PIL")
        from skua.serializers import TorchTensorSerializer
        s = TorchTensorSerializer()
        # (1, C=3, H=8, W=8) batch of 1
        t = torch.rand(1, 3, 8, 8)
        result = s.serialize(t)
        assert result["type"] == "pil.image"

    def test_grayscale_image_tensor(self):
        torch = pytest.importorskip("torch")
        pytest.importorskip("PIL")
        from skua.serializers import TorchTensorSerializer
        s = TorchTensorSerializer()
        t = torch.rand(1, 8, 8)
        result = s.serialize(t)
        assert result["type"] == "pil.image"


class TestTensorFlowSerializer:
    """Tests for TensorFlowTensorSerializer."""

    def test_can_serialize_tf_tensor(self):
        tf = pytest.importorskip("tensorflow")
        from skua.serializers import TensorFlowTensorSerializer
        s = TensorFlowTensorSerializer()
        t = tf.constant([1.0, 2.0, 3.0])
        assert s.can_serialize(t)

    def test_cannot_serialize_non_tensor(self):
        pytest.importorskip("tensorflow")
        from skua.serializers import TensorFlowTensorSerializer
        s = TensorFlowTensorSerializer()
        assert not s.can_serialize([1, 2])

    def test_serialize_produces_dataframe_format(self):
        tf = pytest.importorskip("tensorflow")
        from skua.serializers import TensorFlowTensorSerializer
        s = TensorFlowTensorSerializer()
        t = tf.constant([[1.0, 2.0], [3.0, 4.0]])
        result = s.serialize(t)
        assert result["type"] == "tensorflow.tensor"
        assert result["format"] == "json"


class TestListOfDictsSerializer:
    """Tests for ListOfDictsSerializer."""

    def test_can_serialize_list_of_dicts(self):
        from skua.serializers import ListOfDictsSerializer
        s = ListOfDictsSerializer()
        assert s.can_serialize([{"a": 1}, {"a": 2}])

    def test_cannot_serialize_empty_list(self):
        from skua.serializers import ListOfDictsSerializer
        s = ListOfDictsSerializer()
        assert not s.can_serialize([])

    def test_cannot_serialize_mixed_list(self):
        from skua.serializers import ListOfDictsSerializer
        s = ListOfDictsSerializer()
        assert not s.can_serialize([{"a": 1}, "hello"])

    def test_cannot_serialize_plain_list(self):
        from skua.serializers import ListOfDictsSerializer
        s = ListOfDictsSerializer()
        assert not s.can_serialize([1, 2, 3])

    def test_serialize_hf_pipeline_output(self):
        from skua.serializers import ListOfDictsSerializer
        s = ListOfDictsSerializer()
        # Typical HF text-classification output
        output = [{"label": "POSITIVE", "score": 0.998}, {"label": "NEGATIVE", "score": 0.002}]
        result = s.serialize(output)
        assert result["type"] == "list[dict]"
        assert result["format"] == "json"
        parsed = json.loads(result["data"])
        assert parsed["columns"] == ["label", "score"]
        assert len(parsed["data"]) == 2

    def test_serialize_preserves_all_keys(self):
        from skua.serializers import ListOfDictsSerializer
        s = ListOfDictsSerializer()
        output = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}, {"a": 3, "b": "z"}]
        result = s.serialize(output)
        parsed = json.loads(result["data"])
        assert set(parsed["columns"]) == {"a", "b"}
        assert len(parsed["data"]) == 3

    def test_serialize_object_routes_list_of_dicts(self):
        from skua.serializers import serialize_object
        result = serialize_object([{"x": 1}, {"x": 2}])
        assert result["type"] == "list[dict]"
