import pytest

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import GpuOffer
from voxpilot.services.orchestrator import OfferUnavailableError, Orchestrator, OrchestratorError


def offer(
    offer_id: int = 1,
    price: float = 0.2,
    *,
    inet_down: float = 500,
    direct_ports: int = 2,
) -> GpuOffer:
    return GpuOffer(
        offer_id=offer_id,
        gpu_name="RTX 3090",
        gpu_ram_gb=24,
        price_per_hour=price,
        reliability=0.99,
        dlperf=10,
        inet_down_mbps=inet_down,
        disk_space_gb=100,
        verified=True,
        raw={
            "num_gpus": 1,
            "rentable": True,
            "direct_port_count": direct_ports,
        },
    )


class FakeVast:
    def __init__(self, selected: GpuOffer | None = None):
        self.selected = selected or offer(1)
        self.search_calls = []
        self.find_calls = []
        self.created = False

    async def search_offers(self, query, limit, storage_gb=5.0):
        self.search_calls.append((query, limit, storage_gb))
        return [offer(1), offer(2, 0.21)]

    async def find_offer(self, offer_id, *, policy_query, storage_gb):
        self.find_calls.append((offer_id, policy_query, storage_gb))
        return self.selected if self.selected and self.selected.offer_id == offer_id else None

    async def create_instance(self, *args, **kwargs):
        self.created = True
        return {"new_contract": 123}

    async def find_instances_by_label(self, *args, **kwargs):
        return []


@pytest.mark.asyncio
async def test_rent_uses_selected_offer_lookup_and_real_storage(tmp_path):
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

    assert vast.find_calls
    offer_id, policy_query, storage_gb = vast.find_calls[0]
    assert offer_id == 1
    assert "gpu_ram>=24" in policy_query
    assert storage_gb == 60.0
    assert vast.created is True


@pytest.mark.asyncio
async def test_rent_rejects_offer_lookup_miss(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    settings = Settings(
        vast_api_key="x",
        vast_disk_gb=60,
        voxpilot_repo_url="https://github.com/ahmed9461/VoxPilot.git",
    )
    vast = FakeVast(selected=None)
    vast.selected = None
    orch = Orchestrator(settings, db, vast)

    await orch.offers()
    with pytest.raises(OfferUnavailableError):
        await orch.rent(1)

    assert vast.created is False


@pytest.mark.asyncio
async def test_rent_rejects_offer_that_no_longer_matches_policy(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    settings = Settings(
        vast_api_key="x",
        vast_disk_gb=60,
        vast_min_inet_down_mbps=100,
        voxpilot_repo_url="https://github.com/ahmed9461/VoxPilot.git",
    )
    vast = FakeVast(selected=offer(1, inet_down=20))
    orch = Orchestrator(settings, db, vast)

    await orch.offers()
    with pytest.raises(OfferUnavailableError):
        await orch.rent(1)

    assert vast.created is False


@pytest.mark.asyncio
async def test_unresolved_create_blocks_second_rental(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.phase": "error", "instance.pending_label": "VoxPilot-unresolved"})
    vast = FakeVast()
    orch = Orchestrator(Settings(vast_api_key="x"), db, vast)

    with pytest.raises(OrchestratorError, match="unresolved"):
        await orch.rent(1)

    assert vast.created is False
