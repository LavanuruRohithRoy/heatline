import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import Organization, Site, Jurisdiction, Plan

DEMO_SITES = [
    {
        "name": "LA Construction Site",
        "jurisdiction": Jurisdiction.OSHA_FEDERAL,
        "polygon_geojson": {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": {
                "type": "Polygon",
                "coordinates": [[[-118.2500,34.0500],[-118.2400,34.0500],[-118.2400,34.0600],[-118.2500,34.0600],[-118.2500,34.0500]]]
            }}]
        },
    },
    {
        "name": "Sacramento Warehouse Yard",
        "jurisdiction": Jurisdiction.CAL_OSHA,
        "polygon_geojson": {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": {
                "type": "Polygon",
                "coordinates": [[[-121.5000,38.5800],[-121.4900,38.5800],[-121.4900,38.5900],[-121.5000,38.5900],[-121.5000,38.5800]]]
            }}]
        },
    },
]


async def seed_demo():
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url, connect_args={"statement_cache_size": 0})
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        existing_org = await session.execute(
            select(Organization).where(Organization.is_public_demo.is_(True)).limit(1)
        )
        org = existing_org.scalar_one_or_none()

        if org is None:
            org = Organization(name="Heatline Demo Org", plan=Plan.STANDARD, is_public_demo=True)
            session.add(org)
            await session.flush()

            for s in DEMO_SITES:
                session.add(Site(org_id=org.id, **s))

            await session.commit()
            print(f"Seeded demo org {org.id} with {len(DEMO_SITES)} sites")
        else:
            print(f"Demo org already exists: {org.id}; skipping seed")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_demo())