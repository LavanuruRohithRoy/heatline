import uuid
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, field_validator
from datetime import date, timedelta

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user, CurrentUser, hash_password
from app.core.rate_limit import enforce_check_rate_limit, PLAN_LIMITS
from app.core.exceptions import DomainError, SiteNotFoundError, UpstreamDataError, PermissionDeniedError
from app.models import Site, Jurisdiction, Organization, Plan, ThresholdRule, MetricType, User, UserRole, ComplianceCheck
from app.services.compliance_service import run_compliance_check, CheckMode, find_latest_heatmap_date, _tile_diagnostics
from app.integrations.fortyguard_service import create_heatmap_async, get_satellite_segmentation_async
from app.integrations.cache import get_or_fetch_heatmap
from app.integrations.exceptions import TaskTimeoutError, TaskFailedError, FortyGuardError
from app.routes.auth import router as auth_router
from app.schemas.site import SiteResponse, PublicSiteResponse
from app.schemas.compliance_check import ComplianceCheckResponse
from app.schemas.organization import OrganizationResponse
from app.schemas.heatmap import HeatmapTilesResponse
from shapely.geometry import shape as shapely_shape

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


def _normalize_satellite_context_payload(result: dict) -> tuple[dict, str]:
    """Normalize API-version differences in the FortyGuard satellite payload."""
    payload = result.get("result", {}) if isinstance(result, dict) else {}
    segmentation = payload.get("segmentation") or {}
    segments = segmentation.get("segments") or {}

    candidates: list[str] = []
    for key in ("original_image", "orignal_image"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(str(item) for item in value if item is not None)
        elif value is not None:
            candidates.append(str(value))

    image_content = segmentation.get("image_content")
    if image_content is not None:
        candidates.append(str(image_content))

    image = ""
    for candidate in candidates:
        if not candidate:
            continue
        image = candidate
        break

    if image and not image.startswith("data:image/") and "base64," not in image:
        image = f"data:image/png;base64,{image}"
    return segments, image


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})


@app.get("/health")
@app.head("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/public/sites", response_model=list[PublicSiteResponse])
async def public_sites(db: AsyncSession = Depends(get_db)):
    """No auth required — only returns sites belonging to designated public-demo orgs."""
    result = await db.execute(
        select(Site)
        .join(Organization, Site.org_id == Organization.id)
        .where(Organization.is_public_demo == True)  # noqa: E712
    )
    sites = result.scalars().all()
    if not sites:
        return []

    site_ids = [site.id for site in sites]
    checks_result = await db.execute(
        select(ComplianceCheck)
        .where(ComplianceCheck.site_id.in_(site_ids))
        .order_by(ComplianceCheck.checked_at.desc())
    )
    latest_by_site: dict = {}
    for check in checks_result.scalars():
        if check.site_id not in latest_by_site:
            latest_by_site[check.site_id] = check

    payload = []
    for site in sites:
        latest = latest_by_site.get(site.id)
        payload.append(
            PublicSiteResponse(
                **SiteResponse.model_validate(site).model_dump(),
                latest_result=(
                    ComplianceCheckResponse.model_validate(latest) if latest else None
                ),
            )
        )
    return payload


class SiteCreate(BaseModel):
    name: str
    polygon_geojson: dict
    jurisdiction: Jurisdiction


class MemberCreateRequest(BaseModel):
    email: EmailStr
    password: str
    role: UserRole

    @field_validator("role")
    @classmethod
    def reject_admin_role(cls, value: UserRole) -> UserRole:
        if value == UserRole.ADMIN:
            raise ValueError("Admin accounts can only be created via registration")
        return value


class MemberResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole

    model_config = {"from_attributes": True}


_SITE_WRITE_ROLES = {UserRole.ADMIN.value, UserRole.HSE_MANAGER.value}


def _require_site_write_access(current_user: CurrentUser) -> None:
    if current_user.role not in _SITE_WRITE_ROLES:
        raise PermissionDeniedError("Viewers cannot create sites or run compliance checks")


@app.post("/sites", response_model=SiteResponse)
async def create_site(
    payload: SiteCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_site_write_access(current_user)
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
    _require_site_write_access(current_user)
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

@app.get("/organizations/me", response_model=OrganizationResponse)
async def get_my_organization(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise SiteNotFoundError("Organization not found")
    return org

@app.post("/organizations/members", response_model=MemberResponse)
async def create_organization_member(
    payload: MemberCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.ADMIN.value:
        raise PermissionDeniedError("Only admins can add organization members")

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        org_id=current_user.org_id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


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
    org = await db.get(Organization, current_user.org_id)
    if org.plan != Plan.STANDARD:
        raise PermissionDeniedError("Environmental context requires the Standard plan")

    centroid = shapely_shape(site.polygon_geojson["features"][0]["geometry"]).centroid
    target_date = (date.today() - timedelta(days=6)).isoformat()

    params = {
        "latitude": centroid.y,
        "longitude": centroid.x,
        "start_date": target_date,
        "filter_type": 3,
        "granularity": 100,
    }
    try:
        result = await get_or_fetch_heatmap(
            lambda: get_satellite_segmentation_async(**params),
            is_historical=True,
            **params,
        )
    except (TaskTimeoutError, TaskFailedError, FortyGuardError) as exc:
        raise UpstreamDataError(f"Satellite context unavailable: {exc}") from exc
    segments, image = _normalize_satellite_context_payload(result)
    return {"site_id": site.id, "segments": segments, "satellite_image_base64": image}


@app.get("/sites/{site_id}/heatmap-tiles", response_model=HeatmapTilesResponse)
async def site_heatmap_tiles(
    site_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    site = await db.get(Site, site_id)
    if site is None or site.org_id != current_user.org_id:
        raise SiteNotFoundError("Site not found")

    # Use the shared lookback helper so this endpoint and run_compliance_check
    # always probe the same date range and can't drift independently.
    try:
        target_date, features = await find_latest_heatmap_date(
            site.polygon_geojson,
            filter_type=3,
            granularity=60,
            analytic_type="tcm",
        )
    except (TaskTimeoutError, TaskFailedError, FortyGuardError) as exc:
        raise UpstreamDataError(f"FortyGuard request failed: {exc}") from exc

    if not features:
        raise UpstreamDataError("No tile data available — run a check first")

    diag = _tile_diagnostics(features)

    return {
        "site_id": site.id,
        "metric_label": "Heat Index" if site.jurisdiction == Jurisdiction.OSHA_FEDERAL else "Temperature",
        "tiles": [
            {
                "geometry": feature["geometry"],
                "temp_f": feature["properties"]["max_temperature"] * 9 / 5 + 32,
            }
            for feature in features
        ],
        "diagnostics": diag,
    }
