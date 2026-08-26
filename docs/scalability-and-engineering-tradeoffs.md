# Scalability & Engineering Tradeoffs

This document exists to be explicit about what was considered and
deliberately not built, and why — the absence of a piece of
infrastructure here is a decision, not an oversight.

## Connection pooling

SQLAlchemy's async engine manages connection pooling by default; no custom
pool tuning was required or added. Worth confirming pool size is
appropriate for expected concurrent load before production use, but this
is a configuration check, not new engineering work.

## Dependency injection

FastAPI's `Depends()` mechanism, already used for database session
injection (`get_db`), is dependency injection appropriately scoped to this
system's size. A standalone DI container/framework would add abstraction
without a corresponding need — there is no scenario in this codebase where
`Depends()`'s capabilities are insufficient.

## API gateway

Not deployed as a separate component. At this scale, FastAPI plus the
deploy platform's edge/reverse-proxy layer (Render, or equivalent)
functions as the gateway — handling TLS termination and routing. Standing
up a dedicated gateway (Kong, AWS API Gateway) would add operational
surface with zero functional benefit at current traffic levels.

## Load balancing & horizontal scaling

Not deployed — current target is a single backend instance. The
architecture is designed to support it later without rework: the FastAPI
app holds no in-process state (no in-memory session data, no local
caching layer outside Redis), so multiple instances could run behind a
load balancer with zero application-level changes. This is the correct
engineering posture: **design for statelessness now, defer the
infrastructure until the load actually requires it.**

## Sharding

Not warranted. Sharding solves a data-volume/write-throughput problem this
system does not have — a hackathon-to-early-product dataset (handful of
organizations, hundreds of sites) fits comfortably in a single Postgres
instance. Naming this explicitly, with the actual data-volume reasoning,
is more credible than either building unnecessary infrastructure or
silently ignoring the question.

## Distributed vs. centralized architecture

The system is a centralized architecture (see `01-system-overview.md`
diagram): one backend, one database, one cache, calling outward to
external services it doesn't operate (FortyGuard, the deploy platform,
managed Postgres/Redis providers). This is stated as the accurate
classification, not softened — claiming "distributed system" status for
an architecture that is centralized-with-external-dependencies would be a
misrepresentation, not an aspiration.

## WebSockets

Not implemented. A live-updating dashboard (pushing status changes to
connected clients without a page refresh) is a genuine nice-to-have for
user experience, achievable equally well for demo purposes via short-
interval polling (e.g. every 30 seconds) from the frontend — which
requires zero new infrastructure. The cut is explicit: WebSockets would be
justified if the product had a real requirement for sub-second update
latency (it doesn't — heat conditions change over minutes/hours, not
seconds), not because it's unachievable.

## Cloud architecture / deployment target

Current plan: Render (application hosting, free/starter tier),
Supabase or Neon (managed Postgres), Upstash (managed Redis) — all
managed services chosen specifically to avoid operating infrastructure
that isn't the actual product. A `keep_alive` GitHub Actions workflow
exists to mitigate free-tier cold-start sleep behavior, currently disabled
until first deploy (nothing to ping yet), documented in
`07-known-limitations-and-roadmap.md`.

## Summary framing for review

Every item on this page follows the same shape: name the real capability,
state honestly whether it's needed at this system's actual scale, and if
not, explain the specific reasoning rather than silently omitting it. This
is meant to demonstrate engineering judgment — knowing when *not* to build
something is as much a real skill as building it.