import logging
from datetime import datetime, date, timedelta
from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Site, ThresholdRule, ComplianceCheck
from app.integrations.fortyguard_service import create_heatmap_async, get_env_params_async
from app.integrations.cache import get_or_fetch_heatmap  # generic despite the name — works for any cached fetch

logger = logging.getLogger(__name__)


async def run_compliance_check(session: AsyncSession, site: Site) -> ComplianceCheck:
    """
    Two-step chain, per FortyGuard's official docs:
      1. heatmap (tcm) -> find the worst-case (max-temperature) tile across the site polygon
      2. env_params, queried at that tile's centroid -> real heat index

    Heat index (not raw temperature) is the metric OSHA NEP / Cal-OSHA §3395
    actually cite. Using the max tile's own location (not the polygon's overall
    centroid) keeps the worst-case design principle consistent end-to-end.
    """
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # --- Step 1: heatmap / tcm ---
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

    tile_centroid = shape(max_tile["geometry"]).centroid
    lon, lat = tile_centroid.x, tile_centroid.y

    logger.warning(
        "TCM max tile: %.2f°C at (%.5f, %.5f)", max_tile_temp_c, lat, lon
    )

    # --- Step 2: env_params, chained on the tcm result ---
    env_params_kwargs = {
        "latitude": lat,
        "longitude": lon,
        "temperature": max_tile_temp_c,  # env_params requires °C input
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

    # NOTE: despite the field being named "heat_index_celsius" in FortyGuard's own
    # docs, the returned values are empirically already in Fahrenheit (confirmed by
    # a real response: values ranged ~40-73.5, matching an LA August day's real F
    # curve; a second C->F conversion on top produced a physically impossible 164°F).
    # This mirrors the earlier tcm docstring mislabel — vendor field names are not
    # to be trusted for units without empirical verification.
    raw_heat_index_values = locations[0]["parameters"]["heat_index_celsius"]
    logger.warning("RAW HEAT INDEX VALUES: %s", raw_heat_index_values)
    heat_index_values = [v for v in raw_heat_index_values if v is not None]
    if not heat_index_values:
        raise ValueError("No non-null heat_index_celsius values in env_params response")

    max_heat_index_f = max(heat_index_values)  # already °F, no conversion

    logger.warning("Real heat_index: %.2f°F", max_heat_index_f)

    # --- Threshold comparison (unchanged logic, now fed the correct metric) ---
    rules_result = await session.execute(
        select(ThresholdRule)
        .where(ThresholdRule.jurisdiction == site.jurisdiction.value)
        .order_by(ThresholdRule.heat_index_threshold_f.desc().nullslast())
    )
    rules = rules_result.scalars().all()

    breached_rule = None
    for rule in rules:
        if rule.heat_index_threshold_f is None:
            continue
        if max_heat_index_f >= rule.heat_index_threshold_f:
            breached_rule = rule
            break

    check = ComplianceCheck(
        site_id=site.id,
        checked_at=datetime.utcnow(),
        heat_index_value=max_heat_index_f,
        threshold_breached=breached_rule is not None,
        action_triggered=breached_rule.mandated_action if breached_rule else None,
    )
    session.add(check)
    await session.commit()
    await session.refresh(check)
    return check