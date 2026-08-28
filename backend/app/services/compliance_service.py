import logging
from datetime import datetime, date, timedelta
from enum import Enum
from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Site, ThresholdRule, ComplianceCheck, MetricType
from app.integrations.fortyguard_service import create_heatmap_async, get_env_params_async
from app.integrations.cache import get_or_fetch_heatmap
from app.core.exceptions import UpstreamDataError

logger = logging.getLogger(__name__)


class CheckMode(str, Enum):
    HISTORICAL = "historical"
    FORECAST = "forecast"


async def run_compliance_check(session: AsyncSession, site: Site, mode: CheckMode = CheckMode.HISTORICAL):
    target_date = (date.today() - timedelta(days=6)).isoformat()
    filter_type = 3
    start_time = None
    is_historical_cache = True

    heatmap_params = {
        "polygon_aoi": site.polygon_geojson,
        "start_date": target_date,
        "filter_type": filter_type,
        "granularity": 60,
        "analytic_type": "tcm",
    }

    heatmap_result = await get_or_fetch_heatmap(
        lambda: create_heatmap_async(**heatmap_params),
        is_historical=is_historical_cache,
        **heatmap_params,
    )

    features = heatmap_result["result"]["map_data"]["features"]
    if not features:
        raise UpstreamDataError("No features returned in heatmap response")

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

        env_result = await get_or_fetch_heatmap(
            lambda: get_env_params_async(**env_params_kwargs),
            is_historical=is_historical_cache,
            **env_params_kwargs,
        )
        locations = env_result["result"]["locations"]
        if not locations:
            raise UpstreamDataError("No locations returned in env_params response")
        raw_values = locations[0]["parameters"]["heat_index_celsius"]
        clean_values = [v for v in raw_values if v is not None]
        if not clean_values:
            raise UpstreamDataError("No non-null heat_index_celsius values in env_params response")
        heat_index_f = max(clean_values)
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

    if mode == CheckMode.FORECAST:
        return {
            "site_id": site.id,
            "mode": "forecast",
            "forecast_for": target_date,
            "heat_index_value": recorded_value,
            "threshold_breached": breached_rule is not None,
            "action_triggered": breached_rule.mandated_action if breached_rule else None,
        }

    check = ComplianceCheck(
        site_id=site.id,
        checked_at=datetime.utcnow(),
        heat_index_value=recorded_value,
        threshold_breached=breached_rule is not None,
        action_triggered=breached_rule.mandated_action if breached_rule else None,
    )
    session.add(check)
    await session.commit()
    await session.refresh(check)
    return check