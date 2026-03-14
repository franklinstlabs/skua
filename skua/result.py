"""RecordResult class for rich return values from skua.record()."""

from __future__ import annotations

from typing import Any, Dict


class RecordResult:
    """Rich result object returned by skua.record().

    This object wraps the original object and provides access to the URL
    and metadata while maintaining transparent notebook display behavior.

    Attributes:
        url: The shareable URL for the finding
        metadata: Metadata about the finding (ID, title, tags, etc.)

    Examples:
        >>> result = skua.record(fig, title="My Plot")
        ✓ Recorded: https://skua.dev/f/abc123
        >>> result.url
        'https://skua.dev/f/abc123'
        >>> result.metadata
        {'id': 'abc123', 'title': 'My Plot', 'tags': []}
        >>> result  # In notebooks, displays the original figure
        <matplotlib.figure.Figure object at 0x...>
    """

    def __init__(self, obj: Any, url: str, metadata: Dict[str, Any]):
        """Initialize a RecordResult.

        Args:
            obj: The original object that was recorded
            url: The shareable URL for the finding
            metadata: Metadata about the finding
        """
        self._obj = obj
        self.url = url
        self.metadata = metadata

    def __repr__(self) -> str:
        """Return string representation.

        In notebooks, this displays the original object's representation,
        making RecordResult transparent to the user.
        """
        return repr(self._obj)

    def __str__(self) -> str:
        """Return string representation."""
        return str(self._obj)

    def _repr_html_(self) -> str | None:
        """Return HTML representation for Jupyter notebooks.

        This enables rich display in notebooks (e.g., DataFrames as tables,
        plots as images) while still providing access to .url and .metadata.
        """
        if hasattr(self._obj, "_repr_html_"):
            return self._obj._repr_html_()
        return None

    def _repr_png_(self) -> bytes | None:
        """Return PNG representation for Jupyter notebooks.

        This enables matplotlib figures to display inline.
        """
        if hasattr(self._obj, "_repr_png_"):
            return self._obj._repr_png_()
        return None

    def _repr_jpeg_(self) -> bytes | None:
        """Return JPEG representation for Jupyter notebooks."""
        if hasattr(self._obj, "_repr_jpeg_"):
            return self._obj._repr_jpeg_()
        return None

    def _repr_svg_(self) -> str | None:
        """Return SVG representation for Jupyter notebooks."""
        if hasattr(self._obj, "_repr_svg_"):
            return self._obj._repr_svg_()
        return None

    def _repr_latex_(self) -> str | None:
        """Return LaTeX representation for Jupyter notebooks."""
        if hasattr(self._obj, "_repr_latex_"):
            return self._obj._repr_latex_()
        return None

    def _repr_json_(self) -> Dict[str, Any] | None:
        """Return JSON representation for Jupyter notebooks."""
        if hasattr(self._obj, "_repr_json_"):
            return self._obj._repr_json_()
        return None

    def _repr_markdown_(self) -> str | None:
        """Return Markdown representation for Jupyter notebooks."""
        if hasattr(self._obj, "_repr_markdown_"):
            return self._obj._repr_markdown_()
        return None

    # Make RecordResult behave like the wrapped object for common operations
    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to the wrapped object.

        This allows accessing methods and attributes of the original object
        directly on the RecordResult.

        Example:
            >>> df_result = skua.record(df)
            >>> df_result.head()  # Calls df.head()
        """
        return getattr(self._obj, name)

    def __getitem__(self, key: Any) -> Any:
        """Delegate item access to the wrapped object.

        This allows indexing operations on the RecordResult.

        Example:
            >>> df_result = skua.record(df)
            >>> df_result['column_name']  # Works like df['column_name']
        """
        return self._obj[key]

    def __len__(self) -> int:
        """Delegate len() to the wrapped object."""
        return len(self._obj)

    def __iter__(self):
        """Delegate iteration to the wrapped object."""
        return iter(self._obj)

    def __contains__(self, item: Any) -> bool:
        """Delegate 'in' operator to the wrapped object."""
        return item in self._obj

    # Comparison operators
    def __eq__(self, other: Any) -> bool:
        """Delegate equality to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj == other._obj
        return self._obj == other

    def __ne__(self, other: Any) -> bool:
        """Delegate inequality to the wrapped object."""
        return not self.__eq__(other)

    def __lt__(self, other: Any) -> bool:
        """Delegate less-than to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj < other._obj
        return self._obj < other

    def __le__(self, other: Any) -> bool:
        """Delegate less-than-or-equal to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj <= other._obj
        return self._obj <= other

    def __gt__(self, other: Any) -> bool:
        """Delegate greater-than to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj > other._obj
        return self._obj > other

    def __ge__(self, other: Any) -> bool:
        """Delegate greater-than-or-equal to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj >= other._obj
        return self._obj >= other

    # Arithmetic operators (for numeric types)
    def __add__(self, other: Any) -> Any:
        """Delegate addition to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj + other._obj
        return self._obj + other

    def __sub__(self, other: Any) -> Any:
        """Delegate subtraction to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj - other._obj
        return self._obj - other

    def __mul__(self, other: Any) -> Any:
        """Delegate multiplication to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj * other._obj
        return self._obj * other

    def __truediv__(self, other: Any) -> Any:
        """Delegate division to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj / other._obj
        return self._obj / other

    def __floordiv__(self, other: Any) -> Any:
        """Delegate floor division to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj // other._obj
        return self._obj // other

    def __mod__(self, other: Any) -> Any:
        """Delegate modulo to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj % other._obj
        return self._obj % other

    def __pow__(self, other: Any) -> Any:
        """Delegate power to the wrapped object."""
        if isinstance(other, RecordResult):
            return self._obj ** other._obj
        return self._obj ** other
