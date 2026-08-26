# Heat Compliance Intelligence — FortyGuard Hackathon'26

A portfolio-level heat-compliance decision-support system for outdoor-labor
employers, built on FortyGuard's hyperlocal temperature intelligence API.

## Problem

Employers operating outdoor job sites face active, dated regulatory exposure
around heat — a 2026 federal enforcement program in the US, binding state law
in California, Oregon, and Washington, and an equivalent threshold-based
regulation in the UAE. No existing tool combines hyperlocal, site-specific
heat-duration data with real jurisdictional compliance thresholds at a
portfolio scale. See `docs/research_and_product_case.md` for the full
problem statement, competitive landscape, and supporting research.

## What this is

A system that ingests job-site locations and shift windows, evaluates
site-specific heat exposure duration against applicable jurisdictional
thresholds using FortyGuard's temperature intelligence API, and returns a
compliance status and recommended action per site.

## Status

Data model, FortyGuard integration, and the core compliance-check engine are
built and tested end-to-end:

- SQLAlchemy models (Organization, User, Site, ShiftWindow, ComplianceCheck)
  and a seeded `ThresholdRule` table with real OSHA NEP, Cal/OSHA, and UAE
  values, migrated via Alembic
- Vendored FortyGuard client with an async service wrapper, confirmed working
  against the real API
- `POST /sites` and `POST /sites/{id}/check` — the latter pulls live `tcm`
  heatmap data for a site's polygon, compares against jurisdiction
  thresholds, and records a `ComplianceCheck`
- Core compliance logic (unit conversion, threshold selection) covered by
  tests using mocked FortyGuard responses — no live API calls needed to run
  the test suite

**Known constraint:** FortyGuard's `tcm` heatmap endpoint returns tile
temperatures in Celsius, despite the vendor client's own docstring stating
°F — confirmed by inspecting a real response, not from documentation. All
temperature handling in this repo converts explicitly; don't trust vendor
docstrings for units without re-verifying against a live response.

**Not yet built:** Redis caching/rate-limiting layer, frontend, deployment.

## Repository structure

    docs/           research and product documentation
    backend/         FastAPI application (API, rule engine, FortyGuard
                      integration, data layer)
    frontend/         dashboard application
    .github/workflows/ CI and uptime automation

## Stack

- Backend: Python, FastAPI
- Database: PostgreSQL
- Cache / rate control: Redis
- Data source: FortyGuard Temperature Intelligence API

## Setup

    docker-compose up -d
    docker-compose exec backend alembic upgrade head
    docker-compose exec backend python -m app.seed

## Tests

    docker-compose exec backend pytest tests/ -v