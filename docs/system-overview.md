# System Overview — Heat Compliance Intelligence

## Problem statement

Outdoor-labor employers face active, dated regulatory exposure around heat:
a 2026 federal OSHA National Emphasis Program (NEP) heat-hazard enforcement
initiative in the US, binding state-level law in California (Cal/OSHA Title 8
§3395), and comparable threshold-based work-stoppage regulation in other
jurisdictions (e.g. UAE). Enforcement in the US operates at the site/employer
level — an HSE or operations manager responsible for a portfolio of job sites
needs to know, per site, whether current conditions place them in breach and
what action is mandated, not just "how hot is it."

No existing tool combines hyperlocal, site-specific heat data with real
jurisdictional thresholds at portfolio scale. Generic weather apps report
regional temperature, not site-level heat index tied to a specific legal
threshold and a specific mandated action.

## What this system does

Given a portfolio of registered job sites (each a GeoJSON polygon + a
jurisdiction), the system:

1. Pulls hyperlocal environmental data for each site via FortyGuard's
   Temperature Intelligence API
2. Derives the *legally relevant* metric (heat index, not raw temperature)
3. Compares that metric against the applicable jurisdiction's real,
   seeded regulatory thresholds
4. Records a timestamped, immutable compliance decision — the breach status
   and the specific mandated action, with citation
5. Exposes that decision (and its history) through an API and dashboard

## High-level architecture

```
                    ┌─────────────────────┐
                    │   Frontend (SPA)     │
                    │  site list, status,  │
                    │  check trigger       │
                    └──────────┬───────────┘
                               │ HTTPS
                    ┌──────────▼───────────┐
                    │   FastAPI backend     │
                    │  routes, auth,        │
                    │  rate limiting        │
                    └──┬────────────┬───────┘
                       │            │
            ┌──────────▼──┐   ┌─────▼──────────┐
            │  PostgreSQL  │   │     Redis       │
            │  (schema,    │   │  (cache, rate   │
            │  audit trail)│   │  limit state)   │
            └──────────────┘   └────────┬────────┘
                                         │ cache miss only
                                ┌────────▼─────────┐
                                │  FortyGuard API   │
                                │  (heatmap,        │
                                │   env_params,     │
                                │   heat_intel)      │
                                └───────────────────┘
```

The system is intentionally **centralized**, not distributed: one backend
process, one database, one cache, talking outward to external distributed
services it doesn't own (FortyGuard, the deploy platform). This is the
honest classification for the current scale — see
`06-scalability-and-engineering-tradeoffs.md` for why this is a deliberate
choice, not a limitation we ran out of time to fix.

## Core design principle

Every number the system reports must be traceable to: the raw FortyGuard
response that produced it, the exact regulatory rule it was compared
against, and the citation for that rule. This traceability is what makes
the output usable as an audit artifact, not just a live status light — see
`03-fortyguard-integration.md` and `04-decisions.md` for how this shaped
specific technical choices.