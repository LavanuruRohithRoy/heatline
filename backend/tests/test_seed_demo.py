"""Tests for seed_demo.py's idempotent compliance-check seeding step.

We exercise _seed_demo_compliance_checks() directly (with a test DB session
and a patched run_compliance_check) rather than calling seed_demo() itself,
which requires a real engine with asyncpg connect-args.
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models import (
    ComplianceCheck,
    Jurisdiction,
    Organization,
    Plan,
    Site,
    ThresholdRule,
    MetricType,
)
from app.seed_demo import _IDEMPOTENCY_WINDOW_HOURS, _seed_demo_compliance_checks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_site(org_id: uuid.UUID, jurisdiction: Jurisdiction = Jurisdiction.OSHA_FEDERAL) -> Site:
    return Site(
        org_id=org_id,
        name=f"Demo Site {jurisdiction.value}",
        polygon_geojson={"type": "FeatureCollection", "features": []},
        jurisdiction=jurisdiction,
    )


def _make_recent_check(site_id: uuid.UUID, hours_ago: float = 1.0) -> ComplianceCheck:
    """Return a ComplianceCheck whose checked_at is *inside* the idempotency window."""
    return ComplianceCheck(
        site_id=site_id,
        checked_at=datetime.utcnow() - timedelta(hours=hours_ago),
        heat_index_value=88.0,
        threshold_breached=True,
        action_triggered="mandatory_rest_breaks",
        metric_label="Heat Index",
        data_as_of=(datetime.utcnow() - timedelta(days=6)).date().isoformat(),
        threshold_value=90.0,
    )


def _make_stale_check(site_id: uuid.UUID) -> ComplianceCheck:
    """Return a ComplianceCheck whose checked_at is *outside* the idempotency window."""
    return ComplianceCheck(
        site_id=site_id,
        checked_at=datetime.utcnow() - timedelta(hours=_IDEMPOTENCY_WINDOW_HOURS + 2),
        heat_index_value=82.0,
        threshold_breached=False,
        action_triggered=None,
        metric_label="Heat Index",
        data_as_of=(datetime.utcnow() - timedelta(days=6)).date().isoformat(),
        threshold_value=90.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compliance_check_skipped_when_recent_check_exists(async_session):
    """_seed_demo_compliance_checks must NOT call run_compliance_check when
    a check already exists within the idempotency window for a site."""
    org = Organization(name="Demo Org", plan=Plan.STANDARD, is_public_demo=True)
    async_session.add(org)
    await async_session.flush()

    site = _make_site(org.id)
    async_session.add(site)
    await async_session.flush()

    # Insert a fresh check — within the 24 h window.
    async_session.add(_make_recent_check(site.id))
    await async_session.flush()

    with patch("app.seed_demo.run_compliance_check", new=AsyncMock()) as mock_check:
        await _seed_demo_compliance_checks(async_session, [site])
        mock_check.assert_not_called()


@pytest.mark.asyncio
async def test_compliance_check_runs_when_no_recent_check_exists(async_session):
    """_seed_demo_compliance_checks MUST call run_compliance_check when no
    recent check exists for a site."""
    org = Organization(name="Demo Org", plan=Plan.STANDARD, is_public_demo=True)
    async_session.add(org)
    await async_session.flush()

    site = _make_site(org.id)
    async_session.add(site)
    await async_session.flush()

    # No ComplianceCheck in DB at all.
    fake_check = ComplianceCheck(
        site_id=site.id,
        checked_at=datetime.utcnow(),
        heat_index_value=95.5,
        threshold_breached=True,
        action_triggered="mandatory_rest_breaks",
        metric_label="Heat Index",
        data_as_of=(datetime.utcnow() - timedelta(days=6)).date().isoformat(),
        threshold_value=90.0,
    )
    with patch(
        "app.seed_demo.run_compliance_check", new=AsyncMock(return_value=fake_check)
    ) as mock_check:
        await _seed_demo_compliance_checks(async_session, [site])
        mock_check.assert_called_once()


@pytest.mark.asyncio
async def test_compliance_check_runs_when_only_stale_check_exists(async_session):
    """A check that is older than _IDEMPOTENCY_WINDOW_HOURS must NOT satisfy
    the idempotency guard — the helper should still call run_compliance_check."""
    org = Organization(name="Demo Org", plan=Plan.STANDARD, is_public_demo=True)
    async_session.add(org)
    await async_session.flush()

    site = _make_site(org.id)
    async_session.add(site)
    await async_session.flush()

    # Stale check: outside the 24 h window.
    async_session.add(_make_stale_check(site.id))
    await async_session.flush()

    fake_check = ComplianceCheck(
        site_id=site.id,
        checked_at=datetime.utcnow(),
        heat_index_value=80.0,
        threshold_breached=False,
        action_triggered=None,
        metric_label="Heat Index",
        data_as_of=(datetime.utcnow() - timedelta(days=6)).date().isoformat(),
        threshold_value=90.0,
    )
    with patch(
        "app.seed_demo.run_compliance_check", new=AsyncMock(return_value=fake_check)
    ) as mock_check:
        await _seed_demo_compliance_checks(async_session, [site])
        mock_check.assert_called_once()


@pytest.mark.asyncio
async def test_compliance_check_failure_is_non_fatal(async_session):
    """A FortyGuard / upstream error must not abort the seeding step — it
    should be swallowed so that a partial outage doesn't break deploys."""
    org = Organization(name="Demo Org", plan=Plan.STANDARD, is_public_demo=True)
    async_session.add(org)
    await async_session.flush()

    site = _make_site(org.id)
    async_session.add(site)
    await async_session.flush()

    with patch(
        "app.seed_demo.run_compliance_check",
        new=AsyncMock(side_effect=RuntimeError("FortyGuard unavailable")),
    ):
        # Must not raise.
        await _seed_demo_compliance_checks(async_session, [site])


@pytest.mark.asyncio
async def test_each_site_checked_independently(async_session):
    """With two demo sites where one has a fresh check and the other doesn't,
    run_compliance_check is called exactly once (for the stale site only)."""
    org = Organization(name="Demo Org", plan=Plan.STANDARD, is_public_demo=True)
    async_session.add(org)
    await async_session.flush()

    site_fresh = _make_site(org.id, Jurisdiction.OSHA_FEDERAL)
    site_stale = _make_site(org.id, Jurisdiction.CAL_OSHA)
    async_session.add_all([site_fresh, site_stale])
    await async_session.flush()

    # Fresh check for site_fresh only.
    async_session.add(_make_recent_check(site_fresh.id))
    await async_session.flush()

    fake_check = ComplianceCheck(
        site_id=site_stale.id,
        checked_at=datetime.utcnow(),
        heat_index_value=100.0,
        threshold_breached=True,
        action_triggered="high_heat_procedures_mandatory_buddy_system",
        metric_label="Temperature",
        data_as_of=(datetime.utcnow() - timedelta(days=6)).date().isoformat(),
        threshold_value=95.0,
    )
    with patch(
        "app.seed_demo.run_compliance_check", new=AsyncMock(return_value=fake_check)
    ) as mock_check:
        await _seed_demo_compliance_checks(async_session, [site_fresh, site_stale])
        # Called exactly once — only for the site without a fresh check.
        mock_check.assert_called_once()
        call_args = mock_check.call_args
        assert call_args[0][1].id == site_stale.id  # positional arg: session, site
