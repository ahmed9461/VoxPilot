import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import InstancePhase, InstanceRef
from voxpilot.services.billing import begin_billing, billing_snapshot, pause_billing
from voxpilot.services.instance_runtime import InstanceRuntime, RuntimeErrorState


class FakeVast:
    def __init__(self):
        self.stop_calls = 0
        self.start_calls = 0
        self.destroy_calls = 0
        self.probe_started = asyncio.Event()
        self.allow_stop = asyncio.Event()
        self.inventory_checked = asyncio.Event()
        self.allow_delete = asyncio.Event()
        self.running = False

    async def stop_instance(self, instance_id):
        self.stop_calls += 1

    async def start_instance(self, instance_id):
        self.start_calls += 1

    async def destroy_instance(self, instance_id):
        self.destroy_calls += 1

    async def instance_exists(self, instance_id):
        self.inventory_checked.set()
        await self.allow_delete.wait()
        return False

    async def show_instance(self, instance_id):
        self.probe_started.set()
        if self.running:
            return InstanceRef(instance_id, "running")
        await self.allow_stop.wait()
        return InstanceRef(instance_id, "stopped")


@pytest.mark.asyncio
async def test_stop_keeps_billing_active_until_vast_confirms(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.READY.value})
    await begin_billing(db, 0.2, now=datetime.now(UTC) - timedelta(minutes=1))
    vast = FakeVast()
    runtime = InstanceRuntime(Settings(provision_poll_seconds=0.01), db, vast)

    stopping = asyncio.create_task(runtime.stop_current())
    await vast.probe_started.wait()
    assert (await billing_snapshot(db))["active"] is True
    assert await db.get("instance.phase") == InstancePhase.STOPPING.value

    vast.allow_stop.set()
    assert await stopping is True
    assert (await billing_snapshot(db))["active"] is False
    assert await db.get("instance.phase") == InstancePhase.STOPPED.value
    assert await runtime.stop_current() is False
    assert vast.stop_calls == 1


@pytest.mark.asyncio
async def test_recovery_recognizes_stopped_rental_and_pauses_meter(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.ERROR.value})
    await begin_billing(db, 0.2)
    vast = FakeVast()
    vast.allow_stop.set()
    runtime = InstanceRuntime(Settings(), db, vast)

    await runtime.recover_current()

    assert await db.get("instance.phase") == InstancePhase.STOPPED.value
    assert (await billing_snapshot(db))["active"] is False


@pytest.mark.asyncio
async def test_recovery_preserves_pending_stop_until_provider_confirms(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.STOPPING.value})
    await begin_billing(db, 0.2)
    vast = FakeVast()
    vast.running = True
    runtime = InstanceRuntime(Settings(provision_poll_seconds=0.01), db, vast)

    recovering = asyncio.create_task(runtime.recover_current())
    await vast.probe_started.wait()
    await asyncio.sleep(0)
    assert await db.get("instance.phase") == InstancePhase.STOPPING.value
    assert (await billing_snapshot(db))["active"] is True

    vast.running = False
    vast.allow_stop.set()
    await recovering
    assert await db.get("instance.phase") == InstancePhase.STOPPED.value
    assert (await billing_snapshot(db))["active"] is False
    assert vast.stop_calls == 1


@pytest.mark.asyncio
async def test_recovery_waits_for_pending_boot_instead_of_marking_it_stopped(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.BOOTING.value})
    await begin_billing(db, 0.2)

    class DelayedVast(FakeVast):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def show_instance(self, instance_id):
            self.calls += 1
            return InstanceRef(instance_id, "stopped" if self.calls < 3 else "running")

    vast = DelayedVast()
    runtime = InstanceRuntime(Settings(provision_poll_seconds=0.01), db, vast)

    async def ready(instance_id, progress=None):
        await db.set("instance.phase", InstancePhase.READY.value)

    runtime.wait_until_ready = ready
    await runtime.recover_current()

    assert vast.calls >= 3
    assert await db.get("instance.phase") == InstancePhase.READY.value
    assert (await billing_snapshot(db))["active"] is True


@pytest.mark.asyncio
async def test_recovery_moves_stopped_record_back_to_booting_when_provider_is_running(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.STOPPED.value})
    await begin_billing(db, 0.2)
    await pause_billing(db)
    vast = FakeVast()
    vast.running = True
    runtime = InstanceRuntime(Settings(), db, vast)

    async def ready(instance_id, progress=None):
        assert await db.get("instance.phase") == InstancePhase.BOOTING.value
        await db.set("instance.phase", InstancePhase.READY.value)

    runtime.wait_until_ready = ready
    await runtime.recover_current()

    assert await db.get("instance.phase") == InstancePhase.READY.value
    assert (await billing_snapshot(db))["active"] is True


@pytest.mark.asyncio
async def test_recovery_waits_through_provider_start_transition(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.STOPPED.value})
    await begin_billing(db, 0.2)
    await pause_billing(db)

    class StartingVast(FakeVast):
        def __init__(self):
            super().__init__()
            self.calls = 0

        async def show_instance(self, instance_id):
            self.calls += 1
            return InstanceRef(instance_id, "starting" if self.calls < 3 else "running")

    vast = StartingVast()
    runtime = InstanceRuntime(Settings(provision_poll_seconds=0.01), db, vast)

    async def ready(instance_id, progress=None):
        await db.set("instance.phase", InstancePhase.READY.value)

    runtime.wait_until_ready = ready
    await runtime.recover_current()

    assert vast.calls >= 3
    assert await db.get("instance.phase") == InstancePhase.READY.value
    assert (await billing_snapshot(db))["active"] is True


