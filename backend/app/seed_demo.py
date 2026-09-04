import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models import Organization, Site, Jurisdiction, Plan, ComplianceCheck
from app.services.compliance_service import run_compliance_check, CheckMode

DEMO_SITES = [
    {
        "name": "LA Construction Site",
        "jurisdiction": Jurisdiction.OSHA_FEDERAL,
        "polygon_geojson": {
            "type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": {
                "type": "Polygon",
                "coordinates": [[[-118.2500, 34.0500], [-118.2400, 34.0500], [-118.2400, 34.0600], [-118.2500, 34.0600], [-118.2500, 34.0500]]]
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
                "coordinates": [[[-121.5000, 38.5800], [-121.4900, 38.5800], [-121.4900, 38.5900], [-121.5000, 38.5900], [-121.5000, 38.5800]]]
            }}]
        },
    },
]

# How far back we look when deciding whether a site already has a "fresh enough"
# compliance check and therefore doesn't need another FortyGuard API call.
_IDEMPOTENCY_WINDOW_HOURS = 24


async def _seed_demo_compliance_checks(session: AsyncSession, sites: list) -> None:
    """Run one historical compliance check per demo site, skipping any site
    that already has a check within the last _IDEMPOTENCY_WINDOW_HOURS hours.

    Extracted as a module-level function so it can be patched/tested independently
    without going through the full seed_demo() engine-setup path.

    A failed check is logged but does not abort seeding — the site will still
    appear on the landing page, just without a status badge until the next deploy.
    """
    cutoff = datetime.utcnow() - timedelta(hours=_IDEMPOTENCY_WINDOW_HOURS)
    for site in sites:
        existing = await session.execute(
            select(ComplianceCheck)
            .where(ComplianceCheck.site_id == site.id)
            .where(ComplianceCheck.checked_at >= cutoff)
            .limit(1)
        )
        if existing.scalar_one_or_none() is not None:
            print(
                f"  {site.name}: check found within {_IDEMPOTENCY_WINDOW_HOURS}h window"
                " — skipping FortyGuard call"
            )
            continue

        try:
            check = await run_compliance_check(session, site, mode=CheckMode.HISTORICAL)
            status = "BREACHED" if check.threshold_breached else "OK"
            print(f"  {site.name}: check complete — {status} ({check.heat_index_value:.1f}°F)")
        except Exception as exc:  # noqa: BLE001
            print(f"  {site.name}: compliance check failed ({exc!r}), continuing")


async def seed_demo():
    database_url = settings.database_url
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_name_func": lambda: "",
        },
    )
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
            print(f"Demo org already exists: {org.id}; skipping site seed")

        # Load the demo sites (whether just created or pre-existing) and run
        # idempotent compliance checks so the landing page shows real status on
        # every deploy without re-spending credits when checks are still fresh.
        print("Running idempotent compliance checks for demo sites…")
        sites_result = await session.execute(
            select(Site).where(Site.org_id == org.id)
        )
        demo_sites = list(sites_result.scalars().all())
        await _seed_demo_compliance_checks(session, demo_sites)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_demo())