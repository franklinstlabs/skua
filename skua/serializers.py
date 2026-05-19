"""Object serializers for converting Python objects to JSON-safe formats."""

import base64
import io
from typing import Any, Dict, Protocol


class Serializer(Protocol):
    """Protocol for serializer implementations."""

    def can_serialize(self, obj: Any) -> bool:
        """Check if this serializer can handle the given object.

        Args:
            obj: Object to check

        Returns:
            True if this serializer can handle the object
        """
        ...

    def serialize(self, obj: Any) -> Dict[str, Any]:
        """Serialize object to JSON-safe dictionary.

        Args:
            obj: Object to serialize

        Returns:
            Dictionary with type, format, data, and metadata
        """
        ...


class MatplotlibSerializer:
    """Serializer for matplotlib figures."""

    def can_serialize(self, obj: Any) -> bool:
        """Check if object is a matplotlib figure."""
        try:
            from matplotlib.figure import Figure

            return isinstance(obj, Figure)
        except ImportError:
            return False

    def serialize(self, obj: Any) -> Dict[str, Any]:
        """Serialize matplotlib figure to PNG base64."""

        # Save figure to bytes
        buf = io.BytesIO()
        obj.savefig(buf, format="png", bbox_inches="tight", dpi=200)
        buf.seek(0)
        img_bytes = buf.read()

        # Encode as base64
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        return {
            "type": "matplotlib.figure",
            "format": "png",
            "data": img_b64,
            "metadata": {
                "dpi": 200,
                "size_bytes": len(img_bytes),
            },
        }


class PandasDataFrameSerializer:
    """Serializer for pandas DataFrames."""

    def can_serialize(self, obj: Any) -> bool:
        """Check if object is a pandas DataFrame."""
        try:
            import pandas as pd

            return isinstance(obj, pd.DataFrame)
        except ImportError:
            return False

    def serialize(self, obj: Any) -> Dict[str, Any]:
        """Serialize pandas DataFrame to JSON."""

        # Convert to JSON (orient=split preserves index and columns)
        json_data = obj.to_json(orient="split")

        return {
            "type": "pandas.dataframe",
            "format": "json",
            "data": json_data,
            "metadata": {
                "shape": obj.shape,
                "columns": list(obj.columns),
                "dtypes": {col: str(dtype) for col, dtype in obj.dtypes.items()},
                "index_name": obj.index.name,
            },
        }


class PILImageSerializer:
    """Serializer for PIL/Pillow Image objects."""

    def can_serialize(self, obj: Any) -> bool:
        """Check if object is a PIL Image."""
        try:
            from PIL import Image

            return isinstance(obj, Image.Image)
        except ImportError:
            return False

    def serialize(self, obj: Any) -> Dict[str, Any]:
        """Serialize PIL Image to PNG base64."""

        # Save image to bytes
        buf = io.BytesIO()
        obj.save(buf, format="PNG")
        buf.seek(0)
        img_bytes = buf.read()

        # Encode as base64
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        return {
            "type": "pil.image",
            "format": "png",
            "data": img_b64,
            "metadata": {
                "size": obj.size,  # (width, height)
                "mode": obj.mode,  # RGB, RGBA, L, etc.
                "size_bytes": len(img_bytes),
            },
        }


class DictSerializer:
    """Serializer for Python dicts to pretty-printed JSON."""

    def can_serialize(self, obj: Any) -> bool:
        """Check if object is a dict."""
        return isinstance(obj, dict)

    def serialize(self, obj: Any) -> Dict[str, Any]:
        """Serialize dict to pretty-printed JSON."""
        import json

        json_str = json.dumps(obj, indent=2, default=str, ensure_ascii=False)

        return {
            "type": "dict",
            "format": "json",
            "data": json_str,
            "metadata": {
                "key_count": len(obj),
            },
        }


class NumpySerializer:
    """Serializer for numpy arrays, converted to pandas DataFrames."""

    def can_serialize(self, obj: Any) -> bool:
        """Check if object is a numpy ndarray."""
        try:
            import numpy as np

            return isinstance(obj, np.ndarray)
        except ImportError:
            return False

    def serialize(self, obj: Any) -> Dict[str, Any]:
        """Serialize numpy array by converting to DataFrame."""
        import pandas as pd

        if obj.ndim == 1:
            df = pd.DataFrame(obj)
        else:
            df = pd.DataFrame(obj)

        # Use pandas serialization but preserve numpy type
        result = PandasDataFrameSerializer().serialize(df)
        result["type"] = "numpy.ndarray"
        return result


def _plotly_png_bytes(fig: Any) -> Any:
    """Render a plotly figure to a 1200×630 PNG if kaleido is available.

    Returns None when kaleido isn't installed or rendering fails. The sidecar
    PNG is used as the OpenGraph preview image on record pages; a missing
    image is fine — the record page falls back to the generic home card.

    Kaleido is an optional dep (install via `pip install getskua[plotly]`).
    """
    try:
        import kaleido  # noqa: F401
    except ImportError:
        return None
    try:
        # 1200×630 matches LinkedIn/Twitter's preferred OG card size. scale=1
        # keeps the PNG under ~50 KB for typical charts — well below platform
        # caps. Let kaleido use its bundled chromium-mini.
        return fig.to_image(format="png", width=1200, height=630, scale=1)
    except Exception:
        # Kaleido can fail for many reasons (sandbox issues, font availability,
        # figures with unsupported traces). Silently skip — the record still
        # uploads successfully, just without an OG preview.
        return None


