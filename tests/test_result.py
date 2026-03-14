"""Tests for RecordResult class."""

import pytest

from skua.result import RecordResult


class TestRecordResultBasics:
    """Test basic RecordResult functionality."""

    def test_stores_url_and_metadata(self):
        """Test that RecordResult stores URL and metadata."""
        obj = {"data": [1, 2, 3]}
        url = "https://skua.dev/f/abc123"
        metadata = {"id": "abc123", "title": "Test", "tags": []}

        result = RecordResult(obj=obj, url=url, metadata=metadata)

        assert result.url == url
        assert result.metadata == metadata

    def test_repr_returns_object_repr(self):
        """Test that __repr__ delegates to wrapped object."""
        obj = [1, 2, 3]
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert repr(result) == repr(obj)
        assert repr(result) == "[1, 2, 3]"

    def test_str_returns_object_str(self):
        """Test that __str__ delegates to wrapped object."""
        obj = {"a": 1, "b": 2}
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert str(result) == str(obj)


class TestRecordResultNotebookDisplay:
    """Test Jupyter notebook display methods."""

    def test_repr_html_delegates_to_object(self):
        """Test _repr_html_ delegation."""

        class HTMLObject:
            def _repr_html_(self):
                return "<b>Hello</b>"

        obj = HTMLObject()
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert result._repr_html_() == "<b>Hello</b>"

    def test_repr_html_returns_none_if_not_supported(self):
        """Test _repr_html_ returns None for objects without HTML repr."""
        obj = [1, 2, 3]
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert result._repr_html_() is None

    def test_repr_png_delegates_to_object(self):
        """Test _repr_png_ delegation."""

        class PNGObject:
            def _repr_png_(self):
                return b"PNG_DATA"

        obj = PNGObject()
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert result._repr_png_() == b"PNG_DATA"

    def test_repr_svg_delegates_to_object(self):
        """Test _repr_svg_ delegation."""

        class SVGObject:
            def _repr_svg_(self):
                return "<svg>...</svg>"

        obj = SVGObject()
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert result._repr_svg_() == "<svg>...</svg>"

    def test_repr_json_delegates_to_object(self):
        """Test _repr_json_ delegation."""

        class JSONObject:
            def _repr_json_(self):
                return {"data": [1, 2, 3]}

        obj = JSONObject()
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert result._repr_json_() == {"data": [1, 2, 3]}


class TestRecordResultAttributeAccess:
    """Test transparent attribute access to wrapped object."""

    def test_getattr_delegates_to_object(self):
        """Test that attributes are accessed from wrapped object."""

        class MyObject:
            def __init__(self):
                self.value = 42

            def method(self):
                return "called"

        obj = MyObject()
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert result.value == 42
        assert result.method() == "called"

    def test_getitem_delegates_to_object(self):
        """Test that indexing works on wrapped object."""
        obj = {"a": 1, "b": 2, "c": 3}
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert result["a"] == 1
        assert result["b"] == 2

    def test_len_delegates_to_object(self):
        """Test that len() works on wrapped object."""
        obj = [1, 2, 3, 4, 5]
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert len(result) == 5

    def test_iter_delegates_to_object(self):
        """Test that iteration works on wrapped object."""
        obj = [1, 2, 3]
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        items = list(result)
        assert items == [1, 2, 3]

    def test_contains_delegates_to_object(self):
        """Test that 'in' operator works on wrapped object."""
        obj = [1, 2, 3]
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert 2 in result
        assert 5 not in result


class TestRecordResultComparison:
    """Test comparison operators."""

    def test_equality_with_object(self):
        """Test equality comparison with unwrapped object."""
        obj = [1, 2, 3]
        result = RecordResult(obj=obj, url="https://skua.dev/f/abc", metadata={})

        assert result == [1, 2, 3]
        assert result != [1, 2, 4]

    def test_equality_with_record_result(self):
        """Test equality comparison between RecordResults."""
        obj1 = [1, 2, 3]
        obj2 = [1, 2, 3]
        obj3 = [4, 5, 6]

        result1 = RecordResult(obj=obj1, url="https://skua.dev/f/abc", metadata={})
        result2 = RecordResult(obj=obj2, url="https://skua.dev/f/def", metadata={})
        result3 = RecordResult(obj=obj3, url="https://skua.dev/f/ghi", metadata={})

        assert result1 == result2  # Same wrapped object
        assert result1 != result3  # Different wrapped object

    def test_comparison_operators(self):
        """Test less-than, greater-than operators."""
        result1 = RecordResult(obj=5, url="https://skua.dev/f/abc", metadata={})
        result2 = RecordResult(obj=10, url="https://skua.dev/f/def", metadata={})

        assert result1 < result2
        assert result1 <= result2
        assert result2 > result1
        assert result2 >= result1

        # Compare with unwrapped values
        assert result1 < 10
        assert result2 > 5


