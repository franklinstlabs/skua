# Skua

**Shareable URLs for notebook outputs**

One function call turns plots, DataFrames, and text into permanent links.
Re-run the cell to update — same URL, fresh results.

## Installation

```bash
pip install getskua
```

No setup required. No account, no API key.

## Quick Start

```python
import matplotlib.pyplot as plt
import skua

fig, ax = plt.subplots()
ax.plot([1, 2, 3], [1, 4, 9])
ax.set_title("Quadratic Growth")

result = skua.record(fig, title="Quadratic Growth")
print(result.url)  # https://skua.dev/r/abc123
```

Share the URL with anyone. Call `skua.record()` again with the same title to update the record in place — handy for iterating, and also the simplest way to change visibility.

To group related records together, open a named collection and record into it:

```python
q3 = skua.collection("Q3 Review")
q3.record(fig, title="Quadratic Growth")
q3.record(df, title="Sales Data")
print(q3.url)  # https://skua.dev/c/xyz789 — share the whole collection at once
```

## CLI

Works with any tool that can run shell commands — AI coding assistants, CI pipelines, scripts.

```bash
skua record chart.png --title "Q3 Revenue"
skua record data.csv --title "Sales Data" --public --tags "finance,q3"
skua record plot.json --title "Interactive Chart" --collection "Q3 Review"
cat report.txt | skua record - --type text --title "Analysis"
```

Use `--json` for machine-readable output:

```bash
skua record chart.png --title "Chart" --json
# {"url": "https://skua.dev/r/abc123", "id": "abc123", "visibility": "public"}
```

Other commands:

```bash
skua login           # open browser to verify email
skua verify sk_...   # paste the token from the verification email
skua status          # show current auth state (verified / anonymous, username)
skua list            # list your records
skua open <id>       # open a record URL in the browser
```

## Supported Types

Skua auto-detects the object type and picks the right serializer:

- **Matplotlib figures** — high-DPI PNG
- **Plotly figures** — fully interactive (zoom, pan, hover, export)
- **Pandas DataFrames** — sortable, filterable tables
- **Polars DataFrames** — same interactive tables (LazyFrames collected automatically)
- **NumPy arrays** — rendered as tables
- **PIL Images** — saved as PNG
- **Lists of dicts** — rendered as tables (handy for HuggingFace pipelines, eval loops)
- **PyTorch / TensorFlow tensors** — image tensors as PNG, others as tables
- **Anything else** — falls back to string representation

## API

### `skua.record(obj, title, description=None, visibility=None, tags=None)`

Capture and share a Python object. Returns a `Record` with `.url` and `.metadata`.
In Jupyter, the original object is displayed inline.

Bare calls write to your per-user `Default` collection — the catch-all bucket
when you don't pick a named one.

- `visibility` — `"public"`, `"unlisted"`, or `"private"`. Defaults to the collection's default visibility, or `"unlisted"` if the collection has none set.
  - `public` — listed on your profile, URL shareable, discoverable.
  - `unlisted` — URL works for anyone, but not listed on your profile.
  - `private` — only you can view (requires a verified account).
- `tags` — optional list of strings for categorization (max 20 tags, 30 chars each). Displayed on the record page and profile listing.

Re-calling `record()` with the same `(collection, title)` updates the existing record in place — including its visibility.

### `skua.collection(name, visibility=None)`

Open a named collection scope. Returns a `Collection` handle whose `.record(...)` writes into that collection. Calling twice with the same name returns the same handle.

- `name` — collection name (max 100 chars). Whitespace is trimmed.
- `visibility` — creation hint for the collection's default visibility. Persisted server-side on first creation; calls with a conflicting visibility on a previously-created collection raise `ConfigurationError` rather than silently override.

```python
proj = skua.collection("Q3 Review")
proj.record(fig, title="Lift over time")
print(proj.url)  # /c/<id> — shareable as one bundle
```

### `skua.login()`

Open the browser to verify your email. Verified accounts get 365-day retention (vs 30 days for anonymous), no per-account record cap, and a public profile page at `skua.dev/u/username`.

### `skua.auth("sk_...")`

Paste the token you receive by email after `skua.login()`.

### `skua.status()`

Return a dict with the current auth state: `{"verified": bool, "email": str | None, "username": str, "retention_days": int}`. Useful in scripts that need to branch on "am I verified yet?" before recording.

### `skua.open_profile()`

Open your profile page in a browser. For verified users, mints a short-lived one-click login URL so the browser lands already signed in (unlisted and private records visible). For anonymous users, opens the bare public profile URL. Returns the URL. Pass `open_browser=False` to just get the URL back (CI/headless).

## Environment

All infrastructure-level settings are read from environment variables (rarely needed):

- `SKUA_API_URL` — API host (default: `https://api.skua.dev`)
- `SKUA_WEB_URL` — web host (default: `https://skua.dev`)
- `SKUA_TOKEN` — auth token (alternative to `skua.auth()` / `~/.skua/token`)

## Limits

Anonymous usage works out of the box:

- 30-day retention, 10 records per device, 20 uploads/hour, 10 MB per record

Verify your email to unlock:

- 365-day retention (resets on update), no per-account record cap, 10 MB per record

## Privacy

`public` and `unlisted` records are accessible to anyone who has the URL — URLs contain random IDs that are not guessable, but there's no login-gated access control for these. `private` records are cookie/token-gated and only viewable by you. Do not record sensitive data at `public` or `unlisted`.

## Documentation

Full docs, live examples, and the API reference at [skua.dev/docs](https://skua.dev/docs).

## License

MIT

## Support

Questions or feedback? Email **hello@skua.dev** or open an issue on [GitHub](https://github.com/franklinstlabs/skua).
