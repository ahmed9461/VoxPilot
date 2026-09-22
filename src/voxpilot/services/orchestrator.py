from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime
from typing import Any

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import GpuOffer, InstancePhase, TTSSettings
from voxpilot.services.billing import begin_billing
from voxpilot.services.instance_runtime import InstanceRuntime, ProgressCallback
from voxpilot.services.provisioning import build_onstart_cmd, build_vast_env, extract_instance_id
from voxpilot.services.vast_gateway import VastSdkGateway
from voxpilot.services.vast_models import build_offer_query


class OrchestratorError(RuntimeError):
    pass


class OfferUnavailableError(OrchestratorError):
    pass


class Orchestrator:
    def __init__(self, settings: Settings, db: Database, vast: VastSdkGateway):
        self.settings = settings
        self.db = db
        self.vast = vast
        self.runtime = InstanceRuntime(settings, db, vast)
        self._rent_lock = asyncio.Lock()

    def _offer_query(self) -> str:
        return build_offer_query(
            self.settings.vast_min_gpu_ram_gb,
            self.settings.vast_min_reliability,
            self.settings.vast_max_price_usd_hour,
            disk_gb=self.settings.vast_disk_gb,
            verified_only=self.settings.vast_verified_only,
            datacenter_only=self.settings.vast_datacenter_only,
            min_direct_ports=self.settings.vast_min_direct_ports,
            min_inet_down_mbps=self.settings.vast_min_inet_down_mbps,
        )

    def _offer_eligible(self, offer: GpuOffer) -> bool:
        if offer.offer_id <= 0:
            return False
        if offer.gpu_ram_gb < self.settings.vast_min_gpu_ram_gb:
            return False
        if offer.price_per_hour <= 0 or offer.price_per_hour > self.settings.vast_max_price_usd_hour:
            return False
        if offer.reliability is None or offer.reliability < self.settings.vast_min_reliability:
            return False
        if offer.disk_space_gb is not None and offer.disk_space_gb < self.settings.vast_disk_gb:
            return False
        if self.settings.vast_verified_only and offer.verified is False:
            return False
        if self.settings.vast_min_inet_down_mbps > 0 and (offer.inet_down_mbps or 0.0) < self.settings.vast_min_inet_down_mbps:
            return False

        raw = offer.raw or {}
        if raw:
            if int(raw.get("num_gpus") or 1) != 1:
                return False
            if raw.get("rentable") is False:
                return False
            if self.settings.vast_datacenter_only and not bool(raw.get("datacenter")):
                return False
            if self.settings.vast_min_direct_ports > 0:
                try:
                    direct_ports = int(raw.get("direct_port_count") or 0)
                except (TypeError, ValueError):
                    direct_ports = 0
                if direct_ports < self.settings.vast_min_direct_ports:
                    return False
        return True

    async def offers(self) -> list[GpuOffer]:
        query = self._offer_query()
        rows = await self.vast.search_offers(
            query,
            self.settings.vast_default_limit,
            storage_gb=float(self.settings.vast_disk_gb),
        )
        await self.db.set_many(
            {
                "offers.last": [row.public_dict() for row in rows],
                "offers.last_refreshed_at": datetime.now(UTC).isoformat(),
            }
        )
        await self.db.event("offers.search", {"query": query, "count": len(rows)})
        return rows

    async def cached_offer(self, offer_id: int) -> GpuOffer | None:
        rows = await self.db.get("offers.last", [])
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and int(row.get("offer_id") or 0) == int(offer_id):
                return GpuOffer(**row)
        return None

    async def rent(self, offer_id: int) -> dict[str, Any]:
        async with self._rent_lock:
            self.settings.validate_rent_ready()
            if await self.db.get("instance.id"):
                raise OrchestratorError("There is already an active instance")
            # A timed-out or sparse create response may still have produced a
            # paid instance. Its unique label must be reconciled before any
            # second create request is allowed.
            if await self.db.get("instance.pending_label"):
                raise OrchestratorError("A previous Vast rental is unresolved; reconcile it before renting again")
            phase = await self.db.get("instance.phase", InstancePhase.NONE.value)
            if phase not in {InstancePhase.NONE.value, InstancePhase.ERROR.value}:
                raise OrchestratorError(f"Instance lifecycle is busy: {phase}")

            cached = await self.cached_offer(offer_id)
            if cached is None:
                raise OfferUnavailableError("Offer is not in the latest displayed marketplace snapshot")

            offer = await self.vast.find_offer(
                int(offer_id),
                policy_query=self._offer_query(),
                storage_gb=float(self.settings.vast_disk_gb),
            )
            if offer is None:
                raise OfferUnavailableError("Offer is no longer available")
            if not self._offer_eligible(offer):
                raise OfferUnavailableError("Offer no longer matches the configured rental policy")

            fish_token = secrets.token_urlsafe(32)
            label = f"VoxPilot-{secrets.token_hex(6)}"
            await self.db.set_many(
                {
                    "instance.phase": InstancePhase.RENTING.value,
                    "instance.pending_label": label,
                    "instance.offer": offer.public_dict(),
                    "fish.token": fish_token,
                    "fish.url": None,
                }
            )

            result: dict[str, Any] | None = None
            create_error: Exception | None = None
            try:
                result = await self.vast.create_instance(
                    offer_id,
                    image=None if self.settings.vast_template_hash else self.settings.vast_docker_image,
                    disk_gb=self.settings.vast_disk_gb,
                    template_hash=self.settings.vast_template_hash,
                    env=build_vast_env(self.settings, fish_token),
                    onstart_cmd=build_onstart_cmd(self.settings),
                    label=label,
                    cancel_unavail=self.settings.vast_cancel_unavailable,
                )
            except Exception as exc:
                create_error = exc

            instance_id = extract_instance_id(result or {})
            if not instance_id:
                try:
                    matches = await self.vast.find_instances_by_label(label)
                except Exception as exc:
                    matches = []
                    await self.db.event("instance.reconcile_failed", {"label": label, "error": str(exc)})
                if len(matches) == 1:
                    instance_id = matches[0].instance_id
                    await self.db.event("instance.reconciled", {"instance_id": instance_id, "label": label})

            if not instance_id:
                await self.db.set("instance.phase", InstancePhase.ERROR.value)
                await self.db.event(
                    "instance.rent_failed",
                    {"offer_id": offer_id, "label": label, "error": str(create_error or result)},
                )
                if create_error:
                    raise OrchestratorError("Vast rental failed and no created instance could be reconciled") from create_error
                raise OrchestratorError("Vast rental response did not contain an instance id")

            await self.db.set_many(
                {
                    "instance.id": instance_id,
                    "instance.label": label,
                    "instance.pending_label": None,
                    "instance.phase": InstancePhase.BOOTING.value,
                }
            )
            await begin_billing(self.db, offer.price_per_hour)
            await self.db.event("instance.rented", {"instance_id": instance_id, "offer_id": offer_id})
            return {"instance_id": instance_id, "offer": offer.public_dict(), "raw": result or {}}

    async def rent_and_prepare(self, offer_id: int, progress: ProgressCallback | None = None) -> dict[str, Any]:
        result = await self.rent(offer_id)
        try:
            await self.runtime.wait_until_ready(result["instance_id"], progress=progress)
            return result
        except Exception as exc:
            current = await self.db.get("instance.id")
            if current and int(current) == int(result["instance_id"]):
                phase = await self.db.get("instance.phase")
                if phase not in {InstancePhase.STOPPING.value, InstancePhase.STOPPED.value, InstancePhase.DESTROYING.value}:
                    await self.db.set("instance.phase", InstancePhase.ERROR.value)
                await self.db.event("instance.provision_failed", {"instance_id": current, "error": str(exc)})
                if self.settings.vast_auto_destroy_on_provision_failure and phase not in {
                    InstancePhase.STOPPING.value,
                    InstancePhase.STOPPED.value,
                    InstancePhase.DESTROYING.value,
                }:
                    try:
                        await self.runtime.destroy_current()
                    except Exception as destroy_exc:
                        await self.db.event("instance.rollback_failed", {"instance_id": current, "error": str(destroy_exc)})
            raise

    async def synthesize(
        self,
        text: str,
        settings: TTSSettings,
        *,
        reference_audio: bytes | None = None,
        reference_text: str | None = None,
    ) -> bytes:
        return await self.runtime.synthesize(
            text,
            settings,
            reference_audio=reference_audio,
            reference_text=reference_text,
        )

    async def recover_current(self) -> None:
        await self.runtime.recover_current()

    async def current_state(self, *, probe_fish: bool = False) -> dict[str, Any]:
        return await self.runtime.current_state(probe_fish=probe_fish)

    async def stop_current(self) -> bool:
        return await self.runtime.stop_current()

    async def start_current(self, progress: ProgressCallback | None = None) -> bool:
        return await self.runtime.start_current(progress=progress)

    async def destroy_current(self) -> bool:
        return await self.runtime.destroy_current()

    async def last_billing_snapshot(self) -> dict[str, Any] | None:
        return await self.runtime.last_billing_snapshot()
