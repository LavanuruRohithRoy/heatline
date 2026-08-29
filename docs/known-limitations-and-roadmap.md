# Known Limitations & Roadmap

## Current limitations, stated plainly

- **Live compliance checks are US-only.** UAE is seeded, real, and
  explicitly rejected (not silently passed) at check-time — see
  `decisions.md` ADR-006.
- **Historical checks query a fixed lookback window (currently 6 days
  back), not "yesterday."** This is a direct response to a confirmed
  FortyGuard data-processing backlog encountered during development, not
  the product's intended freshness — see `03`.
- **Forecast mode does not yet perform true look-ahead** — see `03` for
  why, and what would need to be re-verified against FortyGuard to fix it.
- **JWT claims are trusted for the token's full lifetime** — a deleted or
  role-changed user retains access until natural expiry (24h). Re-checking
  against the database per request is a real, unbuilt fix.
- **Vendor-task timeouts (a FortyGuard job stuck in `processing` past the
  client's internal wait limit) are not yet mapped to a clean API error**
  — encountered directly during development; currently surfaces as an
  unhandled exception rather than a clean 502/504.
- **`ShiftWindow` data is not consumed** by the compliance engine.
- **Compliance records do not yet store rule version, vendor activity ID,
  or raw source response** — the audit trail is not yet fully
  reproducible back to its source, despite the traceability goal stated in
  `01`.
- **RBAC is partially, not fully, enforced** — `viewer` role has no
  meaningfully distinct restrictions from other authenticated roles yet.
- **Threshold updates require a manual reseed**, not an admin UI action —
  deliberate tradeoff, see ADR-003.
- **No refresh token, password reset, or email verification.**

## Real, considered roadmap items

- **True forecasting**, once FortyGuard's near-future data window can be
  confirmed reliably returning data (blocked on the vendor-side latency
  issue described in `03`, not on our own code).
- **`heat_intelligence` PDF reports** as an exportable audit deliverable —
  not yet integrated.
- **Scheduled/automatic polling**, once shift-window logic is wired in.
- **Rule versioning and full decision provenance** (source response,
  activity ID, rule version stored per check) — the single most important
  gap for the product's audit-trail claim to be fully true.
- **Threshold-update admin workflow.**
- **Vendor-timeout error mapping** — small, real, near-term fix.
- **Database-backed JWT/session validation** on each request, not just
  trust-until-expiry.

## What's deliberately out of scope, permanently

See `06` for full reasoning: distributed/sharded architecture, dedicated
API gateway, WebSockets, ABAC. Assessed as inappropriate at this system's
actual scale, not deferred for later.