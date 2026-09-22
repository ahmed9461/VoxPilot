import pytest

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import GpuOffer
from voxpilot.services.orchestrator import OfferUnavailableError, Orchestrator


def offer(offer_id: int = 1, price: float = 0.2) -> GpuOffer:
    return GpuOffer(
        offer_id=offer_id,
        gpu_name="RTX 3090",
        gpu_ram_gb=24,
        price_per_hour=price,
        reliability=0.99,
        dlperf=10,
    )


class FakeVast:
    def __init__(self):
        self.search_calls = []
        self.created = False

    async def search_offers(self, query, limit, storage_gb=5.0):
        self.search_calls.append((query, limit, storage_gb))
        if "id=1" in query:
            return [offer(1)]
        return [offer(1), offer(2, 0.21)]

    async def create_instance(self, *args, **kwargs):
        self.created = True
        return {"new_contract": 123}

    async def find_instances_by_label(self, *args, **kwargs):
        return []


@pytest.mark.asyncio
async def test_rent_revalidates_exact_offer_id_and_real_storage(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    settings = Settings(
        vast_api_key="x",
        vast_disk_gb=60,
        voxpilot_repo_url="https://github.com/ahmed9461/VoxPilot.git",
    )
    vast = FakeVast()
    orch = Orchestrator(settings, db, vast)

    await orch.offers()
    await orch.rent(1)

    assert len(vast.search_calls) == 2
    display_query, _, display_storage = vast.search_calls[0]
    exact_query, exact_limit, exact_storage = vast.search_calls[1]
    assert "id=1" not in display_query
    assert "id=1" in exact_query
    assert exact_limit == 1
    assert display_storage == 60.0
    assert exact_storage == 60.0
    assert vast.created is True


class GoneVast(FakeVast):
    async def search_offers(self, query, limit, storage_gb=5.0):
        self.search_calls.append((query, limit, storage_gb))
        if "id=1" in query:
            return []
        return [offer(1)]


@pytest.mark.asyncio
async def test_rent_rejects_exact_offer_that_disappeared(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    settings = Settings(
        vast_api_key="x",
        vast_disk_gb=60,
        voxpilot_repo_url="https://github.com/ahmed9461/VoxPilot.git",
    )
    vast = GoneVast()
    orch = Orchestrator(settings, db, vast)

    await orch.offers()
    with pytest.raises(OfferUnavailableError):
        await orch.rent(1)

    assert vast.created is False
    assert "id=1" in vast.search_calls[-1][0]
