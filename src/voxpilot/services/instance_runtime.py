from __future__ import annotations

import asyncio
import math
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Awaitable, Callable

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import InstancePhase, TTSSettings
from voxpilot.services.billing import (
    begin_billing, billing_snapshot, finalize_billing, last_billing_snapshot,
    pause_billing, resume_billing, sync_billing_status,
)
from voxpilot.services.fish_client import FishClient
from voxpilot.services.provisioning import fish_url
from voxpilot.services.vast_gateway import VastSdkGateway

ProgressCallback = Callable[[str], Awaitable[None]]
_UNSET = object()
_STOP_PHASES = {"stopping", "stopped", "destroying", "none"}
_IDENTITY_KEYS = ["instance.id", "instance.generation", "instance.phase"]
_PENDING_KEYS = ["instance.pending_label", "instance.pending_since", "instance.pending_rejected",
                 "instance.pending_checked_at", "instance.pending_status"]


class RuntimeErrorState(RuntimeError):
    pass


class StaleConfirmation(RuntimeErrorState):
    pass


def _date(value: Any) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value))
        return stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp.astimezone(UTC)
    except (TypeError, ValueError):
        return None


class InstanceRuntime:
    def __init__(self, settings: Settings, db: Database, vast: VastSdkGateway):
        self.settings = settings
        self.db = db
        self.vast = vast
        self._control_lock = asyncio.Lock()
        self._tts_lock = asyncio.Lock()
        self._recovery_lock = asyncio.Lock()

    @property
    def control_lock(self) -> asyncio.Lock:
        # Rental and recovery share the same lifecycle lock as stop/destroy.
        return self._control_lock

    async def _check(self, instance_id: int, generation: Any = _UNSET, phases: set[str] | None = None) -> dict:
        values = await self.db.get_many(_IDENTITY_KEYS)
        if (values.get("instance.id") != instance_id
                or generation is not _UNSET and values.get("instance.generation") != generation
                or phases is not None and values.get("instance.phase") not in phases):
            raise RuntimeErrorState("Instance lifecycle changed")
        return values

    async def mark_failure(self, instance_id: int, generation: Any, kind: str, exc: Exception) -> bool:
        async with self._control_lock:
            try:
                await self._check(instance_id, generation, {"renting", "booting", "provisioning", "error"})
            except RuntimeErrorState:
                return False
            await self.db.set("instance.phase", InstancePhase.ERROR.value)
            await self.db.event(kind, {"instance_id": instance_id, "error_type": type(exc).__name__})
            return True

    async def wait_until_ready(
        self, instance_id: int, progress: ProgressCallback | None = None, *, expected_generation: Any = _UNSET,
    ) -> None:
        async with self._control_lock:
            values = await self._check(instance_id, expected_generation, {"booting", "provisioning", "error", "ready"})
            generation = values.get("instance.generation")
            token = str(await self.db.get("fish.token") or "")
            if not token:
                raise RuntimeErrorState("Fish authentication token is unavailable")
            await self.db.set("instance.phase", InstancePhase.PROVISIONING.value)
        deadline = time.monotonic() + self.settings.fish_ready_timeout_seconds
        last_progress = 0.0
        while time.monotonic() < deadline:
            await self._check(instance_id, generation, {"provisioning"})
            ref = await self.vast.show_instance(instance_id)
            status = ref.status.lower()
            async with self._control_lock:
                await self._check(instance_id, generation, {"provisioning"})
                if status in {"exited", "error", "failed", "dead"}:
                    raise RuntimeErrorState("Vast instance entered a terminal state")
                if status == "stopped":
                    await pause_billing(self.db)
                    await self.db.set("instance.phase", InstancePhase.STOPPED.value)
                    raise RuntimeErrorState("Vast instance stopped before Fish became ready")
                if status in {"running", "frozen"}:
                    await sync_billing_status(self.db, status)
            if ref.public_ip and ref.mapped_port:
                url = fish_url(self.settings, ref.public_ip, ref.mapped_port)
                client = FishClient(url, token, verify_tls=self.settings.fish_verify_tls,
                                    timeout_seconds=self.settings.fish_request_timeout_seconds)
                if await client.is_ready():
                    async with self._control_lock:
                        await self._check(instance_id, generation, {"provisioning"})
                        await self.db.set_many({"fish.url": url, "instance.phase": InstancePhase.READY.value,
                                                "instance.last_activity_at": datetime.now(UTC).isoformat()})
                        await self.db.event("instance.ready", {"instance_id": instance_id})
                    return
            now = time.monotonic()
            if progress and now - last_progress >= 10:
                await progress("provisioning")
                last_progress = now
            await asyncio.sleep(max(1.0, self.settings.provision_poll_seconds))
        raise RuntimeErrorState(f"Fish API did not become ready within {self.settings.fish_ready_timeout_seconds}s")

    async def synthesize(self, text: str, settings: TTSSettings, *, reference_audio: bytes | None = None,
                         reference_text: str | None = None) -> bytes:
        async with self._tts_lock:
            async with self._control_lock:
                values = await self.db.get_many(_IDENTITY_KEYS)
                instance_id = values.get("instance.id")
                generation = values.get("instance.generation")
                if not instance_id or values.get("instance.phase") != InstancePhase.READY.value:
                    raise RuntimeErrorState("Fish server is not ready")
                client = await self._current_fish()
                operation = secrets.token_hex(8)
                await self.db.set_many({"tts.active": True, "tts.operation": operation})
            try:
                return await client.synthesize(text, settings, reference_audio=reference_audio, reference_text=reference_text)
            finally:
                async with self._control_lock:
                    if await self.db.get("tts.operation") == operation:
                        await self.db.set_many({"tts.active": False, "tts.operation": None})
                    try:
                        await self._check(instance_id, generation)
                    except RuntimeErrorState:
                        pass
                    else:
                        await self._touch_activity()

    async def _current_fish(self) -> FishClient:
        values = await self.db.get_many(["fish.url", "fish.token"])
        if not values.get("fish.url") or not values.get("fish.token"):
            raise RuntimeErrorState("Fish endpoint is unavailable")
        return FishClient(str(values["fish.url"]), str(values["fish.token"]),
                          verify_tls=self.settings.fish_verify_tls,
                          timeout_seconds=self.settings.fish_request_timeout_seconds)

    async def clear_pending_locked(self) -> None:
        """Only after a definitive create rejection AND a complete empty lookup."""
        await self.db.set_many({**{key: None for key in _PENDING_KEYS}, "instance.phase": "none",
                                "instance.offer": None, "instance.generation": None,
                                "fish.token": None, "fish.url": None})

    async def adopt_pending_locked(self, instance_id: int, *, recovered: bool = True) -> Any:
        values = await self.db.get_many(_PENDING_KEYS + ["instance.offer", "instance.generation"])
        now = datetime.now(UTC)
        since = _date(values.get("instance.pending_since")) or now
        since = min(now, since)
        generation = values.get("instance.generation") or secrets.token_hex(12)
        offer = values.get("instance.offer") or {}
        price = offer.get("price_per_hour")
        if isinstance(price, (float, int)) and math.isfinite(price) and price > 0:
            # This is a conservative recovered estimate, not a provider invoice.
            await begin_billing(self.db, float(price), now=since, recovered=recovered)
        await self.db.set_many({"instance.id": instance_id, "instance.label": values.get("instance.pending_label"),
                                "instance.generation": generation, "instance.phase": "booting",
                                **{key: None for key in _PENDING_KEYS}})
        return generation

    async def reconcile_pending(self) -> dict[str, Any]:
        async with self._control_lock:
            values = await self.db.get_many(_PENDING_KEYS + ["instance.id"])
            label = values.get("instance.pending_label")
            if values.get("instance.id") or not label:
                return {"status": "not_pending", "instance_id": values.get("instance.id")}
            checked = datetime.now(UTC).isoformat()
            try:
                matches = await self.vast.find_instances_by_label(str(label))
            except Exception as exc:
                await self.db.set_many({"instance.pending_checked_at": checked,
                                        "instance.pending_status": "inventory_unavailable"})
                await self.db.event("instance.pending_recovery_failed", {"error_type": type(exc).__name__})
                return {"status": "inventory_unavailable"}
            if len(matches) == 1:
                instance_id = matches[0].instance_id
                generation = await self.adopt_pending_locked(instance_id)
                if matches[0].status.lower() == "stopped":
                    await pause_billing(self.db)
                    await self.db.set("instance.phase", "stopped")
                await self.db.event("instance.reconciled", {"instance_id": instance_id})
                return {"status": "recovered", "instance_id": instance_id, "generation": generation}
            if not matches and values.get("instance.pending_rejected") is True:
                await self.clear_pending_locked()
                await self.db.event("instance.pending_rejected_confirmed", {})
                return {"status": "rejected"}
            status = "multiple_matches" if matches else "awaiting_provider"
            await self.db.set_many({"instance.pending_checked_at": checked, "instance.pending_status": status})
            return {"status": status}

    async def recover_current(self, *, expected_instance_id: int | None = None, expected_generation: Any = _UNSET) -> None:
        async with self._recovery_lock:
            await self._recover_current(expected_instance_id=expected_instance_id, expected_generation=expected_generation)

    async def _recover_current(self, *, expected_instance_id: int | None, expected_generation: Any) -> None:
        if not await self.db.get("instance.id"):
            await self.reconcile_pending()
        async with self._control_lock:
            values = await self.db.get_many(_IDENTITY_KEYS)
            instance_id = values.get("instance.id")
            if not instance_id or expected_instance_id is not None and instance_id != expected_instance_id:
                return
            try:
                await self._check(instance_id, expected_generation)
            except RuntimeErrorState:
                return
            generation = values.get("instance.generation")
            phase = values.get("instance.phase")
        try:
            if phase == "destroying":
                # An owner-authorized destroy remains recoverable after restart.
                if not await self.vast.instance_exists(instance_id):
                    await asyncio.sleep(min(2.0, self.settings.provision_poll_seconds))
                    if not await self.vast.instance_exists(instance_id):
                        async with self._control_lock:
                            await self._check(instance_id, generation, {"destroying"})
                            await self._finish_destroy(instance_id)
                        return
                await self.destroy_current(expected_instance_id=instance_id, expected_generation=generation)
                return
            ref = await self.vast.show_instance(instance_id)
            status = ref.status.lower()
            async with self._control_lock:
                await self._check(instance_id, generation, {phase})
                if status in {"running", "frozen", "stopped"}:
                    await sync_billing_status(self.db, status)
                if phase == "stopping" and status == "stopped":
                    await self.db.set("instance.phase", "stopped")
                    return
                if phase == "stopped" and status in {"running", "frozen", "starting"}:
                    await self.db.set("instance.phase", "booting")
                    phase = "booting"
            if phase == "stopping":
                await self.stop_current(expected_instance_id=instance_id, expected_generation=generation)
                return
            if phase == "booting" and status not in {"running", "frozen"}:
                try:
                    await self._wait_until_running(instance_id, expected_generation=generation)
                except Exception:
                    latest = await self.vast.show_instance(instance_id)
                    async with self._control_lock:
                        await self._check(instance_id, generation, {"booting"})
                        if latest.status.lower() == "stopped":
                            await pause_billing(self.db)
                            await self.db.set("instance.phase", "stopped")
                            return
                    raise
                async with self._control_lock:
                    await self._check(instance_id, generation, {"booting"})
                    await resume_billing(self.db)
                status = "running"
            if status == "stopped" or status in {"exited", "error", "failed", "dead"}:
                async with self._control_lock:
                    await self._check(instance_id, generation, {phase})
                    await self.db.set("instance.phase", "stopped" if status == "stopped" else "error")
                return
            await self.wait_until_ready(instance_id, expected_generation=generation)
        except Exception as exc:
            await self.mark_failure(instance_id, generation, "instance.recovery_failed", exc)

    async def current_state(self, *, probe_fish: bool = False) -> dict[str, Any]:
        values = await self.db.get_many(_IDENTITY_KEYS + _PENDING_KEYS + ["instance.offer"])
        instance_id = values.get("instance.id")
        state: dict[str, Any] = {
            "instance_id": instance_id, "phase": values.get("instance.phase") or "none",
            "offer": values.get("instance.offer"), "pending": bool(values.get("instance.pending_label")),
            "pending_since": values.get("instance.pending_since"),
            "pending_status": values.get("instance.pending_status"),
            "pending_checked_at": values.get("instance.pending_checked_at"),
        }
        if not instance_id:
            return state
        ref = await self.vast.show_instance(instance_id)
        async with self._control_lock:
            await self._check(instance_id, values.get("instance.generation"), {state["phase"]})
            if ref.status.lower() in {"running", "frozen", "stopped"}:
                await sync_billing_status(self.db, ref.status)
            state.update({"vast_status": ref.status, "public_ip": ref.public_ip,
                          "mapped_port": ref.mapped_port, "billing": await billing_snapshot(self.db)})
        if probe_fish:
            try:
                state["fish_ready"] = await (await self._current_fish()).is_ready()
                await self._check(instance_id, values.get("instance.generation"), {state["phase"]})
            except Exception:
                state["fish_ready"] = False
        return state

    async def stop_current(self, *, expected_instance_id: int | None = None, expected_generation: Any = _UNSET) -> bool:
        async with self._control_lock:
            instance_id = await self.db.get("instance.id")
            if not instance_id:
                return False
            if expected_instance_id is not None and instance_id != expected_instance_id:
                raise RuntimeErrorState("Instance lifecycle changed")
            values = await self._check(instance_id, expected_generation)
            if values.get("instance.phase") == "destroying":
                return False
            if values.get("instance.phase") == "stopped":
                if (await self.vast.show_instance(instance_id)).status.lower() == "stopped":
                    return False
            await self.db.set_many({"instance.phase": "stopping", "instance.generation": secrets.token_hex(12),
                                    "instance.destroy_confirmation": None})
            await self.vast.stop_instance(instance_id)
            deadline = time.monotonic() + 120
            while (await self.vast.show_instance(instance_id)).status.lower() != "stopped":
                if time.monotonic() >= deadline:
                    raise RuntimeErrorState("Vast did not confirm the stop request within 120 seconds")
                await asyncio.sleep(min(2.0, self.settings.provision_poll_seconds))
            await pause_billing(self.db)
            await self.db.set("instance.phase", "stopped")
            await self.db.event("instance.stopped", {"instance_id": instance_id})
            return True

    async def start_current(self, progress: ProgressCallback | None = None) -> bool:
        async with self._control_lock:
            values = await self.db.get_many(_IDENTITY_KEYS)
            instance_id = values.get("instance.id")
            if not instance_id or values.get("instance.phase") in {"renting", "booting", "provisioning", "stopping", "destroying"}:
                return False
            ref = await self.vast.show_instance(instance_id)
            if values.get("instance.phase") == "ready" and ref.status.lower() != "stopped":
                return False
            if ref.status.lower() == "stopped":
                await pause_billing(self.db)
            if ref.status.lower() not in {"running", "frozen", "starting"}:
                await self.vast.start_instance(instance_id)
            generation = secrets.token_hex(12)
            await self.db.set_many({"instance.phase": "booting", "instance.generation": generation,
                                    "instance.destroy_confirmation": None})
        try:
            await self._wait_until_running(instance_id, expected_generation=generation)
            async with self._control_lock:
                await self._check(instance_id, generation, {"booting"})
                await resume_billing(self.db)
            await self.wait_until_ready(instance_id, progress=progress, expected_generation=generation)
        except Exception as exc:
            await self.mark_failure(instance_id, generation, "instance.start_failed", exc)
            raise
        return True

    async def _wait_until_running(self, instance_id: int, *, expected_generation: Any = _UNSET) -> None:
        deadline = time.monotonic() + 300
        while True:
            await self._check(instance_id, expected_generation, {"booting"})
            ref = await self.vast.show_instance(instance_id)
            await self._check(instance_id, expected_generation, {"booting"})
            if ref.status.lower() in {"running", "frozen"}:
                return
            if ref.status.lower() in {"error", "failed", "dead"}:
                raise RuntimeErrorState("Vast instance entered a terminal state")
            if time.monotonic() >= deadline:
                raise RuntimeErrorState("Vast did not confirm start within 300 seconds")
            await asyncio.sleep(min(2.0, self.settings.provision_poll_seconds))

    async def prepare_destroy_confirmation(self) -> dict[str, Any]:
        async with self._control_lock:
            values = await self.db.get_many(_IDENTITY_KEYS)
            if not values.get("instance.id"):
                raise RuntimeErrorState("There is no current instance")
            confirmation = {"instance_id": values["instance.id"], "generation": values.get("instance.generation"),
                            "nonce": secrets.token_hex(8),
                            "expires_at": (datetime.now(UTC) + timedelta(seconds=self.settings.destroy_confirmation_seconds)).isoformat()}
            await self.db.set("instance.destroy_confirmation", confirmation)
            return {**confirmation, "billing": await billing_snapshot(self.db)}

    async def destroy_current(self, *, expected_instance_id: int | None = None,
                              expected_generation: Any = _UNSET, confirmation_nonce: str | None = None,
                              expected_idle_since: str | None = None) -> bool:
        async with self._control_lock:
            instance_id = await self.db.get("instance.id")
            if not instance_id:
                return False
            if expected_instance_id is not None and instance_id != expected_instance_id:
                raise StaleConfirmation("Instance lifecycle changed; request a new confirmation")
            values = await self._check(instance_id, expected_generation)
            if confirmation_nonce is not None:
                saved = await self.db.get("instance.destroy_confirmation")
                if (not isinstance(saved, dict) or saved.get("instance_id") != instance_id
                        or saved.get("generation") != values.get("instance.generation")
                        or not secrets.compare_digest(str(saved.get("nonce", "")), confirmation_nonce)
                        or (_date(saved.get("expires_at")) or datetime.min.replace(tzinfo=UTC)) <= datetime.now(UTC)):
                    raise StaleConfirmation("Confirmation expired or no longer matches this instance")
                await self.db.set("instance.destroy_confirmation", None)
            if expected_idle_since is not None:
                idle = await self.db.get_many(["instance.last_activity_at", "tts.active"])
                if (values.get("instance.phase") != "ready" or idle.get("tts.active")
                        or idle.get("instance.last_activity_at") != expected_idle_since):
                    return False
            await self.db.set_many({"instance.phase": "destroying", "instance.generation": secrets.token_hex(12),
                                    "instance.destroy_confirmation": None})
            await self.vast.destroy_instance(instance_id)
            deadline = time.monotonic() + 120
            absent_checks = 0
            while absent_checks < 2:
                absent_checks = 0 if await self.vast.instance_exists(instance_id) else absent_checks + 1
                if absent_checks >= 2:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeErrorState("Vast did not confirm instance deletion within 120 seconds")
                await asyncio.sleep(min(2.0, self.settings.provision_poll_seconds))
            await self._finish_destroy(instance_id)
            return True

    async def _finish_destroy(self, instance_id: int) -> None:
        await self._check(instance_id, phases={"destroying"})
        billing = await finalize_billing(self.db)
        await self.db.event("instance.destroyed", {"instance_id": instance_id, "billing": billing})
        await self.db.set_many({"instance.id": None, "instance.phase": "none", "instance.generation": None,
                                "instance.offer": None, "instance.label": None, "instance.destroy_confirmation": None,
                                **{key: None for key in _PENDING_KEYS}, "fish.url": None, "fish.token": None,
                                "instance.last_activity_at": None, "tts.active": False, "tts.operation": None})

    async def last_billing_snapshot(self) -> dict[str, Any] | None:
        return await last_billing_snapshot(self.db)

    async def _touch_activity(self) -> None:
        await self.db.set("instance.last_activity_at", datetime.now(UTC).isoformat())
