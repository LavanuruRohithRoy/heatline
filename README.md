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

This commit establishes the project structure and research foundation.
Application logic begins in the following commit.

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

Setup instructions will be added alongside the first functional commit.