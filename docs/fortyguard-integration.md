# FortyGuard Integration

## The three data levels

| Level | Endpoint | Question answered | Query shape |
|---|---|---|---|
| Sky | `heatmap` (`/v1/heatmap`) | How does temperature vary across an area? | Polygon (AOI), tiled |
| Ground | `env_params` (`/v1/env_params`) | What is a person at one point experiencing? | Single lat/lon |
| Surface | `satellite_segmentation` | Why is it hot here — what's the land cover? | Single lat/lon |

## `heatmap` — real, measured behavior

Endpoint: `POST /v1/heatmap`. `analytic_type=tcm` (used here) returns
snapshot temperature per tile, confirmed **°C** via direct response
inspection (the vendored client's own docstring incorrectly claims °F —
do not trust it without re-verifying).

**Credit cost, measured directly:** 4,220 credits per call, flat across
60m/100m granularity, on a ~1km² AOI.

**Data latency — a real, confirmed operational constraint:** FortyGuard's
processing pipeline can lag several days behind real time. This was
directly confirmed twice: multiple live test calls for "today" and "the
current hour" returned zero tiles across several separate attempts, and
FortyGuard's own status channel subsequently posted that their most
recently available data was several days old due to a backlog on their
end. Because of this, the compliance engine queries a fixed lookback
window (currently 6 days back) rather than "yesterday" or "today" — this
is a deliberate reliability choice, not the ideal freshness the product
aims for long-term.

## `env_params` — used only for heat-index jurisdictions

`env_params` requires a `temperature` value (°C) as input — it derives
heat index and related metrics from a temperature already obtained via
`heatmap`, it is not an independent sensor. The engine calls it **only**
when the site's jurisdiction has at least one `heat_index`-type
`ThresholdRule` (currently: OSHA federal). Cal/OSHA sites skip this call
entirely, since Cal/OSHA's regulation is defined in raw temperature — see
`data-model.md` and `decisions.md` ADR-008.

**Units — a second confirmed vendor field/reality mismatch:** the response
field is named `heat_index_celsius`, but its returned values are
empirically already in **Fahrenheit** (confirmed by inspecting a real
response: a 40–73.5 range matching a plausible real diurnal curve; treating
it as Celsius and converting produced a physically impossible ~164°F). No
conversion is applied to this field. This is the second time a FortyGuard
field name/docstring has not matched observed behavior (the first being
`tcm`'s claimed °F) — the operating rule for this codebase is: verify units
empirically against a real response, never trust a vendor field name or
docstring alone.

## `satellite_segmentation` — land-cover context

Single lat/lon query, called at a site's polygon centroid. Returns
land-cover category percentages and a satellite image. Used as a separate,
explanatory layer alongside the compliance decision (not a compliance
input itself) — implemented as `GET /sites/{id}/context` on our API,
cached long-term since land cover doesn't change day to day. Real per-call
credit cost has not yet been independently measured for this endpoint.

## Regional constraint

FortyGuard's current release covers **US locations only**, across all plan
tiers. UAE sites are seeded in `threshold_rules` as real regulatory data
but are explicitly rejected by the API at check-time (`400` response, not
a silent pass) — see `decisions.md` ADR-006.

## Forecast mode — current honest state

`POST /sites/{id}/check?mode=forecast` exists but currently uses the same
lookback-window query as historical mode; it does not yet perform true
look-ahead. Live testing of FortyGuard's documented near-future window
(current hour, current day) consistently returned empty results during
this build window, coinciding with the data-latency issue described above.
`mode=forecast`'s only real behavioral difference today is that it does
not persist a `ComplianceCheck` row — useful as a non-committal "preview"
call, not yet a predictive capability. True forecasting remains a real,
buildable roadmap item.

## Credits & billing — confirmed operational facts

- Credits deduct only on `Completed` status; a `Failed` task or a `400`
  input-validation rejection costs nothing — confirmed repeatedly in
  practice.
- A single fetch_fn timeout (task still `processing` after the client's
  internal wait limit) is a real failure mode encountered during
  development and is not yet mapped to a clean API error.