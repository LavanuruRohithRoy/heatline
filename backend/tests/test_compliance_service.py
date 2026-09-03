import pytest
import uuid
from unittest.mock import AsyncMock, patch
from app.main import _normalize_satellite_context_payload, site_heatmap_tiles
from app.services.compliance_service import run_compliance_check
from app.models import Site, Jurisdiction, ThresholdRule, MetricType
from app.core.security import CurrentUser
from app.core.exceptions import UpstreamDataError, UnsupportedJurisdictionError
from app.integrations.exceptions import TaskTimeoutError

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
                "parameters": {"heat_index_celsius": [35.2778]},
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


@pytest.mark.asyncio
async def test_run_compliance_check_wraps_vendor_timeout_as_upstream_data_error(async_session):
    site = Site(
        org_id=uuid.uuid4(), name="Vendor Error Site",
        polygon_geojson={"type": "FeatureCollection", "features": []},
        jurisdiction=Jurisdiction.OSHA_FEDERAL,
    )
    async_session.add(site)
    await async_session.flush()

    async_session.add(
        ThresholdRule(
            jurisdiction="osha_federal",
            metric_type=MetricType.HEAT_INDEX,
            heat_index_threshold_f=80.0,
            mandated_action="provide_water",
            citation="test",
        )
    )
    await async_session.flush()

    with patch(
        "app.services.compliance_service.create_heatmap_async",
        new=AsyncMock(side_effect=TaskTimeoutError("timed out")),
    ):
        with pytest.raises(UpstreamDataError, match="FortyGuard"):
            await run_compliance_check(async_session, site)


@pytest.mark.asyncio
async def test_compliance_check_persists_metric_metadata(async_session):
    site = Site(
        org_id=uuid.uuid4(), name="Persisted Site",
        polygon_geojson={"type": "FeatureCollection", "features": []},
        jurisdiction=Jurisdiction.OSHA_FEDERAL,
    )
    async_session.add(site)
    await async_session.flush()

    async_session.add(
        ThresholdRule(
            jurisdiction="osha_federal",
            metric_type=MetricType.HEAT_INDEX,
            heat_index_threshold_f=80.0,
            mandated_action="provide_water",
            citation="test",
        )
    )
    await async_session.flush()

    with patch(
        "app.services.compliance_service.create_heatmap_async",
        new=AsyncMock(return_value=MOCK_HEATMAP_RESPONSE),
    ), patch(
        "app.services.compliance_service.get_env_params_async",
        new=AsyncMock(return_value=MOCK_ENV_PARAMS_RESPONSE),
    ):
        check = await run_compliance_check(async_session, site)

    assert check.metric_label == "Heat Index"
    assert check.data_as_of == (__import__("datetime").date.today() - __import__("datetime").timedelta(days=6)).isoformat()


@pytest.mark.asyncio
async def test_uae_site_check_raises_unsupported_jurisdiction_before_vendor(async_session):
    site = Site(
        org_id=uuid.uuid4(), name="Dubai Yard",
        polygon_geojson={"type": "FeatureCollection", "features": []},
        jurisdiction=Jurisdiction.UAE,
    )
    async_session.add(site)
    await async_session.flush()

    async_session.add(
        ThresholdRule(
            jurisdiction="uae",
            metric_type=MetricType.DRY_BULB_TEMPERATURE,
            heat_index_threshold_f=None,
            mandated_action="work_stoppage_midday_window",
            citation="test",
        )
    )
    await async_session.flush()

    with patch(
        "app.services.compliance_service.create_heatmap_async",
        new=AsyncMock(),
    ) as mock_heatmap:
        with pytest.raises(UnsupportedJurisdictionError, match="FortyGuard currently covers US"):
            await run_compliance_check(async_session, site)

    mock_heatmap.assert_not_called()


def test_normalize_satellite_context_supports_documented_aliases():
    payload = {
        "result": {
            "segmentation": {
                "segments": {"roof": 42.0},
                "image_content": "abc123",
            },
            "original_image": ["xyz123"],
        }
    }

    segments, image = _normalize_satellite_context_payload(payload)

    assert segments == {"roof": 42.0}
    assert image == "data:image/png;base64,xyz123"


@pytest.mark.asyncio
async def test_heatmap_tiles_returns_converted_tiles_and_jurisdiction_threshold(async_session):
    site = Site(
        org_id=uuid.uuid4(), name="Tile Site",
        polygon_geojson={"type": "FeatureCollection", "features": []},
        jurisdiction=Jurisdiction.CAL_OSHA,
    )
    async_session.add(site)
    await async_session.flush()
    async_session.add_all([
        ThresholdRule(jurisdiction="cal_osha", metric_type=MetricType.DRY_BULB_TEMPERATURE, heat_index_threshold_f=80.0, mandated_action="shade", citation="test"),
        ThresholdRule(jurisdiction="cal_osha", metric_type=MetricType.DRY_BULB_TEMPERATURE, heat_index_threshold_f=95.0, mandated_action="high_heat", citation="test"),
    ])
    await async_session.flush()

    tile_payload = {
        "result": {"map_data": {"features": [
            {"geometry": {"type": "Polygon", "coordinates": []}, "properties": {"max_temperature": 0.0}},
            {"geometry": {"type": "Polygon", "coordinates": []}, "properties": {"max_temperature": 35.0}},
        ]}}
    }
    with patch("app.main.get_or_fetch_heatmap", new=AsyncMock(return_value=tile_payload)):
        response = await site_heatmap_tiles(
            site.id,
            CurrentUser(uuid.uuid4(), site.org_id, "admin"),
            async_session,
        )

    assert response["metric_label"] == "Temperature"
    assert response["tiles"][0]["temp_f"] == pytest.approx(32.0)
    assert response["tiles"][1]["temp_f"] == pytest.approx(95.0)