class TestRecordResultArithmetic:
    """Test arithmetic operators."""

    def test_addition(self):
        """Test addition operator."""
        result = RecordResult(obj=5, url="https://skua.dev/f/abc", metadata={})

        assert result + 3 == 8
        assert result + result == 10

    def test_subtraction(self):
        """Test subtraction operator."""
        result = RecordResult(obj=10, url="https://skua.dev/f/abc", metadata={})

        assert result - 3 == 7
        assert result - result == 0

    def test_multiplication(self):
        """Test multiplication operator."""
        result = RecordResult(obj=5, url="https://skua.dev/f/abc", metadata={})

        assert result * 2 == 10
        assert result * result == 25

    def test_division(self):
        """Test division operator."""
        result = RecordResult(obj=10, url="https://skua.dev/f/abc", metadata={})

        assert result / 2 == 5
        assert result / result == 1

    def test_floor_division(self):
        """Test floor division operator."""
        result = RecordResult(obj=10, url="https://skua.dev/f/abc", metadata={})

        assert result // 3 == 3

    def test_modulo(self):
        """Test modulo operator."""
        result = RecordResult(obj=10, url="https://skua.dev/f/abc", metadata={})

        assert result % 3 == 1

    def test_power(self):
        """Test power operator."""
        result = RecordResult(obj=2, url="https://skua.dev/f/abc", metadata={})

        assert result**3 == 8


class TestRecordResultWithDataFrame:
    """Test RecordResult with pandas DataFrame (if available)."""

    def test_dataframe_operations(self):
        """Test that DataFrame operations work through RecordResult."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result = RecordResult(obj=df, url="https://skua.dev/f/abc", metadata={})

        # Test column access
        assert list(result["a"]) == [1, 2, 3]

        # Test method call
        assert result.shape == (3, 2)

        # Test _repr_html_ (DataFrames have this)
        html = result._repr_html_()
        assert html is not None
        assert "<table" in html


class TestRecordResultWithMatplotlib:
    """Test RecordResult with matplotlib Figure (if available)."""

    def test_figure_has_repr_png(self):
        """Test that Figure objects expose _repr_png_ if matplotlib supports it."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            pytest.skip("matplotlib not installed")

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])

        result = RecordResult(obj=fig, url="https://skua.dev/f/abc", metadata={})

        # Matplotlib figures may have _repr_png_ depending on backend
        # Test that RecordResult properly delegates if the method exists
        if hasattr(fig, "_repr_png_"):
            png_data = result._repr_png_()
            if png_data is not None:  # Some backends return None
                assert isinstance(png_data, bytes)

        plt.close(fig)


class TestRecordResultEdgeCases:
    """Test edge cases and special scenarios."""

    def test_none_object(self):
        """Test RecordResult with None as wrapped object."""
        result = RecordResult(obj=None, url="https://skua.dev/f/abc", metadata={})

        assert result.url == "https://skua.dev/f/abc"
        assert repr(result) == "None"

    def test_empty_metadata(self):
        """Test RecordResult with empty metadata."""
        result = RecordResult(obj=[1, 2, 3], url="https://skua.dev/f/abc", metadata={})

        assert result.metadata == {}

    def test_complex_metadata(self):
        """Test RecordResult with complex metadata."""
        metadata = {
            "id": "abc123",
            "title": "Complex Finding",
            "tags": ["ml", "analysis", "2024"],
            "size_bytes": 1024,
            "created_at": "2024-01-01T00:00:00Z",
        }
        result = RecordResult(obj=[1, 2, 3], url="https://skua.dev/f/abc", metadata=metadata)

        assert result.metadata == metadata
        assert result.metadata["tags"] == ["ml", "analysis", "2024"]
