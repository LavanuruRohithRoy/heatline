import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import ThresholdRule, MetricType

THRESHOLD_RULES = [
    {
        "jurisdiction": "osha_federal",
        "metric_type": MetricType.HEAT_INDEX,
        "heat_index_threshold_f": 80.0,
        "mandated_action": "provide_water_shade_rest_breaks",
        "citation": "OSHA National Emphasis Program on Heat-Related Hazards (enforcement directive, not a binding federal standard), revised Apr 10, 2026 — heat index 80°F triggers moderate-risk protocols",
    },
    {
        "jurisdiction": "osha_federal",
        "metric_type": MetricType.HEAT_INDEX,
        "heat_index_threshold_f": 90.0,
        "mandated_action": "mandatory_rest_breaks_15min_per_2hr",
        "citation": "OSHA NEP (enforcement directive), revised Apr 10, 2026 — heat index 90°F triggers high-risk protocols",
    },
    {
        "jurisdiction": "cal_osha",
        "metric_type": MetricType.DRY_BULB_TEMPERATURE,
        "heat_index_threshold_f": 80.0,
        "mandated_action": "provide_shade_water_access",
        "citation": "Cal/OSHA Title 8 §3395(b) — 'Temperature' is defined as dry bulb °F; shade required above 80°F ambient",
    },
    {
        "jurisdiction": "cal_osha",
        "metric_type": MetricType.DRY_BULB_TEMPERATURE,
        "heat_index_threshold_f": 95.0,
        "mandated_action": "high_heat_procedures_mandatory_buddy_system",
        "citation": "Cal/OSHA Title 8 §3395(e) — high-heat procedures at 95°F ambient dry-bulb temperature",
    },
    {
        "jurisdiction": "uae",
        "metric_type": MetricType.DRY_BULB_TEMPERATURE,  # not currently evaluated live — FortyGuard is US-only
        "heat_index_threshold_f": None,
        "mandated_action": "work_stoppage_midday_window",
        "citation": "UAE Ministry of Human Resources — outdoor work ban 12:30pm-3:00pm, June 15-Sep 15 annually",
    },
]


async def seed():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        for rule in THRESHOLD_RULES:
            session.add(ThresholdRule(**rule))
        await session.commit()
    print(f"Seeded {len(THRESHOLD_RULES)} threshold rules.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())