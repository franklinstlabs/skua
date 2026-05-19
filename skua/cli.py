"""Skua CLI — record and share from the command line."""

import base64
import json
import sys
from pathlib import Path
from typing import Optional

import click
import requests

from skua.client import (
    get_auth_status,
    get_session_id,
    login,
    set_token,
    upload_record,
)
from skua.config import get_api_url, get_web_url
from skua.exceptions import UploadError, ValidationError

# Exit codes
EXIT_OK = 0
EXIT_AUTH = 1
EXIT_VALIDATION = 2
EXIT_SERVER = 3
EXIT_RATE_LIMITED = 4

# Extension to file type mapping (values match _build_content's file_type param)
EXT_TYPE_MAP = {
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".csv": "csv",
    ".json": "json",
    ".txt": "text",
}


def _detect_type(filepath: str) -> Optional[str]:
    """Detect content type from file extension."""
    ext = Path(filepath).suffix.lower()
    return EXT_TYPE_MAP.get(ext)


def _build_content(raw_bytes: bytes, file_type: str, source_path: Optional[str] = None) -> dict:
    """Build the content dict that upload_record() expects.

    Args:
        raw_bytes: Raw file bytes
        file_type: One of png, jpg, csv, json, text
        source_path: Original file path (for extension detection)

    Returns:
        Content dict with data, type, format, metadata keys
    """
    def _decode_text(data: bytes) -> str:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValidationError(
                "File is not valid UTF-8. Check the file encoding."
            )

    if file_type in ("png", "jpg"):
        fmt = file_type
        img_b64 = base64.b64encode(raw_bytes).decode("utf-8")
        return {
            "type": "pil.image",
            "format": fmt,
            "data": img_b64,
            "metadata": {"size_bytes": len(raw_bytes)},
        }

    if file_type == "csv":
        text = _decode_text(raw_bytes)
        import csv
        import io
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if not rows:
            return {
                "type": "pandas.dataframe",
                "format": "json",
                "data": json.dumps({"columns": [], "index": [], "data": []}),
                "metadata": {"shape": [0, 0], "columns": [], "dtypes": {}},
            }
        columns = rows[0]
        data_rows = rows[1:]
        # Convert values and track types per column
        col_types: list[set[str]] = [set() for _ in columns]
        converted = []
        for row in data_rows:
            converted_row = []
            for j, val in enumerate(row):
                try:
                    converted_row.append(int(val))
                    if j < len(col_types):
                        col_types[j].add("int64")
                except ValueError:
                    try:
                        converted_row.append(float(val))
                        if j < len(col_types):
                            col_types[j].add("float64")
                    except ValueError:
                        converted_row.append(val)
                        if j < len(col_types):
                            col_types[j].add("object")
            converted.append(converted_row)
        # Infer dtype per column: mixed numeric → float64, mixed with strings → object
        dtypes = {}
        for j, col in enumerate(columns):
            types = col_types[j] if j < len(col_types) else {"object"}
            if types == {"int64"}:
                dtypes[col] = "int64"
            elif types <= {"int64", "float64"}:
                dtypes[col] = "float64"
            else:
                dtypes[col] = "object"
        split_json = json.dumps({
            "columns": columns,
            "index": list(range(len(data_rows))),
            "data": converted,
        })
        return {
            "type": "pandas.dataframe",
            "format": "json",
            "data": split_json,
            "metadata": {
                "shape": [len(data_rows), len(columns)],
                "columns": columns,
                "dtypes": dtypes,
            },
        }

    if file_type == "json":
        text = _decode_text(raw_bytes)
        parsed = json.loads(text)
        # Detect plotly: has "data" key with a list of trace objects
        if (
            isinstance(parsed, dict)
            and "data" in parsed
            and isinstance(parsed["data"], list)
        ):
            return {
                "type": "plotly.figure",
                "format": "json",
                "data": text,
                "metadata": {},
            }
        # Generic dict/JSON
        return {
            "type": "dict",
            "format": "json",
            "data": text if isinstance(parsed, dict) else json.dumps(parsed, indent=2),
            "metadata": {"key_count": len(parsed) if isinstance(parsed, dict) else 0},
        }

    # text (default)
    text = raw_bytes.decode("utf-8")
    return {
        "type": "text",
        "format": "plain",
        "data": text,
        "metadata": {},
    }


def _handle_error(e: Exception, json_output: bool = False) -> int:
    """Map exceptions to exit codes and print errors."""
    msg = str(e)

    if json_output:
        click.echo(json.dumps({"error": msg}))
    else:
        click.echo(f"Error: {msg}", err=True)

    if isinstance(e, ValidationError):
        return EXIT_VALIDATION
    if isinstance(e, UploadError):
        lower = msg.lower()
        if "401" in lower or "403" in lower or "auth" in lower:
            return EXIT_AUTH
        if "429" in lower or "rate" in lower:
            return EXIT_RATE_LIMITED
    return EXIT_SERVER


@click.group()
@click.version_option(package_name="getskua")
def main():
    """Skua — shareable URLs for notebook outputs."""
    pass