class PlotlySerializer:
    """Serializer for Plotly figures.

    Stores the figure as JSON — the frontend renders it interactively with
    plotly.js. If `kaleido` is installed, also generates a 1200×630 PNG
    sidecar so social-preview scrapers (LinkedIn/Slack/X) show the chart
    instead of a bare link. The primary `data` field is always JSON; the
    PNG rides alongside as `preview_png_b64`.
    """

    def can_serialize(self, obj: Any) -> bool:
        try:
            from plotly.basedatatypes import BaseFigure
            return isinstance(obj, BaseFigure)
        except ImportError:
            return False

    def serialize(self, obj: Any) -> Dict[str, Any]:
        json_str = obj.to_json()
        result: Dict[str, Any] = {
            "type": "plotly.figure",
            "format": "json",
            "data": json_str,
            "metadata": {},
        }
        png_bytes = _plotly_png_bytes(obj)
        if png_bytes:
            result["preview_png_b64"] = base64.b64encode(png_bytes).decode("utf-8")
        return result


class PolarsDataFrameSerializer:
    """Serializer for Polars DataFrames — produces orient=split JSON natively.

    Avoids the pandas/pyarrow round-trip so users with just `polars` installed
    don't also need pyarrow.
    """

    def can_serialize(self, obj: Any) -> bool:
        try:
            import polars as pl
            return isinstance(obj, (pl.DataFrame, pl.LazyFrame))
        except ImportError:
            return False

    def serialize(self, obj: Any) -> Dict[str, Any]:
        import json
        import polars as pl

        df = obj.collect() if isinstance(obj, pl.LazyFrame) else obj
        columns = list(df.columns)
        data = [list(row) for row in df.iter_rows()]
        json_str = json.dumps(
            {"columns": columns, "index": list(range(df.height)), "data": data},
            default=str,
        )
        return {
            "type": "polars.dataframe",
            "format": "json",
            "data": json_str,
            "metadata": {
                "shape": df.shape,
                "columns": columns,
                "dtypes": {col: str(dtype) for col, dtype in zip(df.columns, df.dtypes)},
                "index_name": None,
            },
        }


class TorchTensorSerializer:
    """Serializer for PyTorch tensors — image tensors as PNG, others as DataFrame."""

    def can_serialize(self, obj: Any) -> bool:
        try:
            import torch
            return isinstance(obj, torch.Tensor)
        except ImportError:
            return False

    def serialize(self, obj: Any) -> Dict[str, Any]:
        import torch
        t = obj.detach().cpu()

        # Image tensor: (C, H, W) or (1, C, H, W) with C in {1, 3, 4}
        if t.ndim == 4 and t.shape[0] == 1:
            t = t.squeeze(0)
        if t.ndim == 3 and t.shape[0] in (1, 3, 4):
            from PIL import Image
            import numpy as np
            arr = t.float().numpy()
            # Normalize to [0, 255] if float
            if arr.dtype != np.uint8:
                arr = ((arr - arr.min()) / (arr.max() - arr.min() + 1e-8) * 255).astype(np.uint8)
            # CHW → HWC
            arr = arr.transpose(1, 2, 0)
            if arr.shape[2] == 1:
                arr = arr[:, :, 0]
            return PILImageSerializer().serialize(Image.fromarray(arr))

        # Everything else: flatten to ≤2D and render as DataFrame
        if t.ndim > 2:
            t = t.reshape(t.shape[0], -1)
        import numpy as np
        result = NumpySerializer().serialize(t.float().numpy())
        result["type"] = "torch.tensor"
        return result


class TensorFlowTensorSerializer:
    """Serializer for TensorFlow/Keras tensors — delegates to NumpySerializer."""

    def can_serialize(self, obj: Any) -> bool:
        try:
            import tensorflow as tf
            return isinstance(obj, (tf.Tensor, tf.Variable))
        except ImportError:
            return False

    def serialize(self, obj: Any) -> Dict[str, Any]:
        result = NumpySerializer().serialize(obj.numpy())
        result["type"] = "tensorflow.tensor"
        return result


class ListOfDictsSerializer:
    """Serializer for list-of-dicts — common output of HF pipelines and eval loops."""

    def can_serialize(self, obj: Any) -> bool:
        return (
            isinstance(obj, list)
            and len(obj) > 0
            and all(isinstance(item, dict) for item in obj)
        )

    def serialize(self, obj: Any) -> Dict[str, Any]:
        import pandas as pd
        df = pd.DataFrame(obj)
        result = PandasDataFrameSerializer().serialize(df)
        result["type"] = "list[dict]"
        return result


class StringSerializer:
    """Fallback serializer for string/text objects."""

    def can_serialize(self, obj: Any) -> bool:
        return True  # Fallback serializer always accepts

    def serialize(self, obj: Any) -> Dict[str, Any]:
        return {
            "type": "text",
            "format": "plain",
            "data": str(obj),
            "metadata": {"original_type": type(obj).__name__},
        }


# Registry of serializers (checked in order)
SERIALIZERS = [
    MatplotlibSerializer(),
    PlotlySerializer(),
    PandasDataFrameSerializer(),
    PolarsDataFrameSerializer(),
    PILImageSerializer(),
    TorchTensorSerializer(),
    TensorFlowTensorSerializer(),
    NumpySerializer(),
    ListOfDictsSerializer(),
    DictSerializer(),
    StringSerializer(),  # Fallback must be last
]


def serialize_object(obj: Any) -> Dict[str, Any]:
    """Serialize an object using the first matching serializer.

    Args:
        obj: Object to serialize

    Returns:
        Serialized data dictionary

    Raises:
        SerializationError: If no serializer can handle the object (shouldn't happen with fallback)
    """
    for serializer in SERIALIZERS:
        if serializer.can_serialize(obj):
            return serializer.serialize(obj)

    # Should never reach here due to StringSerializer fallback
    from skua.exceptions import SerializationError

    raise SerializationError(f"No serializer found for type: {type(obj)}")
