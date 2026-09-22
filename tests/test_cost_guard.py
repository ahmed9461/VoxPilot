from datetime import UTC, datetime, timedelta

import pytest

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import InstancePhase
from voxpilot.services.billing import begin_billing, pause_billing
from voxpilot.services.cost_guard import _tick


class FakeBot:
    def __init__(self):
        self.messages: list[str] = []

    async def send_message(self, owner_id: int, text: str) -> None:
        self.messages.append(text)


@pytest.mark.asyncio
async def test_cost_guard_warns_once_while_paid_instance_is_not_ready(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.PROVISIONING.value})
    await begin_billing(db, 0.2, now=datetime.now(UTC) - timedelta(minutes=15))
    bot = FakeBot()
    settings = Settings(owner_telegram_id=1, cost_guard_warn_minutes=10)

    await _tick(bot, settings, db, orchestrator=None)
    await _tick(bot, settings, db, orchestrator=None)

    assert len(bot.messages) == 1
    assert "لم يصل إلى جاهزية Fish" in bot.messages[0]
    assert await db.get("cost_guard.warned_paid_phase") == "123:provisioning"

    await db.set("instance.phase", InstancePhase.STOPPING.value)
    await _tick(bot, settings, db, orchestrator=None)
    assert len(bot.messages) == 2
    assert "لم يؤكد Vast إيقاف" in bot.messages[1]


@pytest.mark.asyncio
async def test_cost_guard_does_not_warn_for_paused_billing(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.ERROR.value})
    started = datetime.now(UTC) - timedelta(minutes=15)
    await begin_billing(db, 0.2, now=started)
    await pause_billing(db, now=started + timedelta(minutes=1))
    bot = FakeBot()

    await _tick(bot, Settings(owner_telegram_id=1, cost_guard_warn_minutes=10), db, orchestrator=None)

    assert bot.messages == []
