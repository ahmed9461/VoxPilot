import pytest

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import GpuOffer
from voxpilot.services.orchestrator import Orchestrator, OrchestratorError


class FakeVast:
    def __init__(self):
        self.search_count = 0
        self.created = False

    async def search_offers(self, query, limit, storage_gb=5.0):
        self.search_count += 1
        return [
            GpuOffer(
                offer_id=1,
                gpu_name="RTX 3090",
                gpu_ram_gb=24,
                price_per_hour=0.2,
                reliability=0.99,
                dlperf=10,
            )
        ]

    async def create_instance(self, *args, **kwargs):
        self.created = True
        return {"new_contract": 123}

    async def find_instances_by_label(self, *args, **kwargs):
        return []


@pytest.mark.asyncio
async def test_rent_refreshes_market_before_create(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    settings = Settings(
        vast_api_key="x",
        voxpilot_repo_url="https://github.com/ahmed9461/VoxPilot.git",
    )
    vast = FakeVast()
    orch = Orchestrator(settings, db, vast)
    await orch.offers()
    await orch.rent(1)
    assert vast.search_count == 2
    assert vast.created is True


class GoneVast(FakeVast):
    async def search_offers(self, query, limit, storage_gb=5.0):
        self.search_count += 1
        if self.search_count == 1:
            return await super().search_offers(query, limit, storage_gb=storage_gb)
        return []


@pytest.mark.asyncio
async def test_rent_rejects_offer_that_disappeared(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    settings = Settings(vast_api_key="x", voxpilot_repo_url="https://github.com/ahmed9461/VoxPilot.git")
    vast = GoneVast()
    orch = Orchestrator(settings, db, vast)
    await orch.offers()
    with pytest.raises(OrchestratorError):
        await orch.rent(1)
    assert vast.created is False
