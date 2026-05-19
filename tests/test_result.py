"""Tests for RecordResult class (SnapResult kept as silent alias)."""

import pytest

from skua.result import RecordResult, SnapResult


class TestRenameAlias:
    """SnapResult is kept as a silent alias for back-compat."""

    def test_snap_result_is_record_result(self):
        # Old imports must still resolve to the same class — any code
        # referencing `SnapResult` from before 0.11 must keep working.
        assert SnapResult is RecordResult

    def test_class_name_is_record_result(self):
        # Tracebacks and IDE hover should say RecordResult, not SnapResult.
        result = RecordResult(obj={}, url="https://skua.dev/r/x", metadata={})
        assert type(result).__name__ == "RecordResult"


class TestSnapResultBasics:
    """Test basic SnapResult functionality."""

    def test_stores_url_and_metadata(self):
        """Test that SnapResult stores URL and metadata."""
        obj = {"data": [1, 2, 3]}
        url = "https://skua.dev/r/abc123"
        metadata = {"id": "abc123", "title": "Test", "tags": []}

        result = SnapResult(obj=obj, url=url, metadata=metadata)

        assert result.url == url
        assert result.metadata == metadata

    def test_repr_returns_object_repr(self):
        """Test that __repr__ delegates to wrapped object."""
        obj = [1, 2, 3]
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert repr(result) == repr(obj)
        assert repr(result) == "[1, 2, 3]"

    def test_str_returns_object_str(self):
        """Test that __str__ delegates to wrapped object."""
        obj = {"a": 1, "b": 2}
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert str(result) == str(obj)


