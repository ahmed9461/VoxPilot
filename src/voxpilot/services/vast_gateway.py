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
            self._client = VastAI(api_key=self.api_key, raw=True, quiet=True)
        return self._client

    async def search_offers(self, query: str | dict[str, Any], limit: int = 8, *, storage_gb: float = 5.0) -> list[GpuOffer]:
        client = self._get_client()
        display_limit = max(1, int(limit))
        backend_limit = max(32, min(200, display_limit * 8))
        try:
            result = await asyncio.to_thread(
                client.search_offers,
                query=query,
                order="dph_total",
                limit=backend_limit,
                storage=float(storage_gb),
            )
        except Exception as exc:
            raise VastError(f"Vast search failed: {exc}") from exc
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = []
        rows = result if isinstance(result, list) else result.get("offers", []) if isinstance(result, dict) else []
        offers = [normalize_offer(row) for row in rows if isinstance(row, dict)]
        offers = [offer for offer in offers if offer.offer_id > 0]
        offers.sort(key=lambda x: (x.price_per_hour, -(x.dlperf or 0.0), -(x.inet_down_mbps or 0.0)))
        return offers[:display_limit]


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
                raise VastError(f"Vast selected-offer lookup failed: {exc}") from exc
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
            raise VastError(f"Vast create_instance failed: {exc}") from exc
        mapped = _coerce_mapping(result)
        if _offer_unavailable(mapped):
            raise VastOfferUnavailableError("Vast offer is no longer available")
        return mapped if mapped else {"result": result}

    async def show_instance(self, instance_id: int) -> InstanceRef:
        client = self._get_client()
        try:
            raw_result = await asyncio.to_thread(client.show_instance, id=instance_id)
        except Exception as exc:
            raise VastError(f"Vast show_instance failed: {exc}") from exc
        raw = _coerce_mapping(raw_result)
        rows = _extract_rows(raw, "instances", "instance")
        instance_raw = rows[0] if rows else raw
        ref = _instance_ref(instance_raw, api_port=self.fish_api_port, fallback_id=instance_id)
        if ref.status.lower() == "unknown" or not ref.public_ip or not ref.mapped_port:
            try:
                all_instances = await asyncio.to_thread(client.show_instances)
            except Exception:
                all_instances = []
            fallback = next(
                (
                    row
                    for row in all_instances
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
        client = self._get_client()
        try:
            result = await asyncio.to_thread(client.show_instances)
        except Exception as exc:
            raise VastError(f"Vast instance reconciliation failed: {exc}") from exc
        rows = _extract_rows(result, "instances", "results")
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
        client = self._get_client()
        try:
            result = await asyncio.to_thread(client.show_instances)
        except Exception as exc:
            raise VastError(f"Vast inventory check failed: {exc}") from exc
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError as exc:
                raise VastError("Vast inventory response was invalid") from exc
        if not isinstance(result, list) and not (
            isinstance(result, dict)
            and any(isinstance(result.get(key), list) for key in ("instances", "results"))
        ):
            raise VastError("Vast inventory response was invalid")
        return any(
            int(row.get("id") or row.get("instance_id") or 0) == int(instance_id)
            for row in _extract_rows(result, "instances", "results")
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
            raise VastError(f"Vast {method} failed: {exc}") from exc
        if isinstance(response, dict) and (response.get("success") is False or response.get("error")):
            raise VastError(f"Vast {method} was rejected by the provider")
