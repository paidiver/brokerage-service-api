# Search sessions

## Overview

The session endpoints merge independently paginated upstream sources into one ascending
result stream. Completed brokerage pages are cached in Redis. The separate
`GET /api/annotations/search` fetches all matches before sorting and pagination;
use session endpoints for bounded incremental fetching. Export endpoints are
independent of sessions.

## Requests

Create a search:

```http
POST /api/annotations/search/sessions
Content-Type: application/json

{
  "name_part": "cod",
  "sources": ["bodc", "jncc"],
  "order_by": "annotation_creation_datetime",
  "page_size": 20,
  "add_summary": true,
  "add_info": true
}
```

Omit `sources` to search all enabled sources. Unknown sources are rejected. Existing
annotation filters are accepted. `page` may only be 1. Page size is 1–500, default 20.
The default ordering is `annotation_creation_datetime`; `label_aphia_id` and `label_name`
are also accepted subject to the upstream ordering contract below.

A successful creation returns **201** with `count`, `next`, `previous`, an array
in `results`, and `meta`. `Location` identifies page 1. `meta` contains `search_id`,
`page`, `page_size`, `total_pages`, `generated_through_page`, `source_counts`,
`expires_at`, `summary` and `info`.
Counts and summaries describe the initial full matches, not the current page.
Records remain distinct across sources: identity is `(source, row UUID)`.
An empty search has `count=0`, `total_pages=0` and an empty page 1.

With `add_info: true`, `meta.info` contains the available full-search filter options:

```json
{
  "image_sets": [{ "uuid": "00000000-0000-0000-0000-000000000001", "name": "Survey images" }],
  "annotation_sets": [{ "uuid": "00000000-0000-0000-0000-000000000002", "name": "Survey annotations" }],
  "aphia_ids": [{ "aphia_id": 558, "scientific_name": "Porifera", "rank": "Phylum" }]
}
```

The brokerage and UI use `annotation_sets`, matching the annotations API. Set entries are merged
by UUID and taxa by Aphia ID, preserving source order and the first entry for duplicate
IDs. Rank may be null. No fields are inferred from the current page's annotations.
Info is requested on each source's first batch and persisted for subsequent and cached
pages. If some sources omit Info, available sources still contribute; if all omit it,
or `add_info` is false, `info` is null. Empty Info lists remain empty lists.
The regular search endpoint also returns merged `meta.info` when requested.

Retrieve a page:

```http
GET /api/annotations/search/sessions/{search_id}/pages/68
```

A cached page returns **200** without upstream calls. Otherwise the broker merges
from its saved position, preparing intervening pages. Each request has a work budget.
If the requested page is not ready, the response is **202**, with `Retry-After: 1`,
`Location` pointing to the requested page, and:

```json
{
  "status": "preparing",
  "count": 1500,
  "meta": {
    "search_id": "...",
    "page": 68,
    "page_size": 20,
    "total_pages": 75,
    "generated_through_page": 11,
    "expires_at": "...",
    "source_counts": {"bodc": 750, "jncc": 750},
    "summary": null,
    "info": null
  }
}
```

Repeat that GET after the indicated delay. Polling advances the work; there is no
background worker. Stop polling when the user abandons navigation. Creation can also
return 202 for page 1. Processing time limits cover upstream/merge work, not Redis
operations; creation has separate initial-fetch and page-preparation budgets.

Changing filters, sources, sorting or page size requires a new search. Keep its ID in
UI state, or in per-tab `sessionStorage` if refresh recovery is desired. No login or
cookie session is required. These endpoints serve the same public data as existing
search: the unpredictable ID is a capability for accessing that search. If data later
requires authentication, session ownership and per-request access checks must be added.

Release a session early:

```http
DELETE /api/annotations/search/sessions/{search_id}
```

Deletion returns **204**, including repeated deletion. Otherwise Redis automatically
expires all pages and state together, by default 30 minutes after creation. Reading
pages does not extend that deadline. Expired, deleted, evicted and unknown IDs return
**410**; start a fresh search rather than silently reusing page positions.

## Upstream ordering contract

