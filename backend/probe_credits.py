"""
Run once, deliberately — measures real per-call credit cost.
"""
import asyncio
from app.integrations.fortyguard_service import create_heatmap_async, get_usage_async

# Small (~1 km²) polygon, same shape/pattern as their own Manhattan sample —
# a real job-site scale AOI, not a citywide one.
TEST_AOI = {
    "type": "FeatureCollection",
    "features": [
        {
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
        }
    ],
}

async def main() -> None:
    before = await get_usage_async()
    print("Usage before:", before)

    result = await create_heatmap_async(
        polygon_aoi=TEST_AOI,
        start_date="2026-08-20",
        filter_type=3,          # single_day, per samples.py's FILTER_TYPES
        granularity=60,
        analytic_type="exceedance",
        threshold=26.7,         # 80°F in Celsius — the OSHA NEP trigger
        direction="above",
    )
    print("Heatmap result activity_id:", result.get("activity_id"))

    after = await get_usage_async()
    print("Usage after:", after)

if __name__ == "__main__":
    asyncio.run(main())