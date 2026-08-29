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
- `plan` (enum: `trial`, `standard`)
- `is_public_demo` (bool) — flags the one org whose sites are shown on the
  unauthenticated public landing page; no other org's data is ever exposed
  without a valid session
- `created_at`

The tenant boundary. Every `Site` and `User` belongs to exactly one
Organization. See `security-and-multitenancy.md` for enforcement.

### `users`
- `id` (UUID, PK)
- `org_id` (FK → organizations)
- `email` (unique)
- `password_hash`
- `role` (enum: `admin`, `hse_manager`, `viewer`)

### `sites`
- `id` (UUID, PK)
- `org_id` (FK → organizations)
- `name`
- `polygon_geojson` (JSON — validated as a closed GeoJSON Polygon on write)
- `jurisdiction` (enum: `osha_federal`, `cal_osha`, `uae`)

**Why `polygon_geojson` is generic `JSON`, not Postgres `JSONB`:** the
column is never queried *inside* — only read whole and passed through to
FortyGuard's API. Generic `JSON` compiles against both Postgres
(production) and SQLite (test suite). See `decisions.md` ADR-005.

### `threshold_rules`
- `id` (UUID, PK)
- `jurisdiction` (string, matches `sites.jurisdiction`)
- `metric_type` (enum: `heat_index`, `dry_bulb_temperature`)
- `heat_index_threshold_f` (float, nullable) — holds the threshold value
  regardless of `metric_type`; the column name predates the
  `metric_type` split and was kept rather than renamed (a cosmetic-only
  migration was judged not worth the risk this close to submission)
- `mandated_action` (string)
- `citation` (string)

Static, seeded, **not user-editable** — see `decisions.md` ADR-003.

`metric_type` exists because different jurisdictions' regulations specify
different metrics: OSHA federal's NEP cites heat index; Cal/OSHA Title 8
§3395(b) explicitly defines its "Temperature" trigger as dry-bulb °F, not
heat index. The compliance engine reads this field to decide which
FortyGuard-derived value to compare against each rule — see
`fortyguard-integration.md`.

Seeded values, real and cited:
| Jurisdiction | Metric | Threshold | Action | Citation |
|---|---|---|---|---|
| osha_federal | heat_index | 80°F | Provide water/shade/rest breaks | OSHA NEP on Heat-Related Hazards (enforcement directive), revised Apr 10, 2026 |
| osha_federal | heat_index | 90°F | Mandatory rest breaks, 15min/2hr | OSHA NEP, revised Apr 10, 2026 |
| cal_osha | dry_bulb_temperature | 80°F | Provide shade/water access | Cal/OSHA Title 8 §3395(b) |
| cal_osha | dry_bulb_temperature | 95°F | High-heat procedures, buddy system | Cal/OSHA Title 8 §3395(e) |
| uae | dry_bulb_temperature | null (fixed window) | Work stoppage 12:30–15:00, Jun 15–Sep 15 | UAE Ministry of HR |

UAE checks are rejected explicitly at the API level (not silently passed)
since FortyGuard has no live data coverage outside the US — see
`fortyguard-integration.md`.

### `shift_windows`
- `id` (UUID, PK)
- `site_id` (FK → sites)
- `start_time`, `end_time`
- `days_active` (string, e.g. `"mon-fri"`)

Not yet consumed by the compliance engine — a check can be triggered
regardless of shift timing. Real, unbuilt roadmap item.

### `compliance_checks`
- `id` (UUID, PK)
- `site_id` (FK → sites)
- `checked_at` (timestamp)
- `heat_index_value` (float, °F) — holds whichever metric actually drove
  the decision for that jurisdiction (heat index for OSHA federal, raw
  temperature for Cal/OSHA); the column name is a known naming gap, same
  reasoning as `threshold_rules.heat_index_threshold_f` above
- `threshold_breached` (bool)
- `action_triggered` (string, nullable)

Append-only by design — the audit trail. Only `mode=historical` checks
write a row here; `mode=forecast` checks compute and return the
same fields without persisting, since a forecast is not a confirmed
observation.

**Known gap, not yet closed:** this table does not currently store which
`ThresholdRule` id/version, FortyGuard activity ID, or raw response
produced a given decision — meaning a stored check is not yet fully
reproducible/auditable back to its source.