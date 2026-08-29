# Hyperlocal Heat Intelligence for Workforce Compliance
### A Product Case for FortyGuard's Temperature Intelligence Platform

## 1. The Problem

Outdoor-labor employers — in construction, logistics, and agriculture — are
subject to an active, escalating regulatory environment around occupational
heat exposure, with real financial and human stakes.

In the United States, OSHA has proposed a federal Heat Injury and Illness
Prevention rule; that rule remains under rulemaking and is **not yet a
finalized binding standard**. In advance of any final rule, OSHA is
actively enforcing exposure risk through a National Emphasis Program (NEP),
revised April 2026, which targets high-risk industries with heat-priority
inspections and outreach. California enforces its own binding standard
(Title 8 §3395), triggered by ambient dry-bulb temperature — 80°F for shade
and water provisions, 95°F for high-heat procedures — not heat index.
Oregon's standard, by contrast, is heat-index-based. Internationally, the
United Arab Emirates has enforced a threshold-triggered midday outdoor-work
restriction since 2005.

The human and financial cost is real: 48 US worker deaths from
environmental heat exposure were recorded in 2024. Under the current OSHA
penalty schedule, a Serious violation carries a maximum penalty in the
range of $16,000+, and a Willful or Repeat violation substantially more.

## 2. Existing Systems and Their Limitations

**Public reference tools**, such as the OSHA-NIOSH Heat Safety Tool,
provide real-time, location-based heat index readings and general safety
guidance, built on regional weather-service data at single-location,
single-user scale — not designed for multi-site portfolio management.

**Enterprise construction and field-safety platforms** (e.g. Procore, HCSS,
HammerTech) provide mature, multi-site safety management, but generally
treat weather data as a passive, reactive record for project documentation
rather than a forward-looking, jurisdiction-aware compliance input.

No identified existing product combines hyperlocal, site-specific heat data
with active, jurisdiction-specific regulatory thresholds — including the
fact that different jurisdictions specify different metrics (heat index vs.
raw temperature) — at a multi-site portfolio level.

## 3. Why Hyperlocal Data and Jurisdiction-Specific Metrics Matter

Standard regional weather forecasting cannot meaningfully differentiate
between job sites within the same metropolitan area, and cannot by itself
resolve which regulatory metric applies where. Two sites at the same
regional forecast temperature can have different real heat index values
depending on local humidity, and a system evaluating both against the same
metric — when their governing regulations specify different ones — would
produce an incorrect compliance determination for at least one of them.
This is not a hypothetical: it was found and corrected during this
project's own development (see `docs/04-decisions.md`, ADR-008).

## 4. System, As Currently Built

A portfolio-level heat-compliance decision-support system:

1. An employer registers job sites as GeoJSON polygons, each tagged with
   its governing jurisdiction.
2. On request, the system evaluates a site's most recent available
   conditions against the jurisdiction's real, seeded regulatory
   threshold, using the metric that jurisdiction's own regulation
   specifies.
3. A rule table, referencing real regulatory thresholds and citations,
   produces a specific compliance status and, if breached, the specific
   mandated action.
4. A dashboard presents this per site, along with satellite-derived
   land-cover context explaining likely contributing factors (e.g.
   unshaded pavement).

**What is not yet built, stated plainly:** shift-schedule-aware evaluation,
duration/persistence-based exposure analysis (as opposed to a
worst-tile snapshot), scheduled/automatic monitoring, and full audit
provenance (rule version and source data retained per decision). See
`docs/07-known-limitations-and-roadmap.md` for the complete list.

The system is explicitly scoped as decision support. It does not determine
employment or scheduling decisions and does not substitute for an
employer's own legal compliance obligations or professional judgment.

## 5. Commercial Rationale

The buying entity is the employer organization, not the individual
worker — consistent with the existing enterprise field-safety software
market. The product is structurally recurring: heat-season compliance
monitoring is an annually repeating operational need, and usage scales
with site count and season length.

## 6. Scope of Evolution

The core mechanism — jurisdiction-aware, metric-correct threshold
evaluation from hyperlocal data — generalizes to any jurisdiction with a
comparable standard, including the UAE's midday work restriction, pending
FortyGuard's data coverage expanding beyond its current US-only scope.

## 7. Summary

This system applies hyperlocal temperature intelligence to a specific,
underserved gap: the space between free, single-location public tools and
enterprise platforms that treat weather as a passive record — while taking
seriously that "compliance" requires matching each jurisdiction's actual
specified metric, not a single generic heat number applied everywhere.