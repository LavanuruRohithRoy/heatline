# Heat Compliance Intelligence — FortyGuard Hackathon'26

A portfolio-level heat-compliance decision-support system for outdoor-labor
employers, built on FortyGuard's hyperlocal temperature intelligence API.

## Problem

Employers operating outdoor job sites face active, dated regulatory
exposure around heat — an OSHA enforcement directive in the US, binding
state law in California, and comparable threshold-based regulation
elsewhere. No existing tool combines hyperlocal, site-specific heat data
with real jurisdictional compliance thresholds at a portfolio scale. See
`research_and_product_case.md` for the full problem statement and
supporting research.

## What this is

A system that ingests job-site polygons and jurisdictions, evaluates each
site against the metric its specific regulation actually specifies
(heat index or raw temperature, depending on jurisdiction), and returns a
compliance status and recommended action.

## Status

Backend is functional and tested end-to-end: authentication, tenant
isolation, per-jurisdiction compliance logic, caching, rate limiting, and
a satellite-derived environmental context endpoint are built and verified.
Frontend and deployment are in progress — see `docs/known-limitations-and-roadmap.md`
for a complete, honest list of what's built versus what remains.

**Two confirmed vendor-data findings worth knowing before reading the
code:** FortyGuard's `tcm` heatmap field returns Celsius despite the
vendored client's docstring claiming Fahrenheit, and `env_params`'
`heat_index_celsius` field returns values already in Fahrenheit despite
its name — both confirmed by inspecting real responses, not by trusting
documentation. See `docs/fortyguard-integration.md`.

## Repository structure

    docs/                 architecture, data model, decisions, limitations
    research_and_product_case.md   problem statement and market research
    backend/              FastAPI application
    frontend/              React dashboard
    .github/workflows/     CI and uptime automation

## Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Database: PostgreSQL (Supabase in production)
- Cache / rate limiting: Redis (Upstash in production)
- Frontend: React (Vercel in production)
- API hosting: Render
- Data source: FortyGuard Temperature Intelligence API

## Local setup

    docker-compose up -d
    docker-compose exec backend alembic upgrade head
    docker-compose exec backend python -m app.seed
    docker-compose exec backend python -m app.seed_demo

## Tests

    docker-compose exec backend pytest tests/ -v

## Documentation

See `docs/` for full architecture, data model, FortyGuard integration
details (including real measured credit costs), decision records, security
model, scalability tradeoffs, and a complete known-limitations list.