@pytest.mark.asyncio
async def test_repeated_start_does_not_send_second_vast_request(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.STOPPED.value})
    vast = FakeVast()
    vast.running = True
    runtime = InstanceRuntime(Settings(), db, vast)
    entered_wait = asyncio.Event()
    finish_wait = asyncio.Event()

    async def wait_until_ready(instance_id, progress=None):
        entered_wait.set()
        await finish_wait.wait()

    runtime.wait_until_ready = wait_until_ready
    starting = asyncio.create_task(runtime.start_current())
    await entered_wait.wait()
    assert await runtime.start_current() is False
    finish_wait.set()
    assert await starting is True
    assert vast.start_calls == 0


@pytest.mark.asyncio
async def test_start_does_not_reverse_a_pending_stop(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.STOPPING.value})
    vast = FakeVast()
    runtime = InstanceRuntime(Settings(), db, vast)

    assert await runtime.start_current() is False
    assert vast.start_calls == 0
    assert await db.get("instance.phase") == InstancePhase.STOPPING.value


@pytest.mark.asyncio
async def test_rejected_start_keeps_stopped_phase_and_paused_meter(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.STOPPED.value})
    await begin_billing(db, 0.2)
    await pause_billing(db)

    class RejectingVast(FakeVast):
        async def start_instance(self, instance_id):
            raise RuntimeError("provider rejected start")

        async def show_instance(self, instance_id):
            return InstanceRef(instance_id, "stopped")

    runtime = InstanceRuntime(Settings(), db, RejectingVast())
    with pytest.raises(RuntimeError, match="rejected"):
        await runtime.start_current()

    assert await db.get("instance.phase") == InstancePhase.STOPPED.value
    assert (await billing_snapshot(db))["active"] is False


@pytest.mark.asyncio
async def test_start_waits_for_provider_before_resuming_meter(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.STOPPED.value})
    await begin_billing(db, 0.2)
    await pause_billing(db)
    vast = FakeVast()
    runtime = InstanceRuntime(Settings(provision_poll_seconds=0.01), db, vast)

    async def ready(instance_id, progress=None):
        await db.set("instance.phase", InstancePhase.READY.value)

    runtime.wait_until_ready = ready
    starting = asyncio.create_task(runtime.start_current())
    await vast.probe_started.wait()
    assert (await billing_snapshot(db))["active"] is False

    vast.running = True
    vast.allow_stop.set()
    assert await starting is True
    assert (await billing_snapshot(db))["active"] is True
    assert vast.start_calls == 1


@pytest.mark.asyncio
async def test_destroy_retains_state_and_meter_until_inventory_confirms_absence(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.READY.value})
    await begin_billing(db, 0.2)
    vast = FakeVast()
    runtime = InstanceRuntime(Settings(provision_poll_seconds=0.01), db, vast)

    destroying = asyncio.create_task(runtime.destroy_current())
    await vast.inventory_checked.wait()
    assert await db.get("instance.id") == 123
    assert await db.get("instance.phase") == InstancePhase.DESTROYING.value
    assert (await billing_snapshot(db))["active"] is True

    vast.allow_delete.set()
    assert await destroying is True
    assert await db.get("instance.id") is None
    assert await db.get("instance.phase") == InstancePhase.NONE.value
    assert await db.get("billing.last") is not None
    assert vast.destroy_calls == 1


@pytest.mark.asyncio
async def test_failed_start_leaves_retryable_error_phase(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.STOPPED.value})
    vast = FakeVast()
    vast.running = True
    runtime = InstanceRuntime(Settings(), db, vast)

    async def fail_readiness(instance_id, progress=None):
        await db.set("instance.phase", InstancePhase.PROVISIONING.value)
        raise RuntimeErrorState("Fish did not become ready")

    runtime.wait_until_ready = fail_readiness
    with pytest.raises(RuntimeErrorState):
        await runtime.start_current()

    assert await db.get("instance.phase") == InstancePhase.ERROR.value
    assert vast.start_calls == 0


@pytest.mark.asyncio
async def test_readiness_cannot_overwrite_a_concurrent_stop(tmp_path, monkeypatch):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await db.set_many({"instance.id": 123, "instance.phase": InstancePhase.BOOTING.value, "fish.token": "test"})
    await begin_billing(db, 0.2)
    health_started = asyncio.Event()
    finish_health = asyncio.Event()

    class FakeFish:
        def __init__(self, *args, **kwargs):
            pass

        async def is_ready(self):
            health_started.set()
            await finish_health.wait()
            return True

    class ConcurrentVast(FakeVast):
        def __init__(self):
            super().__init__()
            self.running = True

        async def stop_instance(self, instance_id):
            self.stop_calls += 1
            self.running = False
            self.allow_stop.set()

        async def show_instance(self, instance_id):
            if self.running:
                return InstanceRef(instance_id, "running", "127.0.0.1", 8080)
            return InstanceRef(instance_id, "stopped")

    monkeypatch.setattr("voxpilot.services.instance_runtime.FishClient", FakeFish)
    runtime = InstanceRuntime(Settings(), db, ConcurrentVast())
    readiness = asyncio.create_task(runtime.wait_until_ready(123))
    await health_started.wait()

    assert await runtime.stop_current() is True
    finish_health.set()
    with pytest.raises(RuntimeErrorState, match="lifecycle changed"):
        await readiness
    assert await db.get("instance.phase") == InstancePhase.STOPPED.value
    assert (await billing_snapshot(db))["active"] is False