@main.command()
@click.argument("file", type=click.Path(exists=False))
@click.option("--title", "-t", required=True, help="Title for the record")
@click.option("--description", "-d", default=None, help="Optional description")
@click.option("--public", is_flag=True, default=False, help="Make the record public")
@click.option("--collection", "collection_name", default=None,
              help="Collection name. Omit to route to the per-user Default collection.")
@click.option(
    "--type", "file_type", default=None,
    type=click.Choice(["png", "jpg", "csv", "json", "text"]),
    help="File type (required for stdin)",
)
@click.option("--tags", default=None, help='Comma-separated tags (e.g. "finance,pandas")')
@click.option("--json", "json_output", is_flag=True, help="Output JSON for agents")
def record(file: str, title: str, description: Optional[str],
           public: bool, collection_name: Optional[str], file_type: Optional[str],
           tags: Optional[str], json_output: bool):
    """Upload a file as a record."""
    try:
        # Read from stdin or file
        if file == "-":
            if file_type is None:
                raise ValidationError(
                    "--type is required when reading from stdin"
                )
            raw_bytes = sys.stdin.buffer.read()
            if not raw_bytes:
                raise ValidationError("No input received from stdin")
        else:
            path = Path(file)
            if not path.exists():
                raise ValidationError(f"File not found: {file}")
            raw_bytes = path.read_bytes()
            if file_type is None:
                file_type = _detect_type(file)
                if file_type is None:
                    raise ValidationError(
                        f"Cannot detect type for {path.suffix}. "
                        f"Use --type to specify."
                    )

        content = _build_content(raw_bytes, file_type, file)
        visibility = "public" if public else None
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        record_data = {
            "content": content,
            "title": title.strip(),
            "description": description,
            "visibility": visibility,
            "tags": tag_list,
            **({"collection_name": collection_name} if collection_name is not None else {}),
        }

        result = upload_record(record_data)

        record_id = result["id"]
        applied_visibility = result.get("visibility", "public")
        url = f"{get_web_url()}/r/{record_id}"

        if json_output:
            click.echo(json.dumps({
                "url": url,
                "id": record_id,
                "visibility": applied_visibility,
            }))
        else:
            click.echo(f"✓ {title.strip()} → {url} ({applied_visibility})")

    except Exception as e:
        sys.exit(_handle_error(e, json_output))


# Silent alias for `skua record` — rename happened for trademark distance.
main.add_command(record, name="snap")


@main.command()
def status():
    """Show authentication status."""
    try:
        info = get_auth_status()
        username = info.get("username") or "unknown"
        if info.get("verified"):
            click.echo(f"Verified as @{username} ({info.get('email', 'unknown')})")
        else:
            click.echo(f"Anonymous as @{username}")
            click.echo("Run 'skua login' to verify your email")
        click.echo(f"Retention: {info.get('retention_days', '?')} days")
    except UploadError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_SERVER)


@main.command(name="login")
def login_cmd():
    """Open browser to verify your email."""
    login()


@main.command()
@click.argument("token")
def verify(token: str):
    """Activate a verification token."""
    try:
        set_token(token)
    except ValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_VALIDATION)
    except UploadError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_AUTH)


@main.command(name="list")
@click.option("--json", "json_output", is_flag=True, help="Output JSON for agents")
def list_cmd(json_output: bool):
    """List your records."""
    try:
        api_url = get_api_url()
        session_id = get_session_id()
        response = requests.get(
            f"{api_url}/auth/me/records",
            headers={"X-Skua-Token": session_id},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        # /auth/me/records returns {email, records_count, records: [...]}.
        # `snapshots` is the pre-0.3.8 field name — read it as a fallback so
        # this CLI keeps working against older backends during rollout.
        if isinstance(data, list):
            items = data
        else:
            items = data.get("records") or data.get("snapshots") or data.get("items", [])

        if json_output:
            click.echo(json.dumps(items))
            return

        if not items:
            click.echo("No records yet")
            return

        web_url = get_web_url()
        for item in items:
            rid = item.get("id", "?")
            title = item.get("title", "Untitled")
            vis = item.get("visibility", "public")
            click.echo(f"  {rid}  {title}  ({vis})  {web_url}/r/{rid}")

    except requests.exceptions.HTTPError as e:
        resp = e.response
        if resp is not None and resp.status_code == 429:
            click.echo("Error: Rate limited", err=True)
            sys.exit(EXIT_RATE_LIMITED)
        elif resp is not None and resp.status_code in (401, 403):
            click.echo("Error: Authentication required", err=True)
            sys.exit(EXIT_AUTH)
        else:
            click.echo(f"Error: {e}", err=True)
            sys.exit(EXIT_SERVER)
    except requests.exceptions.RequestException as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(EXIT_SERVER)


@main.command(name="open")
@click.argument("record_id")
def open_cmd(record_id: str):
    """Open a record URL in the browser."""
    import webbrowser

    url = f"{get_web_url()}/r/{record_id}"
    click.echo(f"Opening {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        click.echo(f"Could not open browser: {e}", err=True)
        click.echo(f"Visit: {url}")
