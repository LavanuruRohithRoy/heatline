from datetime import datetime, timedelta, timezone

import pytest

from app.models import ComplianceCheck, Jurisdiction, Organization, Plan, Site

POLYGON = {"type": "FeatureCollection", "features": []}


@pytest.mark.asyncio
async def test_public_sites_include_latest_persisted_check_or_null(client, async_session):
    org = Organization(name="Public Demo", plan=Plan.STANDARD, is_public_demo=True)
    async_session.add(org)
    await async_session.flush()

    checked = Site(
        org_id=org.id,
        name="Checked Yard",
        polygon_geojson=POLYGON,
        jurisdiction=Jurisdiction.OSHA_FEDERAL,
    )
    unchecked = Site(
        org_id=org.id,
        name="Unchecked Yard",
        polygon_geojson=POLYGON,
        jurisdiction=Jurisdiction.CAL_OSHA,
    )
    async_session.add_all([checked, unchecked])
    await async_session.flush()

    older = ComplianceCheck(
        site_id=checked.id,
        checked_at=datetime.now(timezone.utc) - timedelta(days=2),
        heat_index_value=81.0,
        threshold_breached=True,
        action_triggered="provide_water_shade_rest_breaks",
        metric_label="Heat Index",
        data_as_of="2026-08-20",
        threshold_value=80.0,
    )
    latest = ComplianceCheck(
        site_id=checked.id,
        checked_at=datetime.now(timezone.utc),
        heat_index_value=92.5,
        threshold_breached=True,
        action_triggered="mandatory_rest_breaks",
        metric_label="Heat Index",
        data_as_of="2026-08-22",
        threshold_value=90.0,
    )
    async_session.add_all([older, latest])
    await async_session.commit()

    response = await client.get("/public/sites")
    assert response.status_code == 200
    body = {row["name"]: row for row in response.json()}

    assert body["Unchecked Yard"]["latest_result"] is None
    result = body["Checked Yard"]["latest_result"]
    assert result is not None
    assert result["heat_index_value"] == pytest.approx(92.5)
    assert result["action_triggered"] == "mandatory_rest_breaks"
    assert result["id"] == str(latest.id)
