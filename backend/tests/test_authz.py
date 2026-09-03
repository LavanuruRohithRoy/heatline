from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import create_access_token, hash_password
from app.models import Organization, Plan, Site, User, UserRole, Jurisdiction

POLYGON = {"type": "FeatureCollection", "features": []}


async def _org_with_users(session):
    org = Organization(name="Acme", plan=Plan.TRIAL)
    session.add(org)
    await session.flush()
    users = {}
    for role, email in (
        (UserRole.ADMIN, "admin@acme.example"),
        (UserRole.HSE_MANAGER, "hse@acme.example"),
        (UserRole.VIEWER, "viewer@acme.example"),
    ):
        user = User(
            org_id=org.id,
            email=email,
            password_hash=hash_password("secret"),
            role=role,
        )
        session.add(user)
        await session.flush()
        users[role] = user
    await session.commit()
    return org, users


def _auth(user: User) -> dict:
    token = create_access_token(user.id, user.org_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_viewer_blocked_from_creating_sites(client, async_session):
    org, users = await _org_with_users(async_session)
    response = await client.post(
        "/sites",
        json={"name": "Yard", "polygon_geojson": POLYGON, "jurisdiction": "osha_federal"},
        headers=_auth(users[UserRole.VIEWER]),
    )
    assert response.status_code == 403
    listed = await client.get("/sites", headers=_auth(users[UserRole.VIEWER]))
    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.asyncio
async def test_hse_manager_and_admin_can_create_sites(client, async_session):
    org, users = await _org_with_users(async_session)
    for role in (UserRole.HSE_MANAGER, UserRole.ADMIN):
        response = await client.post(
            "/sites",
            json={
                "name": f"{role.value} site",
                "polygon_geojson": POLYGON,
                "jurisdiction": "cal_osha",
            },
            headers=_auth(users[role]),
        )
        assert response.status_code == 200, response.text
        assert response.json()["org_id"] == str(org.id)


@pytest.mark.asyncio
async def test_viewer_blocked_from_running_checks(client, async_session):
    org, users = await _org_with_users(async_session)
    site = Site(org_id=org.id, name="Job", polygon_geojson=POLYGON, jurisdiction=Jurisdiction.OSHA_FEDERAL)
    async_session.add(site)
    await async_session.commit()

    with patch("app.main.run_compliance_check", new=AsyncMock()) as mocked:
        response = await client.post(
            f"/sites/{site.id}/check",
            headers=_auth(users[UserRole.VIEWER]),
        )
    assert response.status_code == 403
    mocked.assert_not_called()


@pytest.mark.asyncio
async def test_hse_manager_and_admin_can_run_checks(client, async_session):
    org, users = await _org_with_users(async_session)
    site = Site(org_id=org.id, name="Job", polygon_geojson=POLYGON, jurisdiction=Jurisdiction.OSHA_FEDERAL)
    async_session.add(site)
    await async_session.commit()

    fake = AsyncMock(return_value={"site_id": str(site.id), "threshold_breached": False})
    with patch("app.main.run_compliance_check", new=fake):
        for role in (UserRole.HSE_MANAGER, UserRole.ADMIN):
            response = await client.post(
                f"/sites/{site.id}/check",
                headers=_auth(users[role]),
            )
            assert response.status_code == 200, response.text
    assert fake.await_count == 2


@pytest.mark.asyncio
async def test_non_admin_cannot_create_members(client, async_session):
    _, users = await _org_with_users(async_session)
    for role in (UserRole.HSE_MANAGER, UserRole.VIEWER):
        response = await client.post(
            "/organizations/members",
            json={"email": f"new-{role.value}@acme.example", "password": "secret", "role": "viewer"},
            headers=_auth(users[role]),
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_hse_manager_and_viewer_members(client, async_session):
    org, users = await _org_with_users(async_session)
    for role in (UserRole.HSE_MANAGER, UserRole.VIEWER):
        email = f"{role.value}-hire@acme.example"
        response = await client.post(
            "/organizations/members",
            json={"email": email, "password": "secret", "role": role.value},
            headers=_auth(users[UserRole.ADMIN]),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["email"] == email
        assert body["role"] == role.value
        assert "access_token" not in body

    rejected = await client.post(
        "/organizations/members",
        json={"email": "boss@acme.example", "password": "secret", "role": "admin"},
        headers=_auth(users[UserRole.ADMIN]),
    )
    assert rejected.status_code == 422


@pytest.mark.asyncio
async def test_deleted_user_token_is_rejected_on_next_request(client, async_session):
    _, users = await _org_with_users(async_session)
    user = users[UserRole.ADMIN]
    headers = _auth(user)

    listed = await client.get("/sites", headers=headers)
    assert listed.status_code == 200

    await async_session.delete(user)
    await async_session.commit()

    after_delete = await client.get("/sites", headers=headers)
    assert after_delete.status_code == 401
    assert after_delete.json()["detail"] == "Invalid or expired token"
