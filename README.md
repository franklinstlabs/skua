# Skua

**Capture and share Jupyter notebook results via shareable links.**

Skua eliminates the "last mile" problem of sharing data science results. Instead of taking screenshots or exporting static files, capture your visualizations and data with a single function call.

## Installation

```bash
pip install getskua
```

That's it! Skua automatically detects and works with libraries you already have installed (matplotlib, pandas, PIL, etc.).

## Quick Start

```python
import matplotlib.pyplot as plt
import skua

# Create a visualization
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [1, 4, 9])
ax.set_title("Quadratic Growth")

# Capture and share it
result = skua.record(fig, title="Q3 Revenue Analysis")
print(result.url)  # https://skua.dev/f/abc123
```

Share the URL with colleagues. Re-run `skua.record()` with the same title to update in place — same URL, fresh results.

## Supported Objects

- **Matplotlib figures** - Saved as high-DPI PNG images
- **Pandas DataFrames** - Interactive, sortable, filterable tables
- **NumPy arrays** - Rendered as tables (converted to DataFrames)
- **Dicts** - Pretty-printed JSON with syntax highlighting
- **PIL Images** - Any `PIL.Image` object, saved as PNG
- **Text/strings** - Any object with a string representation

## Configuration

By default, Skua uses the hosted service at `https://skua.dev`. You can configure a different API URL if needed:

```python
import skua

skua.configure(api_url="https://custom-url.com")
```

Or via environment variable:

```bash
export SKUA_API_URL=https://custom-url.com
```

## Anonymous Usage

Skua uses anonymous sessions - no account required:
- Session persists across notebook runs
- Findings expire after 7 days
- Limited to 10 findings per session
- Rate limited to 20 uploads per hour

## Privacy

- Anonymous findings are automatically deleted after 7 days
- Open source Python package (MIT License)

## Documentation

Visit [https://skua.dev](https://skua.dev) for more information and examples.

## License

MIT License - see LICENSE file for details

## Support

Questions or feedback? Email **hello@skua.dev**

## Stay Updated

Get notified about new features and releases:  
**https://skua.dev/subscribe**
