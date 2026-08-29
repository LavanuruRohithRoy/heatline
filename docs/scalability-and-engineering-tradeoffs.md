# Scalability & Engineering Tradeoffs

This document is explicit about what was considered and deliberately not
built, and why — absence here is a decision, not an oversight.

## Connection pooling

SQLAlchemy's async engine manages pooling by default; no custom tuning
added. Worth revisiting pool size against Supabase's actual connection
limits before real production load, but this is a configuration check,
not new engineering work.

## Dependency injection

FastAPI's `Depends()`, already used throughout (`get_db`,
`get_current_user`), is appropriately-scoped DI for this system's size. No
separate DI container was added or needed.

## API gateway

Not deployed. Render's edge handles TLS/routing for the API; a dedicated
gateway would add operational surface with zero functional benefit at
current traffic levels.

## Load balancing & horizontal scaling

Not deployed — single backend instance on Render. The application is
stateless at the app layer (no in-process session state; all shared state
lives in Postgres/Redis), so it could run behind a load balancer across
multiple instances later without application-level rework.

## Sharding

Not warranted at this data volume. Not revisited since the original
assessment — nothing about the actual build changed this calculus.

## Distributed vs. centralized architecture

Centralized: one backend, one database, one cache, calling outward to
external services it doesn't operate. Stated as the accurate
classification.

## WebSockets

Not implemented. Polling from the frontend at a modest interval is
sufficient — heat conditions change over minutes/hours, not seconds, so
there is no sub-second-latency requirement to justify the added
complexity.

## Deployment target — actual, not planned

- **Frontend:** Vercel (static React build)
- **Backend API:** Render (FastAPI, Docker)
- **Database:** Supabase (managed PostgreSQL)
- **Cache/rate-limit store:** Upstash (managed Redis)

All chosen specifically to avoid operating infrastructure that isn't the
actual product. `ALLOWED_ORIGINS` (see `05`) is set to the real deployed
frontend URL. A `keep_alive` GitHub Actions workflow exists to mitigate
free-tier cold-start sleep on Render; its enabled/disabled state should be
confirmed against the actual live deployment status at submission time
rather than assumed from this document.

## Summary framing

Every item here follows the same shape: name the real capability, state
honestly whether it's needed at this system's actual scale, and explain
the reasoning rather than silently omitting it.