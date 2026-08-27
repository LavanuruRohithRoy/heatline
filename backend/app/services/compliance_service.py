import logging
from datetime import datetime, date, timedelta
from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Site, ThresholdRule, ComplianceCheck, MetricType
from app.integrations.fortyguard_service import create_heatmap_async, get_env_params_async
from app.integrations.cache import get_or_fetch_heatmap

logger = logging.getLogger(__name__)


async def run_compliance_check(session: AsyncSession, site: Site) -> ComplianceCheck:
    """
    Step 1 (always): heatmap/tcm -> worst-case (max-temperature) tile across the site polygon.
    This alone is sufficient for jurisdictions whose regulation is defined in raw
    dry-bulb temperature (e.g. Cal/OSHA Title 8 §3395(b) explicitly defines
    "Temperature" as dry bulb °F, not heat index).

    Step 2 (conditional): env_params, queried at the max tile's centroid, only when
    at least one applicable rule for this site's jurisdiction is heat-index-based
    (e.g. OSHA federal NEP). Skipping this call for dry-bulb-only jurisdictions is
    both more correct (right metric per regulation) and cheaper (one fewer paid call).
    """
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    heatmap_params = {
        "polygon_aoi": site.polygon_geojson,
        "start_date": yesterday,
        "filter_type": 3,
        "granularity": 60,
        "analytic_type": "tcm",
    }
    heatmap_result = await get_or_fetch_heatmap(
        lambda: create_heatmap_async(**heatmap_params),
        is_historical=True,
        **heatmap_params,
    )

    features = heatmap_result["result"]["map_data"]["features"]
    if not features:
        raise ValueError("No features returned in heatmap response")

    max_tile = max(features, key=lambda f: f["properties"]["max_temperature"])
    max_tile_temp_c = max_tile["properties"]["max_temperature"]
    max_tile_temp_f = (max_tile_temp_c * 9 / 5) + 32  # tcm is confirmed °C

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
            "start_date": yesterday,
            "filter_type": 3,
        }
        env_result = await get_or_fetch_heatmap(
            lambda: get_env_params_async(**env_params_kwargs),
            is_historical=True,
            **env_params_kwargs,
        )
        locations = env_result["result"]["locations"]
        if not locations:
            raise ValueError("No locations returned in env_params response")
        raw_values = locations[0]["parameters"]["heat_index_celsius"]
        # NOTE: field is misnamed by FortyGuard — values are empirically already °F, no conversion applied.
        clean_values = [v for v in raw_values if v is not None]
        if not clean_values:
            raise ValueError("No non-null heat_index_celsius values in env_params response")
        heat_index_f = max(clean_values)
        logger.info("env_params heat index: %.2f°F", heat_index_f)

    breached_rule = None
    for rule in rules:
        if rule.heat_index_threshold_f is None:
            continue  # fixed-window rules (UAE) — time-based, handled separately

        if rule.metric_type == MetricType.HEAT_INDEX:
            if heat_index_f is not None and heat_index_f >= rule.heat_index_threshold_f:
                breached_rule = rule
                break
        else:  # DRY_BULB_TEMPERATURE
            if max_tile_temp_f >= rule.heat_index_threshold_f:
                breached_rule = rule
                break

    # Store the metric that actually drove the decision for this jurisdiction, not
    # always the heat index — otherwise a Cal/OSHA record would misleadingly show
    # a heat-index number for a decision that was legally based on raw temperature.
    recorded_value = heat_index_f if needs_heat_index and heat_index_f is not None else max_tile_temp_f

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