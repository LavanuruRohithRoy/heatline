# Heat Compliance Intelligence — FortyGuard Hackathon'26

A portfolio-level heat-compliance decision-support system for outdoor-labor employers, built with FortyGuard's hyperlocal temperature intelligence API.

## What it does

Employers add job sites as geographic polygons and select their jurisdiction. The system evaluates each site against the applicable heat-compliance threshold and returns the compliance status, triggering condition, and mandated action.

The current application includes:

- Authentication and organization-level tenant isolation
- Site creation and portfolio dashboard
- Jurisdiction-specific compliance rules
- FortyGuard temperature intelligence integration
- Historical compliance checks with Redis caching
- Plan-based access control and rate limiting
- Satellite-derived environmental context for Standard organizations
- Production frontend and backend deployment

Forecast checks are the remaining major application feature.

## Run locally

### Prerequisites

- Docker and Docker Compose

- A FortyGuard API key

- Create the environment configuration with the required backend values, including:

- FORTYGUARD_API_KEY=your_api_key

Then:

- docker-compose up -d
- docker-compose exec backend alembic upgrade head
- docker-compose exec backend python -m app.seed
- docker-compose exec backend python -m app.seed_demo

### Run the test suite:

- docker-compose exec backend pytest tests/ -v

The frontend and API can then be run through the project's configured local development setup.

## Known limitations

Forecast compliance checks are not yet implemented.

Environmental context depends on FortyGuard satellite-data availability for the requested location/date.

The upgrade flow is a simulated plan upgrade; no real billing integration exists.

FortyGuard API credentials remain server-side and must never be committed or exposed to the frontend.

Detailed limitations, architecture, security decisions, and integration notes are documented under 'docs/'.


## Documentation

Detailed architecture, research, data model, FortyGuard integration findings, security model, scalability decisions, and known limitations are available in 'docs/'.