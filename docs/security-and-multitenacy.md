# Security & Multi-Tenancy

## The real, urgent risk: public demo link vs. metered credit budget

This system calls a metered, credit-limited third-party API. A publicly
reachable demo link with no protection is a direct liability against a
finite 5,000,000-credit budget — not a hypothetical, since a single
`heatmap` + `env_params` compliance check costs real credits every time it
executes against live (uncached) data.

**Mitigations, in order of what actually matters:**

1. **Demo mode is cache/DB-read-only by default.** The public demo serves
   pre-seeded sites with already-fetched, cached compliance data. A
   "refresh" action either replays cached results with a visible
   "last checked" timestamp, or is gated behind an authenticated path.
   This makes the public link safe regardless of traffic volume — the
   credit-spending path is never reachable without authentication.
2. **Rate limiting on any route that can trigger a live FortyGuard call.**
   Implemented via the same Redis instance already used for caching — a
   token-bucket or fixed-window counter per API key/IP, hard-capped
   (e.g. a handful of live checks per minute). This is additive
   infrastructure cost of roughly zero, since Redis is already deployed
   for caching.
3. **Basic API-key requirement on expensive routes.** Not full RBAC —
   simply: does this request carry a valid key. Applied to
   `POST /sites/{id}/check`; read-only demo routes remain open.

## Multi-tenancy — what's structurally present vs. what's enforced

**Structurally present:** every `Site` and `User` carries an `org_id`
foreign key. The schema is multi-tenant-shaped from the first migration.

**Not yet enforced:** query-level scoping — ensuring an authenticated
user's queries are automatically filtered to their own `org_id` — is a
real, necessary, and currently incomplete piece of work. This is a small,
well-understood fix (a `WHERE org_id = current_user.org_id` clause applied
consistently at the query layer, ideally via a shared dependency/session
scope rather than repeated per-route), not a new subsystem. Treated as a
priority item, not deferred indefinitely.

## RBAC — implemented at the level the system actually needs

The `users.role` enum (`admin`, `hse_manager`, `viewer`) exists in the
schema. Current build applies it minimally (e.g., only `admin` can create
sites); full per-route permission enforcement is a realistic half-day of
remaining work, tracked as a near-term task rather than a "someday" item.

**ABAC (attribute-based access control) was considered and explicitly not
built.** ABAC earns its complexity at a scale with many fine-grained,
context-dependent policies across large numbers of tenants and resource
types. This system has three roles and single-org data isolation as its
actual access-control surface. Building an ABAC policy engine here would
be complexity without a corresponding real requirement — naming that
tradeoff explicitly is more honest, and demonstrates better engineering
judgment, than partially implementing a framework the system doesn't need.

## Input validation & injection prevention

Not a gap requiring new work — already true of the current stack, worth
stating explicitly rather than treated as unaddressed:

- **Request validation**: every route's input is a Pydantic model, which
  validates types and structure at the request boundary before any
  business logic runs.
- **SQL injection**: all database access goes through SQLAlchemy's ORM
  with parameterized queries; no raw string-interpolated SQL exists
  anywhere in the codebase.

## CORS

Configured via FastAPI's standard CORS middleware, scoped to the actual
frontend origin once deployed. A few lines of necessary configuration, not
a design question — included here for completeness of the security
surface, not because it required a decision.

## What was explicitly not built, and why that's the right call here

- **Full OAuth/session-based auth flow**: API-key auth (already how
  FortyGuard itself authenticates us) is sufficient for the current scope
  and consistent with the pattern already used for the upstream
  integration.
- **Distributed rate-limit coordination across multiple app instances**:
  moot at single-instance deployment (see
  `06-scalability-and-engineering-tradeoffs.md`); Redis-backed limiting
  already generalizes correctly if/when the app scales horizontally, since
  the limit state lives outside the app process.