import uuid
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import date, timedelta

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user, CurrentUser
from app.core.rate_limit import enforce_check_rate_limit, PLAN_LIMITS
from app.core.exceptions import DomainError, SiteNotFoundError, UpstreamDataError
from app.models import Site, Jurisdiction, Organization, Plan
from app.services.compliance_service import run_compliance_check
from app.routes.auth import router as auth_router
from app.schemas.site import SiteResponse
from app.schemas.compliance_check import ComplianceCheckResponse
from app.schemas.organization import OrganizationResponse
from app.core.exceptions import DomainError, SiteNotFoundError, PermissionDeniedError
from app.services.compliance_service import run_compliance_check, CheckMode
from shapely.geometry import shape as shapely_shape
from app.integrations.fortyguard_service import get_satellite_segmentation_async
from app.integrations.exceptions import TaskTimeoutError, TaskFailedError, FortyGuardError

app = FastAPI(title="Heatline API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/public/sites", response_model=list[SiteResponse])
async def public_sites(db: AsyncSession = Depends(get_db)):
    """No auth required — only returns sites belonging to designated public-demo orgs."""
    result = await db.execute(
        select(Site)
        .join(Organization, Site.org_id == Organization.id)
        .where(Organization.is_public_demo == True)  # noqa: E712
    )
    return result.scalars().all()


class SiteCreate(BaseModel):
    name: str
    polygon_geojson: dict
    jurisdiction: Jurisdiction


@app.post("/sites", response_model=SiteResponse)
async def create_site(
    payload: SiteCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, current_user.org_id)
    existing_count_result = await db.execute(
        select(Site).where(Site.org_id == current_user.org_id)
    )
    existing_count = len(existing_count_result.scalars().all())
    max_sites = PLAN_LIMITS[org.plan]["max_sites"]
    if existing_count >= max_sites:
        raise DomainError(f"Site limit reached: {max_sites} sites on the {org.plan.value} plan")

    site = Site(org_id=current_user.org_id, **payload.model_dump())
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site


@app.get("/sites", response_model=list[SiteResponse])
async def list_sites(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Site).where(Site.org_id == current_user.org_id))
    return result.scalars().all()


@app.post("/sites/{site_id}/check")
async def check_site(
    site_id: uuid.UUID,
    mode: CheckMode = CheckMode.HISTORICAL,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    site = await db.get(Site, site_id)
    if site is None or site.org_id != current_user.org_id:
        raise SiteNotFoundError("Site not found")

    org = await db.get(Organization, current_user.org_id)
    await enforce_check_rate_limit(str(current_user.org_id), org.plan)

    try:
        result = await run_compliance_check(db, site, mode=mode)
    except (TaskTimeoutError, TaskFailedError, FortyGuardError) as exc:
        raise UpstreamDataError(f"FortyGuard request failed: {exc}") from exc
    return result


@app.post("/organizations/upgrade", response_model=OrganizationResponse)
async def upgrade_org(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simulated upgrade — flips plan to Standard. No real billing integration."""
    if current_user.role != "admin":
        raise PermissionDeniedError("Only admins can upgrade the organization")
    org = await db.get(Organization, current_user.org_id)
    org.plan = Plan.STANDARD
    await db.commit()
    await db.refresh(org)
    return org


@app.get("/sites/{site_id}/context")
async def site_context(
    site_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    site = await db.get(Site, site_id)
    if site is None or site.org_id != current_user.org_id:
        raise SiteNotFoundError("Site not found")

    centroid = shapely_shape(site.polygon_geojson["features"][0]["geometry"]).centroid
    target_date = (date.today() - timedelta(days=6)).isoformat()

    params = {
        "latitude": centroid.y,
        "longitude": centroid.x,
        "start_date": target_date,
        "filter_type": 3,
        "granularity": 60,
    }
    result = await get_or_fetch_heatmap(
        lambda: get_satellite_segmentation_async(**params),
        is_historical=True,
        **params,
    )
    segments = result.get("result", {}).get("segmentation", {}).get("segments", {})
    image = result.get("result", {}).get("orignal_image", [""])[0]
    return {"site_id": site.id, "segments": segments, "satellite_image_base64": image}