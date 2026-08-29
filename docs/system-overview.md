# System Overview — Heat Compliance Intelligence

## Problem statement

Outdoor-labor employers face active, dated regulatory exposure around heat:
an OSHA National Emphasis Program (NEP) heat-hazard enforcement directive in
the US (revised April 2026 — an active enforcement program, not yet a
finalized binding federal standard), binding state-level law in California
(Cal/OSHA Title 8 §3395), and comparable threshold-based regulation in other
jurisdictions (e.g. UAE). Enforcement in the US operates at the site/employer
level — an HSE or operations manager responsible for a portfolio of job
sites needs to know, per site, whether recent conditions place them in
breach and what action is mandated, not just "how hot is it."

No existing tool combines hyperlocal, site-specific heat data with real
jurisdictional thresholds at portfolio scale. Generic weather apps report
regional temperature, not a site-level metric tied to a specific legal
threshold and a specific mandated action.

## What this system does

Given a portfolio of registered job sites (each a GeoJSON polygon + a
jurisdiction), the system:

1. Pulls hyperlocal environmental data for each site via FortyGuard's
   Temperature Intelligence API
2. Derives the **metric each jurisdiction's regulation actually specifies**
   — heat index for OSHA federal, raw dry-bulb temperature for Cal/OSHA —
   not one metric applied uniformly
3. Compares that metric against the applicable jurisdiction's real,
   seeded regulatory thresholds
4. Records a timestamped compliance decision — the breach status and the
   specific mandated action — for historical checks
5. Exposes that decision, a satellite-derived land-cover context layer, and
   site history through an authenticated API and dashboard

## High-level architecture

```
                    ┌─────────────────────┐
                    │  Frontend (React,    │
                    │  Vercel)              │
                    └──────────┬───────────┘
                               │ HTTPS
                    ┌──────────▼───────────┐
                    │  FastAPI backend      │
                    │  (Render)             │
                    │  routes, auth, CORS,  │
                    │  rate limiting        │
                    └──┬────────────┬───────┘
                       │            │
            ┌──────────▼──┐   ┌─────▼──────────┐
            │  PostgreSQL  │   │     Redis       │
            │  (Supabase)  │   │  (Upstash)      │
            └──────────────┘   └────────┬────────┘
                                         │ cache miss only
                                ┌────────▼─────────┐
                                │  FortyGuard API   │
                                │  (heatmap,        │
                                │   env_params,     │
                                │   satellite)       │
                                └───────────────────┘
```

The system is intentionally **centralized**, not distributed: one backend
process, one database, one cache, talking outward to external distributed
services it doesn't own (FortyGuard, the deploy platforms). This is the
honest classification for the current scale — see
`06-scalability-and-engineering-tradeoffs.md`.

## Core design principle

Every number the system reports is traceable to a real FortyGuard response
and the specific regulatory threshold it was compared against. What is
**not yet true**: the system does not currently retain the raw source
response, vendor activity ID, or rule version alongside each stored
decision — this is a real, acknowledged gap, not a solved property. See
`known-limitations-and-roadmap.md`.