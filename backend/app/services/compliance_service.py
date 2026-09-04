import logging
import statistics
from datetime import datetime, date, timedelta
from enum import Enum
from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Site, ThresholdRule, ComplianceCheck, MetricType, Jurisdiction
from app.integrations.fortyguard_service import create_heatmap_async, get_env_params_async
from app.integrations.cache import get_or_fetch_heatmap
from app.integrations.exceptions import TaskTimeoutError, TaskFailedError, FortyGuardError
from app.core.exceptions import UpstreamDataError, UnsupportedJurisdictionError

logger = logging.getLogger(__name__)

# ── Lookback window config ────────────────────────────────────────────────────
# FortyGuard's processed-data boundary is not a fixed offset. In practice the
# newest available day tends to be ~6 days behind today, but can drift to 7+.
# We walk backward from LOOKBACK_START_DAYS, retrying each day until we get
# non-empty features, and give up at LOOKBACK_MAX_DAYS to cap credit spend.
LOOKBACK_START_DAYS = 6
LOOKBACK_MAX_DAYS = 10

# ── Outlier threshold ─────────────────────────────────────────────────────────
# Physically implausible raw dry-bulb (°F) used only for the diagnostics log.
# This has no effect on compliance decisions.
_OUTLIER_THRESHOLD_F = 130.0


async def _fetch_vendor_payload(fetch_fn, *, is_historical: bool, **params):
    try:
        return await get_or_fetch_heatmap(fetch_fn, is_historical=is_historical, **params)
    except (TaskTimeoutError, TaskFailedError, FortyGuardError) as exc:
        raise UpstreamDataError(f"FortyGuard request failed: {exc}") from exc


async def find_latest_heatmap_date(
    polygon_aoi: dict,
    *,
    filter_type: int = 3,
    granularity: int = 60,
    analytic_type: str = "tcm",
) -> tuple[str, list]:
    """Walk backward from LOOKBACK_START_DAYS to LOOKBACK_MAX_DAYS (inclusive)
    and return the first date that yields non-empty tile features together with
    those features.

    cache.py already refuses to cache empty-feature responses, so a day that
    came back empty will re-hit FortyGuard on the next retry — correct behavior
    since we need to keep probing until we find data. Cached non-empty results
    are served from Redis as normal.

    Raises UpstreamDataError if every candidate day returns empty features.
    """
    for days_back in range(LOOKBACK_START_DAYS, LOOKBACK_MAX_DAYS + 1):
        target_date = (date.today() - timedelta(days=days_back)).isoformat()
        heatmap_params = {
            "polygon_aoi": polygon_aoi,
            "start_date": target_date,
            "filter_type": filter_type,
            "granularity": granularity,
            "analytic_type": analytic_type,
        }
        result = await _fetch_vendor_payload(
            lambda p=heatmap_params: create_heatmap_async(**p),
            is_historical=True,
            **heatmap_params,
        )
        features = result.get("result", {}).get("map_data", {}).get("features", [])
        if features:
            logger.info(
                "find_latest_heatmap_date: found %d features at days_back=%d (date=%s)",
                len(features), days_back, target_date,
            )
            return target_date, features

        logger.info(
            "find_latest_heatmap_date: empty at days_back=%d (date=%s), retrying",
            days_back, target_date,
        )

    raise UpstreamDataError(
        f"No heatmap features found between {LOOKBACK_START_DAYS} and "
        f"{LOOKBACK_MAX_DAYS} days back — FortyGuard data may not yet be available "
        "for this location and date range."
    )


def _tile_diagnostics(features: list) -> dict:
    """Compute pure tile-distribution statistics from a raw feature list.

    Uses the same field (max_temperature, Celsius) that run_compliance_check
    uses to pick the worst tile, so the numbers directly explain the selected
    value. Conversion to °F is done here for the diagnostics only.

    Returns a dict with:
        tile_count, min_temp_f, max_temp_f, mean_temp_f, median_temp_f,
        outliers_over_130f   (count of tiles whose °F reading exceeds the
                              physically-implausible threshold)
    """
    temps_c = [f["properties"]["max_temperature"] for f in features]
    temps_f = [(t * 9 / 5) + 32 for t in temps_c]
    return {
        "tile_count": len(temps_f),
        "min_temp_f": min(temps_f),
        "max_temp_f": max(temps_f),
        "mean_temp_f": statistics.mean(temps_f),
        "median_temp_f": statistics.median(temps_f),
        "outliers_over_130f": sum(1 for t in temps_f if t > _OUTLIER_THRESHOLD_F),
    }


class CheckMode(str, Enum):
    HISTORICAL = "historical"
    FORECAST = "forecast"


