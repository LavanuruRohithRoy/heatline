import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import ThresholdRule

THRESHOLD_RULES = [
    {
        "jurisdiction": "osha_federal",
        "heat_index_threshold_f": 80.0,
        "mandated_action": "provide_water_shade_rest_breaks",
        "citation": "OSHA National Emphasis Program on Heat Hazards, Nov 2025 — heat index 80°F triggers moderate-risk protocols",
    },
    {
        "jurisdiction": "osha_federal",
        "heat_index_threshold_f": 90.0,
        "mandated_action": "mandatory_rest_breaks_15min_per_2hr",
        "citation": "OSHA NEP — heat index 90°F triggers high-risk protocols",
    },
    {
        "jurisdiction": "cal_osha",
        "heat_index_threshold_f": 80.0,
        "mandated_action": "provide_shade_water_access",
        "citation": "Cal/OSHA Title 8 §3395 — outdoor high-heat procedures begin at 80°F",
    },
    {
        "jurisdiction": "cal_osha",
        "heat_index_threshold_f": 95.0,
        "mandated_action": "high_heat_procedures_mandatory_buddy_system",
        "citation": "Cal/OSHA Title 8 §3395 — high-heat procedures (buddy system, closer supervision) at 95°F",
    },
    {
        "jurisdiction": "uae",
        "heat_index_threshold_f": None,  # not heat-index-based — fixed daily window
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