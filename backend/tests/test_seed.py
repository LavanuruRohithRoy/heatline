import pytest
from sqlalchemy import select
from app.models import ThresholdRule
from app.seed import THRESHOLD_RULES, seed_threshold_rules


@pytest.mark.asyncio
async def test_seed_threshold_rules_is_idempotent(async_session):
    inserted, skipped = await seed_threshold_rules(async_session)
    assert inserted == len(THRESHOLD_RULES)
    assert skipped == 0

    inserted_again, skipped_again = await seed_threshold_rules(async_session)
    assert inserted_again == 0
    assert skipped_again == len(THRESHOLD_RULES)

    rows = (await async_session.execute(select(ThresholdRule))).scalars().all()
    assert len(rows) == len(THRESHOLD_RULES)
