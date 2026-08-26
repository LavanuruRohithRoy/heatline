import pytest
import uuid
from unittest.mock import AsyncMock, patch
from datetime import date

from app.services.compliance_service import run_compliance_check
from app.models import Site, Jurisdiction, ThresholdRule

# Real captured response shape from the live debugging session — Celsius tiles.
MOCK_HEATMAP_RESPONSE = {
    "result": {
        "map_data": {
            "features": [
                {"properties": {"tile_id": 0, "average_temperature": 28.03, "min_temperature": 21.90, "max_temperature": 37.80}},
                {"properties": {"tile_id": 1, "average_temperature": 30.10, "min_temperature": 22.50, "max_temperature": 38.09}},
            ]
        }
    }
}


@pytest.mark.asyncio
async def test_compliance_check_converts_celsius_and_compares_correctly(async_session):
    site = Site(
        org_id=uuid.uuid4(),
        name="Test Site",
        polygon_geojson={"type": "FeatureCollection", "features": []},
        jurisdiction=Jurisdiction.OSHA_FEDERAL,
    )
    async_session.add(site)
    await async_session.flush()

    async_session.add_all([
        ThresholdRule(jurisdiction="osha_federal", heat_index_threshold_f=80.0, mandated_action="provide_water_shade_rest_breaks", citation="test"),
        ThresholdRule(jurisdiction="osha_federal", heat_index_threshold_f=90.0, mandated_action="mandatory_rest_breaks", citation="test"),
    ])
    await async_session.flush()

    with patch(
        "app.services.compliance_service.create_heatmap_async",
        new=AsyncMock(return_value=MOCK_HEATMAP_RESPONSE),
    ):
        check = await run_compliance_check(async_session, site)

    # 38.09°C -> 100.56°F, which exceeds BOTH the 80°F and 90°F rules.
    # Highest-threshold-breached wins (most severe applicable action) -> 90°F rule fires.
    assert check.heat_index_value == pytest.approx(100.56, abs=0.1)
    assert check.threshold_breached is True
    assert check.action_triggered == "mandatory_rest_breaks"