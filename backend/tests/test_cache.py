import pytest
from unittest.mock import AsyncMock
from app.integrations.cache import get_or_fetch_heatmap


@pytest.mark.asyncio
async def test_second_identical_call_uses_cache_not_fetch_fn():
    fetch_fn = AsyncMock(return_value={"result": "mocked heatmap data"})

    params = {
        "polygon_aoi": {"type": "FeatureCollection", "features": []},
        "start_date": "2026-08-25",
        "filter_type": 3,
        "granularity": 60,
        "analytic_type": "tcm",
    }

    result1 = await get_or_fetch_heatmap(fetch_fn, is_historical=True, **params)
    result2 = await get_or_fetch_heatmap(fetch_fn, is_historical=True, **params)

    assert result1 == result2
    fetch_fn.assert_called_once()  # second call must be served from cache, not re-invoke fetch_fn