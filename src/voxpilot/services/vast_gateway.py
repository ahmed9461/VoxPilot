from __future__ import annotations

import asyncio
import json
from typing import Any

from voxpilot.domain import GpuOffer, InstanceRef
from voxpilot.services.vast_models import (
    _coerce_mapping,
    _extract_rows,
    _instance_ref,
    _merge_nonempty,
    normalize_offer,
    network_rank,
)


class VastError(RuntimeError):
    pass


class VastOfferUnavailableError(VastError):
    pass


def _offer_unavailable(response: Any) -> bool:
    if not isinstance(response, dict) or response.get("success") is not False:
        return False
    error = str(response.get("error") or "").lower()
    message = str(response.get("msg") or "").lower()
    return error == "no_such_ask" or "no_such_ask" in message


def _inventory_rows(value: Any) -> list[dict[str, Any]]:
    """Never convert malformed, partial or failed inventory into 'empty'."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise VastError("Vast inventory response was invalid") from exc
    if isinstance(value, dict):
        if value.get("success") is False or value.get("error") or value.get("next_token") or value.get("has_more"):
            raise VastError("Vast inventory response was invalid or incomplete")
        rows = value.get("instances", value.get("results"))
        if value.get("total") is not None and (not isinstance(rows, list) or int(value["total"]) != len(rows)):
            raise VastError("Vast inventory response was incomplete")
    else:
        rows = value
    if not isinstance(rows, list):
        raise VastError("Vast inventory response was invalid")
    try:
        if any(not isinstance(row, dict) or int(row.get("id") or row.get("instance_id") or 0) <= 0 for row in rows):
            raise ValueError("invalid instance row")
    except (ValueError, TypeError, OverflowError) as exc:
        raise VastError("Vast inventory response was invalid") from exc
    return rows


def _complete_sdk_inventory(client: Any) -> list[dict[str, Any]]:
    # The pinned SDK convenience method discards page status/total metadata.
    # Read its documented v1 pages without losing evidence of an invalid result.
    from vastai.api.instances import show_instances_v1
    params: dict[str, Any] = {"select_filters": {}, "order_by": [{"col": "id", "dir": "asc"}], "limit": 25}
    rows: list[dict[str, Any]] = []
    tokens: set[str] = set()
    ids: set[int] = set()
    for _ in range(1000):
        page = show_instances_v1(client, params)
        if not isinstance(page, dict) or page.get("success") is False or page.get("error"):
            raise VastError("Vast inventory response was invalid")
        for row in _inventory_rows(page.get("instances")):
            instance_id = int(row.get("id") or row.get("instance_id"))
            if instance_id in ids:
                raise VastError("Vast inventory changed while paging")
            ids.add(instance_id)
            rows.append(row)
        token = page.get("next_token")
        if not token:
            try:
                total = page.get("total_instances")
                if total is not None and int(total) != len(rows):
                    raise VastError("Vast inventory response was incomplete")
            except (TypeError, ValueError, OverflowError) as exc:
                raise VastError("Vast inventory count was invalid") from exc
            return rows
        token = str(token)
        if token in tokens:
            raise VastError("Vast inventory pagination repeated a token")
        tokens.add(token)
        params["after_token"] = token
    raise VastError("Vast inventory pagination exceeded the safety limit")


class VastSdkGateway:
    def __init__(self, api_key: str, *, fish_api_port: int = 8080):
        self.api_key = api_key
        self.fish_api_port = fish_api_port
        self._client: Any | None = None

    def _get_client(self):
        if self._client is None:
            try:
                from vastai import VastAI
            except ImportError as exc:
                raise VastError("Install the official Vast SDK: pip install vastai") from exc
            self._client = VastAI(api_key=self.api_key, raw=True, quiet=True, retry=1)
        return self._client

    async def _inventory(self) -> list[dict[str, Any]]:
        client = self._get_client()
        from vastai import VastAI
        if not isinstance(client, VastAI):  # Explicit gateway test double.
            return _inventory_rows(await asyncio.to_thread(client.show_instances))
        return await asyncio.to_thread(_complete_sdk_inventory, client.client)

    async def search_offers(self, query: str | dict[str, Any], limit: int = 8, *, storage_gb: float = 5.0) -> list[GpuOffer]:
        client = self._get_client()
        display_limit = max(1, int(limit))
        backend_limit = max(32, min(200, display_limit * 8))
        by_id: dict[int, GpuOffer] = {}
        # Two live pools prevent a cheap-only cutoff from hiding fast hosts.
        # Keep SDK transport retries at one attempt: an unknown create must not
        # be replayed automatically. Read-only searches are safe to refresh.
        for order in ("inet_down-,dph_total", "dph_total,inet_down-"):
            try:
                result = await asyncio.to_thread(
                    client.search_offers, query=query, order=order,
                    limit=backend_limit, storage=float(storage_gb),
                )
            except Exception as exc:
                raise VastError("Vast search failed") from exc
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError as exc:
                    raise VastError("Vast search response was invalid") from exc
            rows = result if isinstance(result, list) else result.get("offers") if isinstance(result, dict) else None
            if not isinstance(rows, list) or isinstance(result, dict) and result.get("success") is False:
                raise VastError("Vast search response was invalid")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                offer = normalize_offer(row)
                if offer.offer_id > 0:
                    by_id[offer.offer_id] = offer
        return sorted(by_id.values(), key=network_rank)[:display_limit]


    async def find_offer(
        self,
        offer_id: int,
        *,
        policy_query: str,
        storage_gb: float,
    ) -> GpuOffer | None:
        """Resolve one selected offer without relying on display ranking.

        First combine the policy with a pre-parsed numeric id so the id bypasses
        Vast's text parser. If that endpoint returns no row, fall back to a wide
        fresh policy search and match the id locally.
        """
        client = self._get_client()
        target_id = int(offer_id)

        async def _search(query, limit: int):
            try:
                result = await asyncio.to_thread(
                    client.search_offers,
                    query=query,
                    order="dph_total",
                    limit=limit,
                    storage=float(storage_gb),
                )
            except Exception as exc:
                raise VastError("Vast selected-offer lookup failed") from exc
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = []
            return result if isinstance(result, list) else result.get("offers", []) if isinstance(result, dict) else []

        from vastai.api.query import offers_alias, offers_fields, offers_mult, parse_query

        exact_query = parse_query(policy_query, {}, offers_fields, offers_alias, offers_mult)
        exact_query["id"] = {"eq": target_id}
        rows = await _search(exact_query, 4)
        for row in rows:
            if isinstance(row, dict):
                item = normalize_offer(row)
                if item.offer_id == target_id:
                    return item

        rows = await _search(policy_query, 200)
        for row in rows:
            if isinstance(row, dict):
                item = normalize_offer(row)
                if item.offer_id == target_id:
                    return item
        return None

    async def create_instance(
        self,
        offer_id: int,
        *,
        image: str | None,
        disk_gb: int,
        template_hash: str | None = None,
        env: str | None = None,
        onstart_cmd: str | None = None,
        label: str = "VoxPilot",
        cancel_unavail: bool = True,
    ) -> dict[str, Any]:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "id": offer_id,
            "disk": disk_gb,
            "label": label,
            "ssh": True,
            "direct": True,
            "cancel_unavail": cancel_unavail,
        }
        if image:
            kwargs["image"] = image
        if template_hash:
            kwargs["template_hash"] = template_hash
        if env:
            kwargs["env"] = env
        if onstart_cmd:
            kwargs["onstart_cmd"] = onstart_cmd
        try:
            result = await asyncio.to_thread(client.create_instance, **kwargs)
        except Exception as exc:
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    if _offer_unavailable(response.json()):
                        raise VastOfferUnavailableError("Vast offer is no longer available") from exc
                except (ValueError, TypeError):
                    pass
            raise VastError("Vast create outcome is uncertain; reconcile before retrying") from exc
        mapped = _coerce_mapping(result)
        if _offer_unavailable(mapped):
            raise VastOfferUnavailableError("Vast offer is no longer available")
        return mapped if mapped else {"result": result}

    async def show_instance(self, instance_id: int) -> InstanceRef:
        client = self._get_client()
        try:
            raw_result = await asyncio.to_thread(client.show_instance, id=instance_id)
        except Exception as exc:
            raise VastError("Vast show_instance failed") from exc
        raw = _coerce_mapping(raw_result)
        rows = _extract_rows(raw, "instances", "instance")
        instance_raw = rows[0] if rows else raw
        ref = _instance_ref(instance_raw, api_port=self.fish_api_port, fallback_id=instance_id)
        if ref.status.lower() == "unknown" or not ref.public_ip or not ref.mapped_port:
            try:
                all_instances = await self._inventory()
            except Exception:
                all_instances = []
            fallback = next(
                (
                    row
                    for row in _extract_rows(all_instances, "instances", "results")
                    if isinstance(row, dict)
                    and int(row.get("id") or row.get("instance_id") or 0) == int(instance_id)
                ),
                None,
            )
            if fallback:
                instance_raw = _merge_nonempty(instance_raw, fallback)
                ref = _instance_ref(instance_raw, api_port=self.fish_api_port, fallback_id=instance_id)
        return ref

    async def find_instances_by_label(self, label: str, limit: int = 5) -> list[InstanceRef]:
        try:
            result = await self._inventory()
        except VastError:
            raise
        except Exception as exc:
            raise VastError("Vast instance reconciliation failed") from exc
        rows = _inventory_rows(result)
        refs: list[InstanceRef] = []
        for row in rows:
            if str(row.get("label") or "") != label:
                continue
            ref = _instance_ref(row, api_port=self.fish_api_port)
            if ref.instance_id > 0:
                refs.append(ref)
            if len(refs) >= max(1, min(int(limit), 25)):
                break
        return refs

    async def instance_exists(self, instance_id: int) -> bool:
        try:
            result = await self._inventory()
        except VastError:
            raise
        except Exception as exc:
            raise VastError("Vast inventory check failed") from exc
        return any(
            int(row.get("id") or row.get("instance_id")) == int(instance_id)
            for row in _inventory_rows(result)
        )

    async def start_instance(self, instance_id: int) -> None:
        await self._lifecycle("start_instance", instance_id)

    async def stop_instance(self, instance_id: int) -> None:
        await self._lifecycle("stop_instance", instance_id)

    async def destroy_instance(self, instance_id: int) -> None:
        await self._lifecycle("destroy_instance", instance_id)

    async def _lifecycle(self, method: str, instance_id: int) -> None:
        client = self._get_client()
        try:
            response = await asyncio.to_thread(getattr(client, method), id=instance_id)
        except Exception as exc:
            raise VastError(f"Vast {method} failed") from exc
        response = _coerce_mapping(response)
        if response.get("success") is False or response.get("error"):
            raise VastError(f"Vast {method} was rejected by the provider")
