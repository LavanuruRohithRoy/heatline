from fastapi import HTTPException
from app.core.redis_client import redis_client
from app.models import Plan

PLAN_LIMITS = {
    Plan.TRIAL: {"max_sites": 3, "checks_per_hour": 10},
    Plan.STANDARD: {"max_sites": 100, "checks_per_hour": 200},
}
WINDOW_SECONDS = 3600


async def enforce_check_rate_limit(org_id: str, plan: Plan) -> None:
    key = f"rate_limit:org:{org_id}"
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, WINDOW_SECONDS)
    limit = PLAN_LIMITS[plan]["checks_per_hour"]
    if current > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} checks/hour on the {plan.value} plan",
        )