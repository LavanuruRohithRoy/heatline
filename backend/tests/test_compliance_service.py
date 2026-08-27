import pytest
import uuid
from unittest.mock import AsyncMock, patch
from app.services.compliance_service import run_compliance_check
from app.models import Site, Jurisdiction, ThresholdRule

MOCK_HEATMAP_RESPONSE = {
    "result": {
        "map_data": {
            "features": [
                {
                    "properties": {"tile_id": 0, "average_temperature": 28.03, "min_temperature": 21.90, "max_temperature": 37.80},
                    "geometry": {"type": "Polygon", "coordinates": [[[-118.25, 34.05], [-118.24, 34.05], [-118.24, 34.06], [-118.25, 34.06], [-118.25, 34.05]]]},
                },
                {
                    "properties": {"tile_id": 1, "average_temperature": 30.10, "min_temperature": 22.50, "max_temperature": 38.09},
                    "geometry": {"type": "Polygon", "coordinates": [[[-118.24, 34.05], [-118.23, 34.05], [-118.23, 34.06], [-118.24, 34.06], [-118.24, 34.05]]]},
                },
            ]
        }
    }
}

MOCK_ENV_PARAMS_RESPONSE = {
    "result": {
        "locations": [
            {
                "lat": 34.055,
                "lon": -118.235,
                "parameters": {
                    # Field is named "heat_index_celsius" by FortyGuard, but empirically
                    # returns values already in °F (confirmed via live response — see
                    # docs/03-fortyguard-integration.md). 95.5 here represents that
                    # already-°F value, chosen to exercise the breach-detection path.
                    "heat_index_celsius": [95.5],
                },
            }
        ]
    }
}


@pytest.mark.asyncio
async def test_compliance_check_uses_heat_index_and_compares_correctly(async_session):
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
    ), patch(
        "app.services.compliance_service.get_env_params_async",
        new=AsyncMock(return_value=MOCK_ENV_PARAMS_RESPONSE),
    ):
        check = await run_compliance_check(async_session, site)

    # 95.5 (already °F, no conversion applied) exceeds both rules -> highest (90°F) wins
    assert check.heat_index_value == pytest.approx(95.5, abs=0.1)
    assert check.threshold_breached is True
    assert check.action_triggered == "mandatory_rest_breaks"