# Changelog

User-facing changes to `getskua`. Latest at top. Voice matches the
[skua.dev changelog](https://skua.dev/changelog): past tense, concrete,
one user-visible thing per line.

Each release must have a section before it can be published — `release-package.yml`
extracts the entry for the current version and uses it as the mirror commit body.

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