class TestIPythonDisplayHook:
    """`_ipython_display_` hands the wrapped object straight to IPython's
    display() machinery so types whose Jupyter rendering relies on IPython's
    formatter registry — most importantly `matplotlib.figure.Figure` — show
    up inline. Without this, `record(fig)` as the last line in a cell falls
    back to the plain-text repr because Figure doesn't expose `_repr_png_`
    on the class itself."""

    def test_ipython_display_passes_wrapped_object_to_display(self, monkeypatch):
        """`_ipython_display_` calls IPython.display.display() with the
        wrapped object so the full formatter pipeline (including matplotlib's
        per-type formatter hook) gets a chance to render it."""
        import sys
        import types

        captured = {}

        def fake_display(obj):
            captured["obj"] = obj

        fake_module = types.ModuleType("IPython.display")
        fake_module.display = fake_display
        fake_pkg = types.ModuleType("IPython")
        fake_pkg.display = fake_module
        monkeypatch.setitem(sys.modules, "IPython", fake_pkg)
        monkeypatch.setitem(sys.modules, "IPython.display", fake_module)

        sentinel = object()
        result = RecordResult(obj=sentinel, url="https://skua.dev/r/abc", metadata={})
        result._ipython_display_()

        assert captured["obj"] is sentinel

    def test_ipython_display_silently_returns_when_ipython_unavailable(self, monkeypatch):
        """If IPython isn't installed (e.g., a non-notebook script picked up
        the SDK), `_ipython_display_` should be a no-op rather than raising —
        the caller wouldn't be invoking it in that environment anyway."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "IPython.display" or name.startswith("IPython"):
                raise ImportError("forced")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        result = RecordResult(obj=[1, 2, 3], url="https://skua.dev/r/abc", metadata={})
        # Should not raise.
        assert result._ipython_display_() is None


class TestSnapResultNotebookDisplay:
    """Test Jupyter notebook display methods."""

    def test_repr_html_delegates_to_object(self):
        """Test _repr_html_ delegation."""

        class HTMLObject:
            def _repr_html_(self):
                return "<b>Hello</b>"

        obj = HTMLObject()
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert result._repr_html_() == "<b>Hello</b>"

    def test_repr_html_returns_none_if_not_supported(self):
        """Test _repr_html_ returns None for objects without HTML repr."""
        obj = [1, 2, 3]
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert result._repr_html_() is None

    def test_repr_png_delegates_to_object(self):
        """Test _repr_png_ delegation."""

        class PNGObject:
            def _repr_png_(self):
                return b"PNG_DATA"

        obj = PNGObject()
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert result._repr_png_() == b"PNG_DATA"

    def test_repr_svg_delegates_to_object(self):
        """Test _repr_svg_ delegation."""

        class SVGObject:
            def _repr_svg_(self):
                return "<svg>...</svg>"

        obj = SVGObject()
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert result._repr_svg_() == "<svg>...</svg>"

    def test_repr_json_delegates_to_object(self):
        """Test _repr_json_ delegation."""

        class JSONObject:
            def _repr_json_(self):
                return {"data": [1, 2, 3]}

        obj = JSONObject()
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert result._repr_json_() == {"data": [1, 2, 3]}


class TestSnapResultAttributeAccess:
    """Test transparent attribute access to wrapped object."""

    def test_getattr_delegates_to_object(self):
        """Test that attributes are accessed from wrapped object."""

        class MyObject:
            def __init__(self):
                self.value = 42

            def method(self):
                return "called"

        obj = MyObject()
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert result.value == 42
        assert result.method() == "called"

    def test_getitem_delegates_to_object(self):
        """Test that indexing works on wrapped object."""
        obj = {"a": 1, "b": 2, "c": 3}
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert result["a"] == 1
        assert result["b"] == 2

    def test_len_delegates_to_object(self):
        """Test that len() works on wrapped object."""
        obj = [1, 2, 3, 4, 5]
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert len(result) == 5

    def test_iter_delegates_to_object(self):
        """Test that iteration works on wrapped object."""
        obj = [1, 2, 3]
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        items = list(result)
        assert items == [1, 2, 3]

    def test_contains_delegates_to_object(self):
        """Test that 'in' operator works on wrapped object."""
        obj = [1, 2, 3]
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert 2 in result
        assert 5 not in result


class TestSnapResultComparison:
    """Test comparison operators."""

    def test_equality_with_object(self):
        """Test equality comparison with unwrapped object."""
        obj = [1, 2, 3]
        result = SnapResult(obj=obj, url="https://skua.dev/r/abc", metadata={})

        assert result == [1, 2, 3]
        assert result != [1, 2, 4]

    def test_equality_with_snap_result(self):
        """Test equality comparison between SnapResults."""
        obj1 = [1, 2, 3]
        obj2 = [1, 2, 3]
        obj3 = [4, 5, 6]

        result1 = SnapResult(obj=obj1, url="https://skua.dev/r/abc", metadata={})
        result2 = SnapResult(obj=obj2, url="https://skua.dev/r/def", metadata={})
        result3 = SnapResult(obj=obj3, url="https://skua.dev/r/ghi", metadata={})

        assert result1 == result2  # Same wrapped object
        assert result1 != result3  # Different wrapped object

    def test_comparison_operators(self):
        """Test less-than, greater-than operators."""
        result1 = SnapResult(obj=5, url="https://skua.dev/r/abc", metadata={})
        result2 = SnapResult(obj=10, url="https://skua.dev/r/def", metadata={})

        assert result1 < result2
        assert result1 <= result2
        assert result2 > result1
        assert result2 >= result1

        # Compare with unwrapped values
        assert result1 < 10
        assert result2 > 5


class TestSnapResultArithmetic:
    """Test arithmetic operators."""

    def test_addition(self):
        """Test addition operator."""
        result = SnapResult(obj=5, url="https://skua.dev/r/abc", metadata={})

        assert result + 3 == 8
        assert result + result == 10

    def test_subtraction(self):
        """Test subtraction operator."""
        result = SnapResult(obj=10, url="https://skua.dev/r/abc", metadata={})

        assert result - 3 == 7
        assert result - result == 0

    def test_multiplication(self):
        """Test multiplication operator."""
        result = SnapResult(obj=5, url="https://skua.dev/r/abc", metadata={})

        assert result * 2 == 10
        assert result * result == 25

    def test_division(self):
        """Test division operator."""
        result = SnapResult(obj=10, url="https://skua.dev/r/abc", metadata={})

        assert result / 2 == 5
        assert result / result == 1

    def test_floor_division(self):
        """Test floor division operator."""
        result = SnapResult(obj=10, url="https://skua.dev/r/abc", metadata={})

        assert result // 3 == 3

    def test_modulo(self):
        """Test modulo operator."""
        result = SnapResult(obj=10, url="https://skua.dev/r/abc", metadata={})

        assert result % 3 == 1

    def test_power(self):
        """Test power operator."""
        result = SnapResult(obj=2, url="https://skua.dev/r/abc", metadata={})

        assert result**3 == 8


class TestSnapResultWithDataFrame:
    """Test SnapResult with pandas DataFrame (if available)."""

    def test_dataframe_operations(self):
        """Test that DataFrame operations work through SnapResult."""
        try:
            import pandas as pd
        except ImportError:
            pytest.skip("pandas not installed")

        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        result = SnapResult(obj=df, url="https://skua.dev/r/abc", metadata={})

        # Test column access
        assert list(result["a"]) == [1, 2, 3]

        # Test method call
        assert result.shape == (3, 2)

        # Test _repr_html_ (DataFrames have this)
        html = result._repr_html_()
        assert html is not None
        assert "<table" in html


class TestSnapResultWithMatplotlib:
    """Test SnapResult with matplotlib Figure (if available)."""

    def test_figure_has_repr_png(self):
        """Test that Figure objects expose _repr_png_ if matplotlib supports it."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            pytest.skip("matplotlib not installed")

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])

        result = SnapResult(obj=fig, url="https://skua.dev/r/abc", metadata={})

        # Matplotlib figures may have _repr_png_ depending on backend
        # Test that SnapResult properly delegates if the method exists
        if hasattr(fig, "_repr_png_"):
            png_data = result._repr_png_()
            if png_data is not None:  # Some backends return None
                assert isinstance(png_data, bytes)

        plt.close(fig)


class TestSnapResultEdgeCases:
    """Test edge cases and special scenarios."""

    def test_none_object(self):
        """Test SnapResult with None as wrapped object."""
        result = SnapResult(obj=None, url="https://skua.dev/r/abc", metadata={})

        assert result.url == "https://skua.dev/r/abc"
        assert repr(result) == "None"

    def test_empty_metadata(self):
        """Test SnapResult with empty metadata."""
        result = SnapResult(obj=[1, 2, 3], url="https://skua.dev/r/abc", metadata={})

        assert result.metadata == {}

    def test_complex_metadata(self):
        """Test SnapResult with complex metadata."""
        metadata = {
            "id": "abc123",
            "title": "Complex Record",
            "tags": ["ml", "analysis", "2024"],
            "size_bytes": 1024,
            "created_at": "2024-01-01T00:00:00Z",
        }
        result = SnapResult(obj=[1, 2, 3], url="https://skua.dev/r/abc", metadata=metadata)

        assert result.metadata == metadata
        assert result.metadata["tags"] == ["ml", "analysis", "2024"]
