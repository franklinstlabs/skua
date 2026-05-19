"""Tests for skua.collection() and the Collection handle class.

Covers the 0.12 behavior where skua.collection(name) performs a synchronous
backend roundtrip on first call (idempotent POST /collections), caches the
handle in-process, and raises ConfigurationError on visibility mismatch
with the persisted value.
"""

from unittest.mock import patch

import pytest

import skua
import skua._collection as collection_module
from skua._collection import Collection
from skua.exceptions import ConfigurationError, ValidationError


@pytest.fixture(autouse=True)
def _reset_collection_cache():
    """Each test gets a fresh per-process cache."""
    collection_module._collections.clear()
    yield
    collection_module._collections.clear()


def _stub_response(name: str, visibility: str = "unlisted", id: str = "Lk2mX4nQ8rTw") -> dict:
    """Canonical POST /collections response body — used to mock the backend."""
    return {
        "id": id,
        "name": name,
        "visibility": visibility,
        "url": f"https://skua.dev/c/{id}",
        "created_at": "2026-04-25T12:00:00Z",
        "is_owner": True,
    }


class TestCollectionFactory:
    def test_collection_returns_handle_with_url_id_visibility(self):
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3 Review", visibility="unlisted")
            c = skua.collection("Q3 Review")
        assert isinstance(c, Collection)
        assert c.name == "Q3 Review"
        assert c.visibility == "unlisted"
        assert c.id == "Lk2mX4nQ8rTw"
        assert c.url == "https://skua.dev/c/Lk2mX4nQ8rTw"

    def test_first_call_hits_backend_subsequent_calls_cache(self):
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3 Review")
            c1 = skua.collection("Q3 Review")
            c2 = skua.collection("Q3 Review")  # cache hit, no backend call
        assert c1 is c2
        assert backend.call_count == 1, "second call should be served from cache"

    def test_whitespace_in_name_is_trimmed(self):
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3 Review")
            c1 = skua.collection("Q3 Review")
            c2 = skua.collection("  Q3 Review  ")
        assert c1 is c2

    def test_empty_name_raises(self):
        with pytest.raises(ValidationError, match="non-empty"):
            skua.collection("")

    def test_whitespace_only_name_raises(self):
        with pytest.raises(ValidationError, match="non-empty"):
            skua.collection("   ")

    def test_name_too_long_raises(self):
        with pytest.raises(ValidationError, match="too long"):
            skua.collection("x" * 101)


class TestCollectionVisibility:
    def test_visibility_kwarg_forwarded_to_backend(self):
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3", visibility="unlisted")
            skua.collection("Q3", visibility="unlisted")
        assert backend.call_args.kwargs == {"name": "Q3", "visibility": "unlisted"}

    def test_no_visibility_kwarg_passes_none(self):
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3", visibility="unlisted")
            skua.collection("Q3")
        assert backend.call_args.kwargs == {"name": "Q3", "visibility": None}

    def test_invalid_visibility_raises_locally(self):
        with pytest.raises(ValidationError, match="Invalid visibility"):
            skua.collection("Q3", visibility="secret")

    def test_visibility_mismatch_in_process_raises_configuration_error(self):
        """First call cached at visibility=public; second call with visibility=private
        raises before any backend roundtrip — first-caller-wins is enforced locally."""
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3", visibility="public")
            c1 = skua.collection("Q3", visibility="public")
        with pytest.raises(ConfigurationError, match="exists with visibility"):
            skua.collection("Q3", visibility="private")

    def test_visibility_match_on_second_call_returns_cached(self):
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3", visibility="unlisted")
            c1 = skua.collection("Q3", visibility="unlisted")
            c2 = skua.collection("Q3", visibility="unlisted")
        assert c1 is c2
        assert backend.call_count == 1, "should not retry the backend on cache hit"

    def test_no_kwarg_after_kwarg_returns_cached(self):
        """Caller drops the kwarg on a second access; resolves to existing handle
        regardless of stored visibility — no error, no backend call."""
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3", visibility="private")
            c1 = skua.collection("Q3", visibility="private")
            c2 = skua.collection("Q3")  # no kwarg, should resolve fine
        assert c1 is c2

    def test_backend_409_translates_to_configuration_error(self):
        """Cross-process: another kernel created the collection at a different
        visibility. Backend returns 409, SDK turns it into ConfigurationError."""
        with patch("skua.client.create_or_get_collection") as backend:
            backend.side_effect = ConfigurationError(
                "Collection 'Q3' exists with visibility='unlisted'. "
                "You passed visibility='public'."
            )
            with pytest.raises(ConfigurationError, match="exists with visibility"):
                skua.collection("Q3", visibility="public")


class TestCollectionRecord:
    def test_record_routes_through_collection_name(self):
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3 Review")
            c = skua.collection("Q3 Review")

        with patch("skua.record.upload_record") as upload:
            upload.return_value = {
                "id": "rec1234567890",
                "creator_username": "testbird-42",
                "visibility": "unlisted",
                "collection_id": "Lk2mX4nQ8rTw",
                "collection_name": "Q3 Review",
                "collection_url": "https://skua.dev/c/Lk2mX4nQ8rTw",
            }
            c.record("hello", title="My Note")
            payload = upload.call_args.args[0]
        assert payload["collection_name"] == "Q3 Review"

    def test_record_no_per_call_visibility_omits_field(self):
        """Server-side default kicks in when SDK sends no visibility; per the new
        layered model the SDK no longer substitutes a collection default
        client-side."""
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3")
            c = skua.collection("Q3")

        with patch("skua.record.upload_record") as upload:
            upload.return_value = {
                "id": "rec1234567890",
                "creator_username": "testbird-42",
                "visibility": "unlisted",
            }
            c.record("hi", title="X")
            payload = upload.call_args.args[0]
        assert payload["visibility"] is None

    def test_per_call_visibility_overrides(self):
        with patch("skua.client.create_or_get_collection") as backend:
            backend.return_value = _stub_response("Q3", visibility="unlisted")
            c = skua.collection("Q3", visibility="unlisted")

        with patch("skua.record.upload_record") as upload:
            upload.return_value = {
                "id": "rec1234567890",
                "creator_username": "testbird-42",
                "visibility": "public",
            }
            c.record("hi", title="X", visibility="public")
            payload = upload.call_args.args[0]
        assert payload["visibility"] == "public"
