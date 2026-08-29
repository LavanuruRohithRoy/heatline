# Architecture Decision Records

## ADR-001: Heat index drives compliance for heat-index jurisdictions

**Decision:** `env_params`-derived heat index is the compliance signal for
jurisdictions whose regulation specifies heat index (currently: OSHA
federal). See ADR-008 for the correction that this is jurisdiction-specific,
not universal.

**Why:** OSHA's NEP cites heat index, not raw ambient temperature.

## ADR-002: Max-tile value, not average, across a site's polygon

**Decision:** the compliance engine uses the maximum tile value from
`heatmap`, not the mean, across a site's polygon.

**Why:** conservative-by-design — averaging away a site's hottest corner
would under-trigger the required action for workers actually in that
corner.

## ADR-003: Static, seeded `ThresholdRule` table — not user-editable

**Decision:** regulatory thresholds are seeded once, from cited sources,
not exposed for tenant editing.

**Why:** these are legal facts, not business configuration. A controlled,
audited update process is a real roadmap item, not solved here.

## ADR-004: Redis caching, keyed by exact request parameters

**Decision:** every `heatmap`/`env_params`/`satellite_segmentation` fetch
is wrapped in a Redis cache keyed by a hash of its exact parameters.
Historical results cache for 7 days; same-day results for 1 hour. Empty
upstream responses (zero features/locations) are explicitly **not**
cached.

**Why:** cost control against a metered API, and standard practice for a
metered third-party dependency regardless. The "don't cache empty
results" rule was added after a real incident: an empty response (caused
by a genuine FortyGuard processing backlog) was cached and silently
reused across multiple unrelated requests sharing the same parameters,
masking the real cause for several debugging cycles until traced via a
repeated vendor activity ID appearing in unrelated responses.

## ADR-005: Generic `JSON`, not Postgres `JSONB`, for `sites.polygon_geojson`

**Decision:** dialect-portable `JSON`, not `JSONB`.

**Why:** the column is never queried inside; portability across Postgres
(prod) and SQLite (tests) was worth more than JSONB's unused indexing
capability. Discovered as a hard test-suite blocker, not chosen
proactively.

## ADR-006: US-only live scope; UAE modeled but explicitly rejected, not silently skipped

**Decision:** UAE `ThresholdRule` data remains seeded and real, but
`POST /sites/{id}/check` on a UAE-jurisdiction site returns a `400` with an
explicit "not currently supported" message, rather than silently
evaluating (and always passing, since its threshold is null).

**Why:** FortyGuard has no live coverage outside the US. An explicit
rejection was added after review identified that the original
implementation could return a misleading "compliant" result for a
jurisdiction the system cannot actually evaluate.

## ADR-007: Centralized architecture, not distributed

**Decision:** one FastAPI backend, one Postgres, one Redis — no message
queue, no service mesh.

**Why:** appropriate at current and expected near-term scale; the
application is stateless at the app layer specifically so it could scale
horizontally later without a rewrite. See `06`.

## ADR-008: Per-jurisdiction metric selection (correctness fix)

**Decision:** `ThresholdRule.metric_type` distinguishes `heat_index` from
`dry_bulb_temperature`. The compliance engine compares each rule against
whichever FortyGuard-derived value matches its `metric_type`, and only
calls `env_params` when at least one applicable rule needs heat index.

**Why:** Cal/OSHA Title 8 §3395(b) defines its "Temperature" trigger as
dry-bulb °F — verified directly against the regulation text. The original
implementation applied heat index uniformly across all jurisdictions,
which was a real correctness bug for Cal/OSHA, not a stylistic
simplification. This also reduces cost: Cal/OSHA checks now skip
`env_params` entirely (one fewer paid call per check).

## ADR-009: Structured DTOs and domain-error mapping

**Decision:** API routes return Pydantic response models rather than raw
ORM objects; a `DomainError` hierarchy maps known failure cases to
specific HTTP status codes (404/403/502) via a single exception handler.

**Why:** decouples the public API contract from internal persistence
schema, and gives API consumers a machine-distinguishable reason for
failure instead of a uniform 500.