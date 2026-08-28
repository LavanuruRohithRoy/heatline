import hashlib
import json
from app.core.redis_client import redis_client

# Historical (already-elapsed) day queries never change once fetched — cache long.
# A "most recent day" query could still be finalizing server-side, so it gets a shorter TTL.
HISTORICAL_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
RECENT_TTL_SECONDS = 60 * 60  # 1 hour


def _make_cache_key(**kwargs) -> str:
    canonical = json.dumps(kwargs, sort_keys=True, default=str)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"heatmap:{digest}"


def _is_empty_result(result: dict) -> bool:
    payload = result.get("result")
    if not isinstance(payload, dict):
        return False
    features = payload.get("map_data", {}).get("features")
    locations = payload.get("locations")
    if features is not None and len(features) == 0:
        return True
    if locations is not None and len(locations) == 0:
        return True
    return False


async def get_or_fetch_heatmap(fetch_fn, *, is_historical: bool = True, **cache_params) -> dict:
    """
    Wraps a FortyGuard heatmap fetch with a Redis cache, keyed by the exact
    request parameters. is_historical=True (default) uses a long TTL since
    past-day data doesn't change; pass False for same-day/live queries.
    """
    key = _make_cache_key(**cache_params)
    cached = await redis_client.get(key)
    if cached is not None:
        return json.loads(cached)

    result = await fetch_fn()

    if not _is_empty_result(result):
        ttl = HISTORICAL_TTL_SECONDS if is_historical else RECENT_TTL_SECONDS
        await redis_client.set(key, json.dumps(result), ex=ttl)

    return result