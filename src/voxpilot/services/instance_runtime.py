from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import InstancePhase, TTSSettings
from voxpilot.services.billing import (
    billing_snapshot,
    finalize_billing,
    last_billing_snapshot,
    pause_billing,
    resume_billing,
    sync_billing_status,
)
from voxpilot.services.fish_client import FishClient
from voxpilot.services.provisioning import fish_url
from voxpilot.services.vast_gateway import VastSdkGateway


ProgressCallback = Callable[[str], Awaitable[None]]


class RuntimeErrorState(RuntimeError):
    pass


class InstanceRuntime:
    def __init__(self, settings: Settings, db: Database, vast: VastSdkGateway):
        self.settings = settings
        self.db = db
        self.vast = vast
        self._control_lock = asyncio.Lock()
        self._tts_lock = asyncio.Lock()

    async def wait_until_ready(self, instance_id: int, progress: ProgressCallback | None = None) -> None:
        await self.db.set("instance.phase", InstancePhase.PROVISIONING.value)
        deadline = time.monotonic() + self.settings.fish_ready_timeout_seconds
        last_progress = 0.0
        while time.monotonic() < deadline:
            current = await self.db.get("instance.id")
            if not current or int(current) != int(instance_id):
                raise RuntimeErrorState("Instance changed while provisioning")
            ref = await self.vast.show_instance(instance_id)
            status = ref.status.lower()
            if status in {"exited", "error", "failed", "dead"}:
                raise RuntimeErrorState(f"Vast instance entered terminal state: {ref.status}")
            if status == "stopped":
                await pause_billing(self.db)
                await self.db.set("instance.phase", InstancePhase.STOPPED.value)
                raise RuntimeErrorState("Vast instance stopped before Fish became ready")
            if status in {"running", "frozen"}:
                await sync_billing_status(self.db, status)
            if ref.public_ip and ref.mapped_port:
                url = fish_url(self.settings, ref.public_ip, ref.mapped_port)
                token = str(await self.db.get("fish.token") or "")
                if token:
                    client = FishClient(
                        url,
                        token,
                        verify_tls=self.settings.fish_verify_tls,
                        timeout_seconds=self.settings.fish_request_timeout_seconds,
                    )
                    if await client.is_ready():
                        await self.db.set_many(
                            {
                                "fish.url": url,
                                "instance.phase": InstancePhase.READY.value,
                                "instance.last_activity_at": datetime.now(UTC).isoformat(),
                            }
                        )
                        await self.db.event("instance.ready", {"instance_id": instance_id})
                        return
            now = time.monotonic()
            if progress and now - last_progress >= 10:
                await progress("provisioning")
                last_progress = now
            await asyncio.sleep(max(1.0, self.settings.provision_poll_seconds))
        raise RuntimeErrorState(f"Fish API did not become ready within {self.settings.fish_ready_timeout_seconds}s")

    async def synthesize(
        self,
        text: str,
        settings: TTSSettings,
        *,
        reference_audio: bytes | None = None,
        reference_text: str | None = None,
    ) -> bytes:
        async with self._tts_lock:
            phase = await self.db.get("instance.phase", InstancePhase.NONE.value)
            if phase != InstancePhase.READY.value:
                raise RuntimeErrorState("Fish server is not ready")
            client = await self._current_fish()
            await self.db.set("tts.active", True)
            try:
                return await client.synthesize(
                    text,
                    settings,
                    reference_audio=reference_audio,
                    reference_text=reference_text,
                )
            finally:
                await self.db.set("tts.active", False)
                await self._touch_activity()

    async def _current_fish(self) -> FishClient:
        values = await self.db.get_many(["fish.url", "fish.token"])
        url = values.get("fish.url")
        token = values.get("fish.token")
        if not url or not token:
            raise RuntimeErrorState("Fish endpoint is unavailable")
        return FishClient(
            str(url),
            str(token),
            verify_tls=self.settings.fish_verify_tls,
            timeout_seconds=self.settings.fish_request_timeout_seconds,
        )

    async def recover_current(self) -> None:
        await self.db.set("tts.active", False)
        instance_id = await self.db.get("instance.id")
        if not instance_id:
            pending_label = await self.db.get("instance.pending_label")
            if not pending_label:
                return
            try:
                matches = await self.vast.find_instances_by_label(str(pending_label))
            except Exception as exc:
                await self.db.event("instance.pending_recovery_failed", {"label": pending_label, "error": str(exc)})
                return
            if len(matches) != 1:
                await self.db.event("instance.pending_recovery_unresolved", {"label": pending_label, "count": len(matches)})
                return
            instance_id = matches[0].instance_id
            await self.db.set_many(
                {
                    "instance.id": instance_id,
                    "instance.label": pending_label,
                    "instance.pending_label": None,
                    "instance.phase": InstancePhase.BOOTING.value,
                }
            )

        try:
            ref = await self.vast.show_instance(int(instance_id))
        except Exception as exc:
            await self.db.event("instance.recovery_probe_failed", {"instance_id": instance_id, "error": str(exc)})
            return
        status = ref.status.lower()
        if status in {"running", "frozen", "stopped"}:
            await sync_billing_status(self.db, status)
        if status == "stopped":
            await self.db.set("instance.phase", InstancePhase.STOPPED.value)
            return
        if status in {"exited", "error", "failed", "dead"}:
            await self.db.set("instance.phase", InstancePhase.ERROR.value)
            return
        try:
            await self.wait_until_ready(int(instance_id))
        except Exception as exc:
            await self.db.set("instance.phase", InstancePhase.ERROR.value)
            await self.db.event("instance.recovery_failed", {"instance_id": instance_id, "error": str(exc)})

    async def current_state(self, *, probe_fish: bool = False) -> dict[str, Any]:
        values = await self.db.get_many(["instance.id", "instance.phase", "instance.offer"])
        instance_id = values.get("instance.id")
        state: dict[str, Any] = {
            "instance_id": instance_id,
            "phase": values.get("instance.phase", InstancePhase.NONE.value),
            "offer": values.get("instance.offer"),
        }
        if not instance_id:
            return state
        ref = await self.vast.show_instance(int(instance_id))
        if ref.status.lower() in {"running", "frozen", "stopped"}:
            await sync_billing_status(self.db, ref.status)
        state.update(
            {
                "vast_status": ref.status,
                "public_ip": ref.public_ip,
                "mapped_port": ref.mapped_port,
                "billing": await billing_snapshot(self.db),
            }
        )
        if probe_fish:
            try:
                state["fish_ready"] = await (await self._current_fish()).is_ready()
            except Exception:
                state["fish_ready"] = False
        return state

    async def stop_current(self) -> bool:
        async with self._control_lock:
            instance_id = await self.db.get("instance.id")
            if not instance_id:
                return False
            await self.db.set("instance.phase", InstancePhase.STOPPING.value)
            await self.vast.stop_instance(int(instance_id))
            await pause_billing(self.db)
            await self.db.set("instance.phase", InstancePhase.STOPPED.value)
            await self.db.event("instance.stopped", {"instance_id": instance_id})
            return True

    async def start_current(self, progress: ProgressCallback | None = None) -> bool:
        async with self._control_lock:
            instance_id = await self.db.get("instance.id")
            if not instance_id:
                return False
            await self.vast.start_instance(int(instance_id))
            await resume_billing(self.db)
            await self.db.set("instance.phase", InstancePhase.BOOTING.value)
        await self.wait_until_ready(int(instance_id), progress=progress)
        return True

    async def destroy_current(self) -> bool:
        async with self._control_lock:
            instance_id = await self.db.get("instance.id")
            if not instance_id:
                return False
            await self.db.set("instance.phase", InstancePhase.DESTROYING.value)
            await self.vast.destroy_instance(int(instance_id))
            billing = await finalize_billing(self.db)
            await self.db.event("instance.destroyed", {"instance_id": instance_id, "billing": billing})
            await self.db.set_many(
                {
                    "instance.id": None,
                    "instance.phase": InstancePhase.NONE.value,
                    "instance.offer": None,
                    "instance.label": None,
                    "instance.pending_label": None,
                    "fish.url": None,
                    "fish.token": None,
                    "instance.last_activity_at": None,
                    "tts.active": False,
                }
            )
            return True

    async def last_billing_snapshot(self) -> dict[str, Any] | None:
        return await last_billing_snapshot(self.db)

    async def _touch_activity(self) -> None:
        await self.db.set("instance.last_activity_at", datetime.now(UTC).isoformat())