Every source must honour the requested ascending `order_by`, **nulls last**, with
ascending search-row UUID as a tie-breaker. The merger compares `(value, source, UUID)`;
within any one source this agrees with `(value, UUID)`. Timestamps are compared in UTC.
`label_name` requires Unicode code-point order, which is not guaranteed by a database's
default collation. Sources must be configured/updated to agree before relying on text
ordering. Local sorting of one batch cannot correct incompatible upstream ordering.

The broker validates each batch and its boundary against the preceding batch. It
rejects detected backwards records or repeated keys with `upstream_ordering`. This
validation is defensive: it cannot prove that unseen upstream records are correctly
ordered. Old source deployments that ignore `order_by` are not compatible with this
merge contract. No upstream repository changes are included in this implementation.

Upstream page size is independent of brokerage page size. The broker uses each source's
own sequential page number, checks `count` and `next` for consistency, and never forwards
the requested brokerage page number to all sources. Sources may cap the requested batch
size; the actual records fetched determine progress.

## Consistency and errors

Pages already generated are immutable. Initial counts are not a database snapshot.
Detected count changes return `upstream_changed`; restart the search. Changes that
preserve the count, or insertions/deletions between numbered upstream pages, can still
cause missing/repeated records. Strong consistency needs upstream snapshot support or
full materialization; cursor pagination alone does not freeze changing data.

A failed source is not silently skipped because its next record may precede every other
source's record. Completed pages remain usable; retry from the last committed position.
State and each completed page are saved atomically. A per-session writer lease prevents
concurrent advancement; Redis WATCH checks lease ownership and state existence before
commit, so a stale worker cannot overwrite progress or resurrect a deleted session.

Errors use RFC 9457 `application/problem+json` with top-level `code` and a string `detail`:

| Status | Code | Client action |
| --- | --- | --- |
| 404 | `invalid_page` | Request a page within the reported range |
| 409 | `search_session_busy` | Retry after `Retry-After` |
| 409 | `upstream_changed` | Start a new search |
| 410 | `search_session_expired` | Start a new search |
| 413 | `search_session_limit` | Narrow the search; completed pages remain readable |
| 422 | `unknown_source` | Correct the source selection |
| 429 | `search_creation_limit` | Retry after `Retry-After` |
| 502 | `upstream_failed` | Retry; completed pages remain readable |
| 502 | `upstream_invalid` / `upstream_ordering` | Correct the source contract |
| 503 | `search_sessions_unavailable` / `no_sources` | Restore Redis or source configuration |
| 504 | `upstream_timeout` | Retry creating the search |

## Configuration and operation

Use `REDIS_ENABLED=true`, `REDIS_BACKEND=redis` and a shared `REDIS_URL` for multiple
API workers. Existing Compose and Helm configurations already select real Redis.
The default standalone Python configuration uses `fake`, which is process-local and
only suitable for single-worker development/tests. Redis failure returns 503 for
session operations; it does not fall back to private worker state.

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `SEARCH_SESSION_TTL_SECONDS` | 1800 | Fixed lifetime; maximum 86400 |
| `SEARCH_SESSION_BATCH_SIZE` | 100 | Upstream batch size; maximum 500 |
| `SEARCH_SESSION_PAGES_PER_REQUEST` | 10 | Maximum new pages per retrieval; maximum 100 |
| `SEARCH_SESSION_REQUEST_SECONDS` | 5 | Work time per phase; maximum 20 |
| `SEARCH_SESSION_MAX_BYTES` | 16000000 | Serialized state and pages per session; maximum 256000000 |
| `SEARCH_SESSION_CREATIONS_PER_MINUTE` | 60 | Global fixed-minute creation limit across workers; maximum 10000 |

All values must be positive. Helm exposes corresponding values under `searchSessions`.
The writer lease is 30 seconds; a request that outlives it must retry rather than commit.
The byte limit excludes Redis key/hash overhead, so provision additional memory.
Creation admission also counts attempts whose upstream calls subsequently fail.

Size and admission limits bound growth but are not a total Redis memory reservation.
Set Redis memory capacity/policy for the expected number of active searches. Eviction
loses sessions (410); persistence is optional because clients can restart searches.
A Redis restart/failover can lose cached progress; this is not a durable search archive.