async def run_compliance_check(session: AsyncSession, site: Site, mode: CheckMode = CheckMode.HISTORICAL):
    if site.jurisdiction == Jurisdiction.UAE:
        raise UnsupportedJurisdictionError(
            "UAE sites cannot be checked automatically: FortyGuard currently covers US locations only, "
            "so no live compliance evaluation is available for this jurisdiction."
        )

    filter_type = 3

    # ── PART 2: walk back to find the newest date with real data ─────────────
    target_date, features = await find_latest_heatmap_date(
        site.polygon_geojson,
        filter_type=filter_type,
        granularity=60,
        analytic_type="tcm",
    )

    # ── PART 1: tile diagnostics (read-only, no effect on compliance logic) ──
    diag = _tile_diagnostics(features)
    logger.info(
        "[tile-diagnostics] site=%s tiles=%d min=%.1f°F max=%.1f°F "
        "mean=%.1f°F median=%.1f°F outliers_over_130f=%d",
        site.id,
        diag["tile_count"],
        diag["min_temp_f"],
        diag["max_temp_f"],
        diag["mean_temp_f"],
        diag["median_temp_f"],
        diag["outliers_over_130f"],
    )

    # ── Existing max-tile selection logic — UNCHANGED ─────────────────────────
    max_tile = max(features, key=lambda f: f["properties"]["max_temperature"])
    max_tile_temp_c = max_tile["properties"]["max_temperature"]
    max_tile_temp_f = (max_tile_temp_c * 9 / 5) + 32

    tile_centroid = shape(max_tile["geometry"]).centroid
    lon, lat = tile_centroid.x, tile_centroid.y

    logger.info("TCM max tile: %.2f°C (%.2f°F) at (%.5f, %.5f)", max_tile_temp_c, max_tile_temp_f, lat, lon)

    rules_result = await session.execute(
        select(ThresholdRule)
        .where(ThresholdRule.jurisdiction == site.jurisdiction.value)
        .order_by(ThresholdRule.heat_index_threshold_f.desc().nullslast())
    )
    rules = rules_result.scalars().all()

    needs_heat_index = any(r.metric_type == MetricType.HEAT_INDEX for r in rules)

    heat_index_f = None
    if needs_heat_index:
        env_params_kwargs = {
            "latitude": lat,
            "longitude": lon,
            "temperature": max_tile_temp_c,
            "start_date": target_date,
            "filter_type": filter_type,
        }

        env_result = await _fetch_vendor_payload(
            lambda: get_env_params_async(**env_params_kwargs),
            is_historical=True,
            **env_params_kwargs,
        )
        locations = env_result["result"]["locations"]
        if not locations:
            raise UpstreamDataError("No locations returned in env_params response")
        raw_values = locations[0]["parameters"]["heat_index_celsius"]
        clean_values = [v for v in raw_values if v is not None]
        if not clean_values:
            raise UpstreamDataError("No non-null heat_index_celsius values in env_params response")
        heat_index_f = (max(clean_values) * 9 / 5) + 32
        logger.info("env_params heat index: %.2f°F", heat_index_f)

    breached_rule = None
    for rule in rules:
        if rule.heat_index_threshold_f is None:
            continue
        if rule.metric_type == MetricType.HEAT_INDEX:
            if heat_index_f is not None and heat_index_f >= rule.heat_index_threshold_f:
                breached_rule = rule
                break
        else:
            if max_tile_temp_f >= rule.heat_index_threshold_f:
                breached_rule = rule
                break

    recorded_value = heat_index_f if needs_heat_index and heat_index_f is not None else max_tile_temp_f

    metric_label = "Heat Index" if needs_heat_index else "Temperature"
    threshold_value = breached_rule.heat_index_threshold_f if breached_rule else (
        rules[-1].heat_index_threshold_f if rules else None
    )

    if mode == CheckMode.FORECAST:
        return {
            "site_id": site.id,
            "mode": "forecast",
            "forecast_for": target_date,
            "heat_index_value": recorded_value,
            "threshold_breached": breached_rule is not None,
            "action_triggered": breached_rule.mandated_action if breached_rule else None,
            "metric_label": metric_label,
            "data_as_of": target_date,
            "threshold_value": threshold_value,
        }

    check = ComplianceCheck(
        site_id=site.id,
        checked_at=datetime.utcnow(),
        heat_index_value=recorded_value,
        threshold_breached=breached_rule is not None,
        action_triggered=breached_rule.mandated_action if breached_rule else None,
    )
    check.metric_label = metric_label
    check.data_as_of = target_date
    check.threshold_value = threshold_value
    session.add(check)
    await session.commit()
    await session.refresh(check)
    return check