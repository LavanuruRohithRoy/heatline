# Architecture Decision Records

Each entry: the decision, why, and what was given up.

## ADR-001: Heat index (`env_params`), not raw temperature (`tcm`), drives compliance

**Decision:** the compliance check's primary signal is
`env_params.heat_index_celsius`, derived from a `heatmap`/`tcm` tile
temperature, not the raw `tcm` value directly.

**Why:** OSHA's NEP and Cal/OSHA Title 8 §3395 both cite heat index
(temperature + humidity), not ambient temperature. The two diverge
meaningfully on humid days — raw temperature can under-report real risk
by 10–15°F equivalent.

**History:** the initial implementation used `tcm` directly as a
placeholder for heat index. This was identified as a correctness gap
during a deliberate system-design review, not caught by a test or a bug
report — worth stating plainly rather than presenting the final design as
if it were correct from the start.

**Cost given up:** every compliance check now requires two chained,
credit-costing API calls instead of one.

## ADR-002: Max-tile value, not average, across a site's polygon

**Decision:** when a site's polygon returns multiple `heatmap` tiles, the
compliance engine uses the maximum tile value, not the mean.

**Why:** this is a safety-compliance tool. Averaging away a site's hottest
corner would under-trigger the required action for workers actually in
that corner. Conservative-by-design, stated as such rather than left
implicit.

## ADR-003: Static, seeded `ThresholdRule` table — not user-editable

**Decision:** regulatory thresholds are seeded once, from cited sources,
and are not exposed for tenant editing in the current build.

**Why:** these are legal facts, not business configuration. Allowing
arbitrary customer edits would let a tenant silently misconfigure their
own regulatory exposure — the opposite of what a compliance tool should
allow.

**Tradeoff acknowledged:** updating a threshold (e.g. if OSHA revises the
NEP trigger) currently requires a manual migration/reseed, not a UI action.
A real production version would need a controlled, audited update process
(admin-only, versioned) — explicitly scoped as a roadmap item, not solved
here.

## ADR-004: Redis caching, keyed by exact request parameters

**Decision:** every `heatmap` fetch is wrapped in a Redis cache keyed by a
hash of its exact parameters (polygon, date, filter_type, granularity,
analytic_type). Historical (already-elapsed-day) results cache for 7 days;
same-day results cache for 1 hour.

**Why:** two reasons, both real. First, cost control against a metered,
credit-limited upstream API — repeated identical checks (dev iteration,
demo re-runs, accidental double-clicks) must not re-spend credits.
Second, this is legitimate production practice regardless of the credit
constraint: caching a metered third-party API behind a short TTL is
standard, not a hackathon-specific workaround.

**History:** this was built *after* a real, costly debugging session (9
heatmap calls, ~38,000 credits) where each retry during active development
re-spent credits. The lesson — that dev-time iteration against a paid API
needs caching from day one, not after the fact — is itself worth recording.

## ADR-005: Generic `JSON`, not Postgres `JSONB`, for `sites.polygon_geojson`

**Decision:** the polygon column uses SQLAlchemy's dialect-portable `JSON`
type, not Postgres-specific `JSONB`.

**Why:** the column is never queried *inside* — no filtering on properties
within the polygon JSON — so JSONB's indexing/containment-operator
advantages were never being used. Generic `JSON` compiles against both
Postgres (production) and SQLite (in-memory test suite), removing a real
test-infrastructure dependency (a live Postgres container) for the test
suite.

**History:** this was discovered as a hard blocker, not chosen proactively
— the original `JSONB` column caused `sqlalchemy.exc.CompileError` against
SQLite during the first real test run. The fix was a genuine architecture
correction (portability), not a workaround.

## ADR-006: US-only live scope; UAE modeled but not live-queryable

**Decision:** the product's live-data compliance checks are scoped to
`osha_federal` and `cal_osha` jurisdictions. The `uae` `ThresholdRule`
remains in the schema as real, cited regulatory data, but is explicitly
documented as not currently queryable via FortyGuard, since FortyGuard's
current release covers US locations only.

**Why:** this is an honest response to a real, documented upstream vendor
constraint (see `03-fortyguard-integration.md`), not a design choice we
made. Removing the UAE data entirely would discard real regulatory
research for no benefit; presenting it as live-checkable would misrepresent
what the system can actually do today.

## ADR-007: Centralized architecture, not distributed

**Decision:** one FastAPI backend process, one Postgres instance, one
Redis instance. No message queue, no service mesh, no horizontal
partitioning.

**Why:** at current and near-term expected data volume (a handful of
organizations, hundreds of sites at most), a distributed architecture adds
operational complexity with no corresponding benefit. The system is
designed to be *stateless at the application layer* (no in-process session
state, all shared state in Postgres/Redis) specifically so it *could* scale
horizontally later without a rewrite — see
`06-scalability-and-engineering-tradeoffs.md`. Building the distributed
infrastructure now, before it's needed, would be premature and would cost
build time better spent on correctness (ADR-001) and safety (ADR-004,
security doc).