# Security & Multi-Tenancy

## Public demo link vs. metered credit budget

**Mitigations, implemented:**

1. **The unauthenticated public route (`GET /public/sites`) is read-only
   and returns only pre-seeded data belonging to one designated
   `is_public_demo` organization.** No credit-spending route is reachable
   without authentication. This is the primary protection for a publicly
   shared link.
2. **Rate limiting** on `POST /sites/{id}/check`, per-organization,
   Redis-backed, scaled by plan (`trial`: 10 checks/hour, `standard`: 200
   checks/hour — see `rate_limit.py`).
3. **JWT authentication** required on every mutating and credit-spending
   route.

## Multi-tenancy — implemented and verified

Every authenticated query is scoped to `current_user.org_id`, derived
server-side from the JWT, never from client-supplied input. Verified
directly: a created site is correctly stamped with the authenticated
user's org, and a cross-org check attempt against another org's site
returns `404`, not the resource. `POST /sites`'s request body does not
accept an `org_id` field at all — it cannot be spoofed by a client.

## Authentication — real, implemented

Email/password registration and login, bcrypt password hashing, JWT
(single access token, 24-hour expiry, **no refresh token** — a deliberate
scope decision; re-login after expiry is the accepted UX for the current
build). The JWT's claims (`user_id`, `org_id`, `role`) are trusted for the
token's lifetime once issued — the system does **not** currently re-check
against the database on each request whether the user/org/role still
exist or are unchanged. This is a real, acknowledged gap: a
deleted/downgraded user retains access until their token naturally
expires. See `07`.

## RBAC — enforced, not just modeled

`POST /sites` requires `admin` or `hse_manager` role. `POST
/organizations/upgrade` requires `admin`. Other authenticated routes are
open to any valid role. This is a real, if partial, enforcement — not
every route has a role check, and `viewer` currently has no meaningfully
restricted capability beyond what any authenticated user can do.

**ABAC was considered and explicitly not built** — see `06` for the
reasoning; unchanged from the original assessment.

## Input validation

- `polygon_geojson` is validated on write (`POST /sites`) as a real,
  closed GeoJSON Polygon via Shapely — malformed payloads are rejected
  with `400` before ever reaching FortyGuard.
- All request bodies are Pydantic models, validated at the boundary.
- All database access is via SQLAlchemy's parameterized query builder —
  no raw string-interpolated SQL exists anywhere in the codebase.

## CORS — configured via environment, not hardcoded

`allow_origins` is populated from an environment variable
(`ALLOWED_ORIGINS`, comma-separated) rather than hardcoded — set to the
deployed frontend's real Vercel URL and `http://localhost:5173` (or
whichever local dev port the frontend uses) for local development. This
replaces an earlier open `["*"]` placeholder used during initial local
development.

## What was explicitly not built, and why

- Full OAuth/social login, refresh tokens, password reset, email
  verification — real, legitimate features, out of scope for this
  timeline, noted as roadmap items rather than pretended-away.
- Distributed rate-limit coordination — moot at single-instance
  deployment; Redis-backed state already generalizes correctly if the app
  scales horizontally later.