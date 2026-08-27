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

    ttl = HISTORICAL_TTL_SECONDS if is_historical else RECENT_TTL_SECONDS
    await redis_client.set(key, json.dumps(result), ex=ttl)
    return result