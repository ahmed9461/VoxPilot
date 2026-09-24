from dataclasses import replace

import pytest

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import GpuOffer
from voxpilot.services.orchestrator import OfferUnavailableError, Orchestrator, OrchestratorError
from voxpilot.services.vast_gateway import VastError, VastOfferUnavailableError


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
    def __init__(self, selected: GpuOffer | None = None, rows: list[GpuOffer] | None = None):
        self.selected = selected or offer(1)
        self.rows = rows if rows is not None else [offer(1), offer(2, 0.21)]
        self.search_calls = []
        self.find_calls = []
        self.created = False
        self.create_error = None
        self.reconcile_error = None

    async def search_offers(self, query, limit, storage_gb=5.0):
        self.search_calls.append((query, limit, storage_gb))
        return self.rows[:limit]

    async def find_offer(self, offer_id, *, policy_query, storage_gb):
        self.find_calls.append((offer_id, policy_query, storage_gb))
        return self.selected if self.selected and self.selected.offer_id == offer_id else None

    async def create_instance(self, *args, **kwargs):
        self.created = True
        if self.create_error:
            raise self.create_error
        return {"new_contract": 123}

    async def find_instances_by_label(self, *args, **kwargs):
        if self.reconcile_error:
            raise self.reconcile_error
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
async def test_rent_rejects_price_increase_over_hard_ceiling(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    vast = FakeVast(selected=offer(1, price=0.51))
    orch = Orchestrator(Settings(vast_api_key="x", vast_max_price_usd_hour=0.50), db, vast)

    assert [item.offer_id for item in await orch.offers()] == [1, 2]
    with pytest.raises(OfferUnavailableError):
        await orch.rent(1)

    assert vast.created is False
    assert await db.get("instance.pending_label") is None


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


@pytest.mark.asyncio
async def test_search_does_not_display_offers_its_local_policy_would_reject(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    vast = FakeVast(rows=[offer(1, inet_down=20), offer(2, 0.21), offer(3, direct_ports=0)])
    orch = Orchestrator(Settings(vast_api_key="x"), db, vast)

    displayed = await orch.offers()

    assert [item.offer_id for item in displayed] == [2]
    assert [item["offer_id"] for item in await db.get("offers.last")] == [2]
    assert vast.search_calls[0][1] > orch.settings.vast_default_limit
    assert "rented=false" in vast.search_calls[0][0]


@pytest.mark.asyncio
async def test_missing_optional_provider_fields_do_not_false_reject_policy_match(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    partial = offer(3)
    partial.raw.pop("direct_port_count")
    partial = replace(partial, inet_down_mbps=None)
    vast = FakeVast(selected=partial, rows=[partial])
    orch = Orchestrator(Settings(vast_api_key="x"), db, vast)

    assert [item.offer_id for item in await orch.offers()] == [3]
    result = await orch.rent(3)
    assert result["instance_id"] == 123


@pytest.mark.asyncio
async def test_failed_offer_is_excluded_from_immediate_refresh(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    orch = Orchestrator(Settings(vast_api_key="x"), db, FakeVast())

    displayed = await orch.offers(exclude_offer_ids={1})

    assert [item.offer_id for item in displayed] == [2]
    assert [item["offer_id"] for item in await db.get("offers.last")] == [2]


@pytest.mark.asyncio
async def test_definitive_create_rejection_releases_pending_label(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    vast = FakeVast()
    vast.create_error = VastOfferUnavailableError("no_such_ask")
    orch = Orchestrator(Settings(vast_api_key="x"), db, vast)
    await orch.offers()

    with pytest.raises(OfferUnavailableError):
        await orch.rent(1)

    assert await db.get("instance.phase") == "none"
    assert await db.get("instance.pending_label") is None
    assert await db.get("instance.id") is None
    assert await db.get("fish.token") is None


@pytest.mark.asyncio
async def test_ambiguous_create_result_keeps_duplicate_rental_guard(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    vast = FakeVast()
    vast.create_error = VastError("timeout")
    orch = Orchestrator(Settings(vast_api_key="x"), db, vast)
    await orch.offers()

    with pytest.raises(OrchestratorError):
        await orch.rent(1)

    assert await db.get("instance.phase") == "error"
    assert await db.get("instance.pending_label") is not None
    with pytest.raises(OrchestratorError, match="unresolved"):
        await orch.rent(1)


@pytest.mark.asyncio
async def test_provider_rejection_with_failed_inventory_stays_unresolved(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    vast = FakeVast()
    vast.create_error = VastOfferUnavailableError("no_such_ask")
    vast.reconcile_error = VastError("inventory unavailable")
    orch = Orchestrator(Settings(vast_api_key="x"), db, vast)
    await orch.offers()

    with pytest.raises(OrchestratorError):
        await orch.rent(1)

    assert await db.get("instance.pending_label") is not None
