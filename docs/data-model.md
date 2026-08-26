# Data Model & Schema

## Entity overview

```
Organization ──< User
     │
     └──< Site ──< ShiftWindow
             │
             └──< ComplianceCheck

ThresholdRule   (static reference table, not tied to Organization)
```

## Tables

### `organizations`
- `id` (UUID, PK)
- `name`
- `created_at`

The tenant boundary. Every `Site` and `User` belongs to exactly one
Organization. See `05-security-and-multitenancy.md` for how this boundary
is enforced at the query layer.

### `users`
- `id` (UUID, PK)
- `org_id` (FK → organizations)
- `email` (unique)
- `role` (enum: `admin`, `hse_manager`, `viewer`)

The `role` enum exists now so basic RBAC can be layered on without a schema
migration later. See `05-security-and-multitenancy.md` for current
enforcement status.

### `sites`
- `id` (UUID, PK)
- `org_id` (FK → organizations)
- `name`
- `polygon_geojson` (JSON — see decision rationale below)
- `jurisdiction` (enum: `osha_federal`, `cal_osha`, `uae`)

**Why `polygon_geojson` is generic `JSON`, not Postgres `JSONB`:** the
column is never queried *inside* (no filtering on properties within the
polygon), only read whole and passed through to FortyGuard's API. Generic
`JSON` is dialect-portable — it compiles against both Postgres (production)
and SQLite (test suite, in-memory, zero setup cost). `JSONB`'s indexing and
containment-query advantages were never going to be used, so there was no
real capability given up by choosing portability. This was a real bug we
hit (SQLite couldn't compile `JSONB` DDL) and fixed by changing the type,
not by working around the test environment. See `04-decisions.md` ADR-005.

### `threshold_rules`
- `id` (UUID, PK)
- `jurisdiction` (string, matches `sites.jurisdiction`)
- `heat_index_threshold_f` (float, nullable)
- `mandated_action` (string)
- `citation` (string)

Static, seeded, **not user-editable**. Regulatory thresholds are legal
facts, not tenant configuration — see `04-decisions.md` ADR-003 for the
full rationale, including the deliberate tradeoff this creates (updates
require a controlled process, currently manual).

`heat_index_threshold_f` is nullable to support fixed-window rules (e.g.
UAE's midday work-stoppage ban, which is time-based, not a temperature
threshold at all).

Seeded values, real and cited:
| Jurisdiction | Threshold | Action | Citation |
|---|---|---|---|
| osha_federal | 80°F | Provide water/shade/rest breaks | OSHA NEP on Heat Hazards, Nov 2025 |
| osha_federal | 90°F | Mandatory rest breaks, 15min/2hr | OSHA NEP, high-risk tier |
| cal_osha | 80°F | Provide shade/water access | Cal/OSHA Title 8 §3395 |
| cal_osha | 95°F | High-heat procedures, buddy system | Cal/OSHA Title 8 §3395 |
| uae | null (fixed window) | Work stoppage 12:30–15:00, Jun 15–Sep 15 | UAE Ministry of HR |

### `shift_windows`
- `id` (UUID, PK)
- `site_id` (FK → sites)
- `start_time`, `end_time`
- `days_active` (string, e.g. `"mon-fri"`)

Not yet consumed by the compliance engine — currently a compliance check
can be triggered at any time. Intended future use: only alert/escalate
during a site's actual active shift window, avoiding noise outside working
hours.

### `compliance_checks`
- `id` (UUID, PK)
- `site_id` (FK → sites)
- `checked_at` (timestamp)
- `heat_index_value` (float, °F — always converted, see ADR-001)
- `threshold_breached` (bool)
- `action_triggered` (string, nullable)

**This table is append-only by design, never updated in place.** It is the
audit trail — the record of what the system knew and decided at each point
in time. This was the correct call made early in the schema design,
recognized in hindsight as the single most important table for the
product's actual value proposition: a defensible, timestamped compliance
history a real HSE manager or auditor could rely on.