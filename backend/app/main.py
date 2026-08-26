import uuid
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.db import get_db
from app.models import Site, Jurisdiction, ComplianceCheck
from app.services.compliance_service import run_compliance_check

app = FastAPI(title="Heatline API", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


class SiteCreate(BaseModel):
    org_id: uuid.UUID
    name: str
    polygon_geojson: dict
    jurisdiction: Jurisdiction


@app.post("/sites")
async def create_site(payload: SiteCreate, db: AsyncSession = Depends(get_db)):
    site = Site(**payload.model_dump())
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site


@app.post("/sites/{site_id}/check")
async def check_site(site_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    site = await db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    check = await run_compliance_check(db, site)
    return check