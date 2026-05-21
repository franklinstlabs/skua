# Changelog

User-facing changes to `getskua`. Latest at top. Voice matches the
[skua.dev changelog](https://skua.dev/changelog): past tense, concrete,
one user-visible thing per line.

Each release must have a section before it can be published — `release-package.yml`
extracts the entry for the current version and uses it as the mirror commit body.

## 0.13.0 — 2026-05-21

- `skua.record(..., visibility="private")` and `skua.collection(name,
  visibility="private")` now raise `UploadError` immediately if the
  account is not verified — before any serialization or upload. The
  backend rejects this with 422; the SDK fail-fast saves you a 10MB
  upload on a guaranteed reject. The `/auth/status` roundtrip is only
  paid when `visibility="private"` is passed explicitly; the common
  default path stays network-cheap. `unlisted` and `public` remain
  available for anonymous accounts — `unlisted` is the right choice if
  you want a hard-to-guess shareable link without verifying.

Back-compat pruning pass. Everything below was previously kept as a silent
alias for pre-0.11 / pre-0.12 callers; with 0.12.0 just out as the first
stable on the collections API and no real users yet, this is the right
moment to delete the cruft before pinning the surface for v1.

Removed (would fail with `AttributeError` / `ImportError`):

- `skua.snap()` — use `skua.record()`.
- `skua.SnapResult` (also re-exported from `skua.result`) — use `RecordResult`.
- `skua snap <file>` CLI subcommand — use `skua record <file>`.
- `skua.init()` — gone. Bare `skua.record()` writes to your per-user
  `Default` collection; named scopes use `skua.collection(name).record(...)`.
  The 0.12 deprecation cushion that raised `ConfigurationError` with a
  migration snippet is also gone — calling init() now fails with the
  standard Python `AttributeError`.
- `skua.configure()` — set `SKUA_API_URL` / `SKUA_WEB_URL` / `SKUA_TOKEN`
  via environment variables instead.
- `skua.token()` — alias for `skua.auth()`. Use `skua.auth(token)`.
- `skua.client.upload_snapshot` / `skua.client.upload_finding` — internal
  helpers; use `skua.client.upload_record` if you really need the raw
  function (most callers should use `skua.record(...)`).
- `skua.client.get_session_id` — use `skua.client.get_client_token`.
- `skua.client.request_verification` — use `skua.client.login`.
- `skua.config.get_session_file` — use `skua.config.get_client_token_file`.
- `~/.skua/session` / `~/.skua/token` legacy fallback. Only `~/.skua/client`
  is read now. If you have a verified token in the old location, copy it
  to `~/.skua/client` before upgrading.

## 0.12.0 — 2026-05-19

- First stable release on the collections API. `skua.init()` is gone — bare `skua.record()` writes to your per-user `Default` bucket; named scopes use `skua.collection(name).record(...)`. Re-call with the same `(collection, title)` to update a record in place.
- `skua.record()` accepts `description=` and per-call `visibility=` (`"public"` / `"unlisted"` / `"private"`). Visibility is per-record; the collection's persisted default fills in when you omit it.
- `skua.open_profile()` now works for anonymous users — opens the public `/u/<auto-username>` URL. Verified users still get a short-lived one-click login URL with owner view (unlisted + private records visible).
- README + docs now match what's exported: `skua.status()`, `skua.open_profile()`, full CLI (`skua login`, `skua verify`, `skua status`, `skua list`, `skua open`).
- CLI `--public` flag (was incorrectly documented as `--visibility public`); `--collection NAME` to route to a named collection.

## 0.12.0a4 — 2026-04-27

- README rewritten for the `skua.collection()` API: bare `skua.record()` writes to the per-user "Default" bucket; named collections use `skua.collection(name).record(...)` and share a single `/c/{id}` URL for the whole bundle. The pre-0.12 `skua.init()` documentation is gone.
- `skua.record()` now raises `ValidationError` when `title` is not a string (e.g. a `Mock` left over from a test fixture, or an accidental int) — fails at the SDK boundary instead of silently uploading `repr(obj)` as the title.

## 0.11.0a8 — 2026-04-23

- `skua.open_profile()` now works for anonymous users — opens the public `/u/<auto-username>` profile URL directly. Previously it required a verified account and raised `UploadError` for anon sessions. Verified users still get the one-click login URL with unlisted/owner view

## 0.11.0a7 — 2026-04-23

- Terminology cleanup: internal `upload_snapshot` and `upload_finding` helpers are now `upload_record` (old names kept as silent aliases, no user-visible change); `@demo_finding` → `@demo_record` (alias kept); CLI help text, error messages, and docstrings now say "record" everywhere the old terms crept in
- `skua list` CLI now reads the new `records` field from `/auth/me/records` (with a fallback to the pre-0.3.8 `snapshots` shape so the CLI keeps working across the backend transition)

## 0.11.0a6 — 2026-04-22

- Empty `str` / `dict` / `list` inputs to `skua.record()` now raise `ValidationError` before serialization, with the specific type in the message

## Earlier

Entries before `0.11.0a6` aren't tracked in this file — see
[skua.dev/changelog](https://skua.dev/changelog) for the product-level history
of user-visible changes.
