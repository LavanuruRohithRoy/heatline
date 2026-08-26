# FortyGuard Integration

## The three data levels

FortyGuard's endpoints answer three distinct questions, at three distinct
spatial scales:

| Level | Endpoint | Question answered | Query shape |
|---|---|---|---|
| Sky | `heatmap` (`/v1/heatmap`) | How does temperature vary across an area, over time? | Polygon (AOI), tiled |
| Ground | `env_params` (`/v1/env_params`) | What is a person at one point actually experiencing? | Single lat/lon |
| Surface | `satellite`/`streetview` segmentation | Why is it hot here — what's the land cover? | Single lat/lon |

None of these is a superset of the others. The compliance engine needs
signals from more than one to answer the real question correctly — see
below.

## `heatmap` — the four `analytic_type` values

Endpoint: `POST /v1/heatmap`, Premium tier max AOI 50 mi² (Basic: 10 mi²).

| `analytic_type` | Returns | Units | Real example we measured |
|---|---|---|---|
| `tcm` (default) | Snapshot temperature per tile | °C | `max_temperature: 37.8` (confirmed via live response, contradicts our vendored client's docstring which claimed °F) |
| `exceedance` | Hours per tile above/below a threshold | hour | `value: 10.0` = 10 hours exceeded 26.7°C in the queried window |
| `persistence` | Longest *continuous* run of hours past threshold | hour | Not yet measured live |
| `time_of_measure` | UTC hour (0–23) of each tile's peak | hour-of-day | Not yet measured live |

**`tcm`'s real response shape** (confirmed by direct inspection, not
documentation — the vendored client's docstring was wrong about units):
```json
{
  "properties": {
    "tile_id": 0,
    "average_temperature": 28.03,
    "min_temperature": 21.90,
    "max_temperature": 37.80
  }
}
```
Official docs (fetched later) confirm: `tcm` returns °C per tile;
`exceedance`/`persistence`/`time_of_measure` return values in hours
(`stats_data.units = "hour"`). This matches what we found empirically.

**Credit cost, measured directly:** 4,220 credits per call, confirmed flat
across 60m and 100m granularity (identical cost, not scaled by resolution)
on a ~1km² AOI. At 5,000,000 Premium credits, that's roughly 1,184 calls
before exhausting the monthly allocation — before caching. Caching
(Redis, see `04-decisions.md` ADR-004) is what makes repeated/demo usage
sustainable within this budget.

**Forecasting capability (from official docs, not yet used):**
`start_date` accepts values up to 12 hours into the future — `heatmap`
supports genuine short-term forecasting, not just historical/current
snapshots. This is a real, documented capability that could support a
"will this site breach threshold in the next few hours" feature. Not built
in the current scope; noted as a real roadmap item in
`07-known-limitations-and-roadmap.md`.

## `env_params` — the actually-correct compliance signal

Endpoint: `POST /v1/env_params`. Basic tier: 3 parameters/request max.
Premium: full access.

**Critical integration detail, confirmed from official docs:** `env_params`
is not an independent sensor — it takes a `temperature` value (°C) as a
**required input** and derives heat index, apparent temperature, wet-bulb
temperature, humidity, AQI, and solar irradiance from it plus lat/lon/time.
Docs state explicitly the date/time "should match the heatmap you generated
for the same location and time."

This means the real pipeline is a **two-step chain**, not two independent
calls:
```
heatmap (tcm) → tile max_temperature (°C)
     ↓
env_params(lat, lon, temperature=that_value, date_time=same_window)
     ↓
heat_index_celsius  ← the actual OSHA/Cal-OSHA-relevant metric
```

**Why this matters for correctness, not just completeness:** OSHA's NEP and
Cal/OSHA's Title 8 §3395 both cite *heat index* (temperature + humidity
combined), not raw ambient temperature. A site could show a compliant raw
temperature while its real heat index — the number the regulation actually
references — is already past threshold on a humid day. Using `tcm` alone,
as the initial implementation did, is a genuine correctness gap, not a
missing nice-to-have. This was caught during system-design review, not
during initial build — see `04-decisions.md` ADR-001.

**Cost implication:** this makes each real compliance check *two*
credit-costing calls (`heatmap` + `env_params`), not one. Budget planning
in `03b-credit-economics.md`-equivalent sections above already assumes
this.

**Units note:** `env_params` wants its `temperature` input in **Celsius**.
`heat_intelligence` (below) wants its `temperature` input in **Fahrenheit**.
Same conceptual field, different units, different endpoints — exactly the
class of vendor inconsistency that caused the original tcm-unit bug.
Explicit unit conversion at every boundary crossing between these two
endpoints is mandatory, not optional cleanup.

## `satellite_segmentation` / `street_view_segmentation` — the "why"

Both Premium-only, single lat/lon queries. Return land-cover classification
(asphalt, vegetation, building shadow, etc.) as percentages plus a
segmentation mask image. Neither returns a temperature.

**Real product value, not just checkbox Premium usage:** two sites at
identical heat index don't carry identical worker risk if one is 80%
unshaded asphalt and the other has tree cover. This is the contextual
explanation layer, shown alongside the compliance number, not a substitute
for it.

## `heat_intelligence` — the audit deliverable

Premium-only. Takes lat/lon/temperature(°F)/date + an `analysis` array
(subset of `geographic`, `environmental`, `urban`, `events`,
`anthropogenic`). Generates a PDF report, delivered via a **temporary
signed download link** (not streamed directly) — the docs are explicit
that this link must be used immediately and not logged or shared, and that
generation can take several minutes.

**Real product framing:** this is not a demo flourish. A real HSE manager's
actual deliverable to a regulator or insurer is a *document*, not a live
dashboard. This endpoint is the closest thing FortyGuard offers to that
artifact directly. Treated as a genuine roadmap priority — see
`07-known-limitations-and-roadmap.md`.

## Regional constraint — the one that reshaped scope

Official docs, `Known Limitations`: **all current-release endpoints are
restricted to locations within the United States**, across every plan
tier (Basic, Premium, Startup).

This directly affects the seeded `uae` `ThresholdRule` — that regulatory
data is real and stays in the schema, but it is **not currently
queryable via live FortyGuard data**. This is stated plainly rather than
worked around: the product's live-checkable scope is US jurisdictions only
(`osha_federal`, `cal_osha`) for the current build; UAE support is
correctly modeled in the schema and blocked purely by an upstream vendor
constraint, not a gap in our design. See ADR-006 in `04-decisions.md`.

## Credits & billing — operational facts from official docs

- Credits deduct **only on `Completed` status** — a `Failed` task costs
  nothing. Confirmed empirically: every 400/500 error hit during
  development cost zero credits; every successful completion cost exactly
  4,220.
- Unused credits do **not** roll over between billing cycles.
- Requests violating input constraints (bad polygon, bad date range, etc.)
  return `400` and are never charged — this is why aggressive
  trial-and-error during development, however frustrating in the moment,
  never actually put the credit budget at risk from failed attempts; only
  successful completions with wrong assumptions did.