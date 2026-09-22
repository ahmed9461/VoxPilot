import pytest

from voxpilot.services.vast_gateway import VastError, VastSdkGateway


def raw_offer(offer_id: int, price: float = 0.2):
    return {
        "id": offer_id,
        "gpu_name": "RTX 3090",
        "gpu_ram": 24576,
        "dph_total": price,
        "reliability": 0.99,
        "inet_down": 500,
        "disk_space": 100,
        "verified": True,
        "num_gpus": 1,
        "rentable": True,
        "direct_port_count": 2,
    }


class FakeClient:
    def __init__(self, direct_rows=None, fallback_rows=None):
        self.direct_rows = direct_rows if direct_rows is not None else []
        self.fallback_rows = fallback_rows if fallback_rows is not None else []
        self.calls = []

    def search_offers(self, *, query, order, limit, storage):
        self.calls.append((query, order, limit, storage))
        if isinstance(query, dict):
            return list(self.direct_rows)
        return list(self.fallback_rows)

    def show_instances(self):
        return list(self.direct_rows)


@pytest.mark.asyncio
async def test_find_offer_uses_numeric_id_query_first():
    client = FakeClient(direct_rows=[raw_offer(123)])
    gateway = VastSdkGateway("x")
    gateway._client = client

    found = await gateway.find_offer(
        123,
        policy_query="num_gpus=1 rentable=true",
        storage_gb=60,
    )

    assert found is not None
    assert found.offer_id == 123
    query, _, limit, storage = client.calls[0]
    assert query == {"id": {"eq": 123}}
    assert limit == 4
    assert storage == 60.0
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_find_offer_falls_back_to_wide_policy_search():
    client = FakeClient(
        direct_rows=[],
        fallback_rows=[raw_offer(111), raw_offer(123), raw_offer(222)],
    )
    gateway = VastSdkGateway("x")
    gateway._client = client

    found = await gateway.find_offer(
        123,
        policy_query="num_gpus=1 rentable=true",
        storage_gb=60,
    )

    assert found is not None
    assert found.offer_id == 123
    assert len(client.calls) == 2
    fallback_query, _, fallback_limit, fallback_storage = client.calls[1]
    assert fallback_query == "num_gpus=1 rentable=true"
    assert fallback_limit == 200
    assert fallback_storage == 60.0


@pytest.mark.asyncio
async def test_inventory_confirmation_checks_exact_instance_id():
    gateway = VastSdkGateway("x")
    gateway._client = FakeClient(direct_rows=[{"id": 111}, {"id": 222}])

    assert await gateway.instance_exists(222) is True
    assert await gateway.instance_exists(333) is False


@pytest.mark.asyncio
async def test_malformed_inventory_cannot_confirm_deletion():
    class MalformedClient:
        def show_instances(self):
            return {"error": "temporary"}

    gateway = VastSdkGateway("x")
    gateway._client = MalformedClient()

    with pytest.raises(VastError, match="invalid"):
        await gateway.instance_exists(222)


@pytest.mark.asyncio
async def test_lifecycle_rejects_provider_success_false():
    class RejectedClient:
        def start_instance(self, *, id):
            return {"success": False, "error": "provider declined"}

    gateway = VastSdkGateway("x")
    gateway._client = RejectedClient()

    with pytest.raises(VastError, match="rejected"):
        await gateway.start_instance(222)
