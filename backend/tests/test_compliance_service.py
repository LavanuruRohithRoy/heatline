import pytest
import uuid
from unittest.mock import AsyncMock, patch
from app.services.compliance_service import run_compliance_check
from app.models import Site, Jurisdiction, ThresholdRule, MetricType

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
# max_tile_temp_c = 38.09 -> 100.56°F

MOCK_ENV_PARAMS_RESPONSE = {
    "result": {
        "locations": [
            {
                "lat": 34.055,
                "lon": -118.235,
                "parameters": {"heat_index_celsius": [95.5]},  # already-°F, per confirmed real API behavior
            }
        ]
    }
}


@pytest.mark.asyncio
async def test_osha_federal_uses_heat_index_and_calls_env_params(async_session):
    """OSHA federal is heat-index-based -> env_params must be called."""
    site = Site(
        org_id=uuid.uuid4(), name="OSHA Site",
        polygon_geojson={"type": "FeatureCollection", "features": []},
        jurisdiction=Jurisdiction.OSHA_FEDERAL,
    )
    async_session.add(site)
    await async_session.flush()

    async_session.add_all([
        ThresholdRule(jurisdiction="osha_federal", metric_type=MetricType.HEAT_INDEX, heat_index_threshold_f=80.0, mandated_action="provide_water_shade_rest_breaks", citation="test"),
        ThresholdRule(jurisdiction="osha_federal", metric_type=MetricType.HEAT_INDEX, heat_index_threshold_f=90.0, mandated_action="mandatory_rest_breaks", citation="test"),
    ])
    await async_session.flush()

    with patch(
        "app.services.compliance_service.create_heatmap_async",
        new=AsyncMock(return_value=MOCK_HEATMAP_RESPONSE),
    ), patch(
        "app.services.compliance_service.get_env_params_async",
        new=AsyncMock(return_value=MOCK_ENV_PARAMS_RESPONSE),
    ) as mock_env:
        check = await run_compliance_check(async_session, site)

    mock_env.assert_called_once()  # heat-index jurisdiction must call env_params
    assert check.heat_index_value == pytest.approx(95.5, abs=0.1)
    assert check.threshold_breached is True
    assert check.action_triggered == "mandatory_rest_breaks"


@pytest.mark.asyncio
async def test_cal_osha_uses_dry_bulb_and_skips_env_params(async_session):
    """Cal/OSHA is dry-bulb-temperature-based -> env_params must NOT be called."""
    site = Site(
        org_id=uuid.uuid4(), name="Cal/OSHA Site",
        polygon_geojson={"type": "FeatureCollection", "features": []},
        jurisdiction=Jurisdiction.CAL_OSHA,
    )
    async_session.add(site)
    await async_session.flush()

    async_session.add_all([
        ThresholdRule(jurisdiction="cal_osha", metric_type=MetricType.DRY_BULB_TEMPERATURE, heat_index_threshold_f=80.0, mandated_action="provide_shade_water_access", citation="test"),
        ThresholdRule(jurisdiction="cal_osha", metric_type=MetricType.DRY_BULB_TEMPERATURE, heat_index_threshold_f=95.0, mandated_action="high_heat_procedures_mandatory_buddy_system", citation="test"),
    ])
    await async_session.flush()

    with patch(
        "app.services.compliance_service.create_heatmap_async",
        new=AsyncMock(return_value=MOCK_HEATMAP_RESPONSE),
    ), patch(
        "app.services.compliance_service.get_env_params_async",
        new=AsyncMock(),
    ) as mock_env:
        check = await run_compliance_check(async_session, site)

    mock_env.assert_not_called()  # dry-bulb jurisdiction must skip env_params entirely
    # max_tile_temp_c 38.09 -> 100.56°F, exceeds both 80°F and 95°F -> highest (95°F) wins
    assert check.heat_index_value == pytest.approx(100.56, abs=0.1)
    assert check.threshold_breached is True
    assert check.action_triggered == "high_heat_procedures_mandatory_buddy_system"