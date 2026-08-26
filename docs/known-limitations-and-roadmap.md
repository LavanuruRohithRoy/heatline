# Known Limitations & Roadmap

## Current limitations, stated plainly

- **Live compliance checks are US-only** (`osha_federal`, `cal_osha`),
  because FortyGuard's current API release only covers US locations. The
  `uae` jurisdiction's regulatory data is real and seeded, but not
  currently checkable against live data. This is an upstream vendor
  constraint, documented in `03-fortyguard-integration.md`, not a gap in
  our design.
- **Manual-trigger only** — compliance checks run on demand
  (`POST /sites/{id}/check`), not on a schedule. No automatic polling
  exists yet.
- **`ShiftWindow` data is not yet consumed** by the compliance engine — a
  check can be triggered regardless of whether a site's shift is
  currently active.
- **Multi-tenant query scoping is structurally present but not fully
  enforced** — see `05-security-and-multitenancy.md` for the specific,
  scoped fix required.
- **Threshold updates require a manual reseed**, not an admin UI action —
  a deliberate tradeoff (see ADR-003 in `04-decisions.md`), not an
  oversight.
- **No deployment yet** — Render/Supabase/Upstash endpoints not yet
  provisioned; `keep_alive.yml` exists but is disabled until there's
  something to ping.

## Real, considered roadmap items (not built, but grounded in actual API capability)

- **Forecasting-driven alerts.** `heatmap`'s `start_date` genuinely accepts
  values up to 12 hours into the future (confirmed in official docs). A
  "this site will likely breach threshold in the next N hours" feature is
  buildable on existing API capability, not speculative.
- **`heat_intelligence` as the exportable audit deliverable.** The PDF
  report this endpoint generates is the closest match to what a real HSE
  manager needs to hand to a regulator or insurer — a documented artifact,
  not a live number. Genuine near-term priority once core correctness and
  safety items are done.
- **`satellite_segmentation` as a persistent per-site context layer**,
  cached alongside a site's record (land cover doesn't change day to day)
  rather than fetched per-check — shown as contextual explanation next to
  the compliance number.
- **Scheduled polling**, once shift-window logic is wired in — checks
  would run automatically during a site's active hours rather than only
  on manual trigger.
- **Threshold-update admin workflow** — a controlled, audited process for
  updating `ThresholdRule` values when regulations change, replacing the
  current manual-reseed approach.

## What's deliberately out of scope, permanently (not "later")

See `06-scalability-and-engineering-tradeoffs.md` for the full reasoning
on each: distributed/sharded architecture, dedicated API gateway,
WebSockets, ABAC. These aren't deferred — they're assessed as
inappropriate for this system's actual scale and would be re-evaluated
only if that scale materially changed.