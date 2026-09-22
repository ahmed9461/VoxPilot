from datetime import UTC, datetime, timedelta

import pytest

from voxpilot.db import Database
from voxpilot.services.billing import begin_billing, billing_snapshot, finalize_billing, pause_billing, resume_billing


@pytest.mark.asyncio
async def test_billing_pause_resume_and_finalize(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    start = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
    await begin_billing(db, 0.36, now=start)
    snap = await billing_snapshot(db, now=start + timedelta(minutes=10))
    assert snap is not None
    assert round(snap["estimated_cost_usd"], 4) == 0.06

    await pause_billing(db, now=start + timedelta(minutes=10))
    paused = await billing_snapshot(db, now=start + timedelta(minutes=30))
    assert round(paused["estimated_cost_usd"], 4) == 0.06

    await resume_billing(db, now=start + timedelta(minutes=30))
    final = await finalize_billing(db, now=start + timedelta(minutes=40))
    assert final is not None
    assert round(final["estimated_cost_usd"], 4) == 0.12
