import logging
from datetime import datetime, date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Site, ThresholdRule, ComplianceCheck
from app.integrations.fortyguard_service import create_heatmap_async

logger = logging.getLogger(__name__)


async def run_compliance_check(session: AsyncSession, site: Site) -> ComplianceCheck:
    """
    Pull heat index for a site's AOI, compare against its jurisdiction's
    threshold rules, and record the outcome. Uses MAX tile value across the site
    polygon — worst-case tile determines the action, since this is a safety tool
    and under-triggering a heat protocol is the unacceptable failure mode.
    """
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    heatmap_result = await create_heatmap_async(
        polygon_aoi=site.polygon_geojson,
        start_date=yesterday,
        filter_type=3,  # single_day — proven working pattern from probe_credits.py
        granularity=60,
        analytic_type="tcm",
    )

    features = heatmap_result["result"]["map_data"]["features"]
    if not features:
        raise ValueError("No features returned in heatmap response")

    logger.warning("RAW FIRST FEATURE PROPERTIES: %s", features[0]["properties"])

    tile_values = [f["properties"]["max_temperature"] for f in features]
    max_heat_index = max(tile_values)
    # FortyGuard tcm tiles return Celsius, not °F as the client docstring states —
    # confirmed via live response inspection (28-38 range = plausible LA summer Celsius)
    max_heat_index_f = (max_heat_index * 9 / 5) + 32

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
        checked_at=datetime.now(datetime.UTC),
        heat_index_value=max_heat_index_f,
        threshold_breached=breached_rule is not None,
        action_triggered=breached_rule.mandated_action if breached_rule else None,
    )
    session.add(check)
    await session.commit()
    await session.refresh(check)
    return check