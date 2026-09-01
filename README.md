# Heatline — Heat Compliance Intelligence

**Built for FortyGuard Hackathon '26**

A portfolio-level heat-compliance decision-support system for outdoor-labor
employers. Employers register job sites as geographic polygons and select
the jurisdiction that governs them. The system pulls FortyGuard's hyperlocal
temperature intelligence for each site, compares it against the *specific
regulatory metric* that jurisdiction actually specifies (heat index for
federal OSHA, raw dry-bulb temperature for Cal/OSHA — these are not the same
number), and returns a compliance decision and the mandated action.

Repository note: `backend/app/integrations/fortyguard_client.py` is
FortyGuard's own vendored quickstart client, used unmodified as the
low-level HTTP/polling layer. Everything above that file — the data model,
compliance engine, jurisdiction logic, caching, auth, and the entire
frontend — was built during the hackathon.

## What it does

- Auth and organization-level tenant isolation
- Site registration with real GeoJSON polygons and jurisdiction selection
  (OSHA federal, Cal/OSHA, UAE)
- Jurisdiction-specific compliance logic — the engine branches per rule
  between heat index and raw temperature, not a single generic threshold
- FortyGuard temperature intelligence integration (`heatmap`/`tcm` for
  hyperlocal tile data, `env_params` for heat index)
- Historical compliance checks, persisted as an append-only audit record,
  with Redis caching to control credit spend
- Plan-based access control and rate limiting
- Satellite-derived land-cover context ("why is it hot here") for Standard
  organizations
- Production frontend and backend deployment

## Run locally, from scratch

### Prerequisites

- Docker and Docker Compose
- A FortyGuard API key

### Setup

1. Clone the repository.
2. Create `backend/.env` with at least:
   ```
   FORTYGUARD_API_KEY=your_api_key
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/heatline
   REDIS_URL=redis://redis:6379/0
   JWT_SECRET=any_random_string
   ALLOWED_ORIGINS=http://localhost:5173
   ```
3. Start everything:
   ```bash
   docker-compose up -d
   ```
4. Run database migrations:
   ```bash
   docker-compose exec backend alembic upgrade head
   ```
5. Seed the real regulatory threshold data and demo organization:
   ```bash
   docker-compose exec backend python -m app.seed
   docker-compose exec backend python -m app.seed_demo
   ```
6. Run the test suite:
   ```bash
   docker-compose exec backend pytest tests/ -v
   ```
7. Start the frontend:
   ```bash
   npm --prefix frontend install
   npm --prefix frontend run dev
   ```

The API is served at `http://localhost:8000`, the frontend at
`http://localhost:5173`.

## A real FortyGuard API request and response

This is a real call made during development, with the raw response shape as
FortyGuard actually returned it — not the shape its docstrings claimed.

**Request** (`heatmap`/`tcm`, the default analytic type, over a real job-site
scale polygon in Los Angeles):

```python
import asyncio
from app.integrations.fortyguard_service import create_heatmap_async

TEST_AOI = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-118.2500, 34.0500],
                [-118.2400, 34.0500],
                [-118.2400, 34.0600],
                [-118.2500, 34.0600],
                [-118.2500, 34.0500],
            ]],
        },
    }],
}

result = asyncio.run(create_heatmap_async(
    polygon_aoi=TEST_AOI,
    start_date="2026-08-20",
    filter_type=3,
    granularity=60,
))
```

**Response** (first tile's properties, taken directly from our logs):

```json
{
  "activity_id": "f780d5d7-e867-4d13-823d-667b0d434166",
  "status": "completed",
  "result": {
    "map_data": {
      "features": [
        {
          "properties": {
            "tile_id": 0,
            "average_temperature": 28.0308,
            "min_temperature": 21.8976,
            "max_temperature": 37.804
          }
        }
      ]
    }
  }
}
```

Two real findings from this call that shaped the codebase: `tcm` returns
temperature in **Celsius**, and results are per-tile min/avg/max rather than
a single flat value — both contradict the vendored client's own docstring.
Details and the full FortyGuard integration writeup are in
[FortyGuard Integration](docs/fortyguard-integration.md).

## Known limitations

- **Forecast compliance checks are not implemented.** FortyGuard's `heatmap`
  endpoint supports genuine forward-looking queries, but every live test we
  ran against a current/near-future window returned zero features during
  development — a real, observed FortyGuard data-latency issue, not a bug
  on our side. The system currently evaluates the most recent confirmed
  conditions (a fixed lookback window), not a live or predictive feed.
- **UAE jurisdiction is modeled but not live-checkable.** The regulatory
  rule is real and seeded, but FortyGuard's current release only covers US
  locations — a documented upstream constraint, not a gap in our design.
- **Environmental/satellite context depends on FortyGuard's own data
  coverage** for the requested location and date, and can occasionally be
  unavailable or slow.
- **The upgrade flow is simulated** — no real billing integration exists.
  Trial and Standard plans currently differ mainly in site-count and
  rate-limit numbers; Standard additionally unlocks the satellite context
  feature.
- **No full decision-provenance trail yet** — a compliance check stores its
  result, not the raw upstream response or matched rule ID. Scoped as a
  near-term improvement, not built in this pass.
- FortyGuard API credentials remain server-side only and are never
  committed or exposed to the frontend.

Full, honest detail on all of the above is in
[Known Limitations and Roadmap](docs/known-limitations-and-roadmap.md).

## Documentation

- [System Overview](docs/system-overview.md) — the problem, what the
  system does, architecture diagram
- [Data Model](docs/data-model.md) — every table, every field, and why
- [FortyGuard Integration](docs/fortyguard-integration.md) — all four
  `heatmap` analytic types with real measured numbers, the
  `heatmap → env_params` chain, credit economics, the US-only constraint
- [Architecture Decisions](docs/decisions.md) — every major decision,
  why it was made, and what was given up
- [Security and Multi-Tenancy](docs/security-and-multitenancy.md)
- [Scalability and Engineering Tradeoffs](docs/scalability-and-engineering-tradeoffs.md)
- [Known Limitations and Roadmap](docs/known-limitations-and-roadmap.md)
- [Research and Product Case](research_and_product_case.md) — the original
  domain research behind why this product exists
  
