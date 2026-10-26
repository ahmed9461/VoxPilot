"""Regression tests for the 2026-10-27 audit; no provider/network/real audio."""

import asyncio
import sqlite3
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from voxpilot.bot.keyboards import destroy_confirm_keyboard
from voxpilot.bot.routers import home, servers, voices
from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import GpuOffer, InstanceRef
from voxpilot.services.billing import begin_billing, billing_snapshot, finalize_billing, pause_billing, resume_billing
from voxpilot.services.cost_guard import _tick
from voxpilot.services.instance_runtime import InstanceRuntime, RuntimeErrorState, StaleConfirmation
from voxpilot.services.orchestrator import Orchestrator, OrchestratorError, OfferUnavailableError
from voxpilot.services.vast_gateway import VastError, VastOfferUnavailableError, VastSdkGateway
from voxpilot.services.vast_models import normalize_offer


@pytest.fixture
async def db(tmp_path):
    value = Database(tmp_path / "state.sqlite3")
    await value.init()
    return value


def offer(oid=1, down=2000.0, price=0.2, up=100.0):
    return GpuOffer(
        oid, "RTX 3090", 24, price, 0.99, 10, inet_down_mbps=down, inet_up_mbps=up, disk_space_gb=100, verified=True
    )


class Provider:
    def __init__(self):
        self.rows = [offer()]
        self.matches = []
        self.create_error = None
        self.inventory_error = None
        self.created = 0
        self.deleted = []
        self.queries = []
        self.status = "stopped"

    async def search_offers(self, query, limit, storage_gb):
        self.queries.append(query)
        return self.rows

    async def find_offer(self, offer_id, *, policy_query, storage_gb):
        self.queries.append(policy_query)
        return next((item for item in self.rows if item.offer_id == offer_id), None)

    async def create_instance(self, *args, **kwargs):
        self.created += 1
        if self.create_error:
            raise self.create_error
        return {"new_contract": 123}

    async def find_instances_by_label(self, label):
        if self.inventory_error:
            raise self.inventory_error
        return self.matches

    async def show_instance(self, instance_id):
        return InstanceRef(instance_id, self.status)

    async def destroy_instance(self, instance_id):
        self.deleted.append(instance_id)

    async def instance_exists(self, instance_id):
        return False


@pytest.mark.asyncio
async def test_atomic_pause_across_independent_connections(db):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    await begin_billing(db, 0.3, now=start)
    peers = [Database(db.path) for _ in range(32)]
    await asyncio.gather(*(pause_billing(peer, now=start + timedelta(seconds=120)) for peer in peers))
    snapshot = await billing_snapshot(db, now=start + timedelta(seconds=120))
    assert snapshot["active_seconds"] == 120
    assert snapshot["estimated_cost_usd"] == pytest.approx(0.01)


@pytest.mark.asyncio
async def test_atomic_resume_finalize_and_snapshot_are_idempotent(db):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    await begin_billing(db, 0.3, now=start)
    await pause_billing(db, now=start + timedelta(seconds=120))
    await asyncio.gather(*(resume_billing(Database(db.path), now=start + timedelta(seconds=180)) for _ in range(12)))
    results = await asyncio.gather(
        *(finalize_billing(Database(db.path), now=start + timedelta(seconds=240)) for _ in range(12))
    )
    assert sum(item is not None for item in results) == 1
    assert (await db.get("billing.last"))["active_seconds"] == 180
    await resume_billing(db)
    assert await billing_snapshot(db) is None
    assert await db.get("billing.active_since") is None


@pytest.mark.asyncio
async def test_transaction_failure_rolls_back_and_connections_close(db, monkeypatch):
    connections = []

    def connect():
        connection = sqlite3.connect(db.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connections.append(connection)
        return connection

    monkeypatch.setattr(db, "_connect", connect)
    await db.set("kept", 1)

    def fail(values):
        raise ValueError("synthetic failure")

    with pytest.raises(ValueError):
        await db.transaction(["kept"], fail)
    assert await db.get("kept") == 1
    for connection in connections:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


@pytest.mark.asyncio
@pytest.mark.parametrize("current_id,phase", [(None, "none"), (456, "ready"), (123, "stopped")])
async def test_stale_readiness_does_not_mutate_state(db, current_id, phase):
    await db.set_many({"instance.id": current_id, "instance.phase": phase, "fish.token": "synthetic"})
    runtime = InstanceRuntime(Settings(), db, Provider())
    with pytest.raises(RuntimeErrorState):
        await runtime.wait_until_ready(123)
    assert await db.get("instance.id") == current_id
    assert await db.get("instance.phase") == phase


@pytest.mark.asyncio
async def test_health_from_previous_generation_cannot_revive_same_id(db, monkeypatch):
    await db.set_many(
        {"instance.id": 123, "instance.phase": "booting", "instance.generation": "old", "fish.token": "test"}
    )
    started, release = asyncio.Event(), asyncio.Event()

    class Fish:
        def __init__(self, *args, **kwargs):
            pass

        async def is_ready(self):
            started.set()
            await release.wait()
            return True

    class Vast(Provider):
        async def show_instance(self, instance_id):
            return InstanceRef(instance_id, "running", "127.0.0.1", 8080)

    monkeypatch.setattr("voxpilot.services.instance_runtime.FishClient", Fish)
    runtime = InstanceRuntime(Settings(), db, Vast())
    task = asyncio.create_task(runtime.wait_until_ready(123, expected_generation="old"))
    await asyncio.wait_for(started.wait(), 2)
    async with runtime.control_lock:
        await db.set_many({"instance.phase": "booting", "instance.generation": "new"})
    release.set()
    with pytest.raises(RuntimeErrorState):
        await task
    assert await db.get("instance.phase") == "booting"
    assert await db.get("fish.url") is None


@pytest.mark.asyncio
async def test_stale_status_response_cannot_pause_new_meter(db):
    started, release = asyncio.Event(), asyncio.Event()

    class Vast(Provider):
        async def show_instance(self, instance_id):
            started.set()
            await release.wait()
            return InstanceRef(instance_id, "stopped")

    runtime = InstanceRuntime(Settings(), db, Vast())
    await db.set_many({"instance.id": 123, "instance.phase": "ready", "instance.generation": "old"})
    await begin_billing(db, 0.2)
    task = asyncio.create_task(runtime.current_state())
    await asyncio.wait_for(started.wait(), 2)
    async with runtime.control_lock:
        await finalize_billing(db)
        await db.set_many({"instance.id": 456, "instance.phase": "ready", "instance.generation": "new"})
        await begin_billing(db, 0.3)
    release.set()
    with pytest.raises(RuntimeErrorState):
        await task
    assert (await billing_snapshot(db))["active"] is True
    assert (await billing_snapshot(db))["price_per_hour"] == 0.3


@pytest.mark.asyncio
async def test_pending_timeout_recovers_later_without_second_create(db):
    vast = Provider()
    vast.create_error = VastError("synthetic timeout")
    orch = Orchestrator(Settings(), db, vast)
    await orch.offers()
    with pytest.raises(OrchestratorError):
        await orch.rent(1)
    assert (await orch.current_state())["pending"] is True
    old = datetime.now(UTC) - timedelta(minutes=4)
    await db.set("instance.pending_since", old.isoformat())
    assert (await orch.reconcile_pending(prepare=False))["status"] == "awaiting_provider"
    with pytest.raises(OrchestratorError):
        await orch.rent(1)
    vast.matches = [InstanceRef(123, "stopped")]
    result = await orch.reconcile_pending(prepare=False)
    assert result["status"] == "recovered"
    assert await db.get("instance.id") == 123
    assert not await db.get("instance.pending_label")
    bill = await billing_snapshot(db)
    assert bill["active_seconds"] >= 240 and bill["recovered_estimate"] is True
    await orch.recover_current()
    assert await db.get("instance.phase") == "stopped"
    assert vast.created == 1


@pytest.mark.asyncio
async def test_definitive_rejection_survives_inventory_failure_and_restart(db):
    vast = Provider()
    vast.create_error = VastOfferUnavailableError("no_such_ask")
    vast.inventory_error = VastError("temporary")
    first = Orchestrator(Settings(), db, vast)
    await first.offers()
    with pytest.raises(OrchestratorError):
        await first.rent(1)
    assert await db.get("instance.pending_rejected") is True
    restarted = Orchestrator(Settings(), Database(db.path), vast)
    vast.inventory_error = None
    assert (await restarted.reconcile_pending(prepare=False))["status"] == "rejected"
    assert await db.get("instance.pending_label") is None
    assert await db.get("fish.token") is None
    assert vast.created == 1


@pytest.mark.asyncio
async def test_multiple_pending_matches_never_pick_or_clear(db):
    await db.set_many({"instance.pending_label": "VoxPilot-synthetic", "instance.phase": "error"})
    vast = Provider()
    vast.matches = [InstanceRef(123, "running"), InstanceRef(124, "running")]
    runtime = InstanceRuntime(Settings(), db, vast)
    assert (await runtime.reconcile_pending())["status"] == "multiple_matches"
    assert await db.get("instance.id") is None
    assert await db.get("instance.pending_label")
    assert vast.created == 0


@pytest.mark.asyncio
async def test_pending_cost_guard_warns_once_and_keeps_guard(db):
    await db.set_many(
        {
            "instance.pending_label": "VoxPilot-synthetic",
            "instance.phase": "error",
            "instance.pending_since": (datetime.now(UTC) - timedelta(minutes=3)).isoformat(),
        }
    )
    vast = Provider()
    settings = Settings(pending_rental_warn_seconds=120)
    orch = Orchestrator(settings, db, vast)
    messages = []

    class Bot:
        async def send_message(self, owner, text):
            messages.append(text)

    await _tick(Bot(), settings, db, orch)
    await _tick(Bot(), settings, db, orch)
    assert len(messages) == 1 and "غير محسوم" in messages[0]
    assert await db.get("instance.pending_label")
    assert vast.created == 0


@pytest.mark.asyncio
async def test_destroy_confirmation_rejects_new_resource_and_old_generation(db):
    vast = Provider()
    runtime = InstanceRuntime(Settings(), db, vast)
    await db.set_many({"instance.id": 123, "instance.phase": "ready", "instance.generation": "old"})
    confirmation = await runtime.prepare_destroy_confirmation()
    await db.set_many({"instance.id": 456, "instance.generation": "new"})
    with pytest.raises(StaleConfirmation):
        await runtime.destroy_current(expected_instance_id=123, confirmation_nonce=confirmation["nonce"])
    await db.set("instance.id", 123)
    with pytest.raises(StaleConfirmation):
        await runtime.destroy_current(expected_instance_id=123, confirmation_nonce=confirmation["nonce"])
    assert vast.deleted == []


@pytest.mark.asyncio
async def test_destroy_confirmation_expiry_single_use_and_callback_size(db):
    vast = Provider()
    runtime = InstanceRuntime(Settings(provision_poll_seconds=0.01), db, vast)
    await db.set_many({"instance.id": 123, "instance.phase": "ready"})
    confirmation = await runtime.prepare_destroy_confirmation()
    expired = {**confirmation, "expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()}
    await db.set("instance.destroy_confirmation", expired)
    with pytest.raises(StaleConfirmation):
        await runtime.destroy_current(expected_instance_id=123, confirmation_nonce=confirmation["nonce"])
    confirmation = await runtime.prepare_destroy_confirmation()
    markup = destroy_confirm_keyboard(123, confirmation["nonce"])
    assert len(markup.inline_keyboard[0][0].callback_data.encode()) <= 64
    results = await asyncio.gather(
        *(runtime.destroy_current(expected_instance_id=123, confirmation_nonce=confirmation["nonce"]) for _ in range(2))
    )
    assert sorted(results) == [False, True]
    assert vast.deleted == [123]


@pytest.mark.asyncio
async def test_idle_destroy_rechecks_recent_activity_and_active_tts(db):
    vast = Provider()
    runtime = InstanceRuntime(Settings(), db, vast)
    await db.set_many({"instance.id": 123, "instance.phase": "ready", "instance.last_activity_at": "new"})
    assert not await runtime.destroy_current(expected_instance_id=123, expected_idle_since="old")
    await db.set("tts.active", True)
    assert not await runtime.destroy_current(expected_instance_id=123, expected_idle_since="new")
    assert vast.deleted == []


@pytest.mark.asyncio
async def test_network_first_ranking_preserves_price_cap_and_upload_policy(db):
    vast = Provider()
    vast.rows = [
        offer(1, 180, 0.1),
        offer(2, 1200, 0.25),
        offer(3, 5200, 0.3),
        offer(4, 10000, 0.51),
        offer(5, 9000, 0.2, up=10),
    ]
    orch = Orchestrator(Settings(vast_min_inet_down_mbps=100), db, vast)
    assert [row.offer_id for row in await orch.offers()] == [3, 2, 1]
    assert "inet_up>=50" in vast.queries[0]
    assert "dph_total<=0.5000" in vast.queries[0]


@pytest.mark.asyncio
async def test_slow_fallback_is_explicit_and_click_time_revalidated(db):
    vast = Provider()
    vast.rows = [offer(1, 180, 0.15)]
    orch = Orchestrator(Settings(), db, vast)
    assert await orch.offers() == []
    displayed = await orch.offers(allow_slow=True)
    assert displayed[0].network_fallback
    assert "inet_down>=100" in vast.queries[-1]
    await orch.rent(1)
    assert "inet_down>=100" in vast.queries[-1]
    assert vast.created == 1


@pytest.mark.asyncio
async def test_network_change_between_click_and_create_rejects(db):
    vast = Provider()
    orch = Orchestrator(Settings(), db, vast)
    await orch.offers()
    vast.rows = [offer(1, 180)]
    with pytest.raises(OfferUnavailableError):
        await orch.rent(1)
    assert vast.created == 0


@pytest.mark.asyncio
async def test_gateway_unions_network_and_price_pools():
    calls = []

    class Client:
        def search_offers(self, *, query, order, limit, storage):
            calls.append(order)
            base = {"gpu_ram": 24576, "reliability": 0.99, "dph_total": 0.2}
            if order.startswith("inet_down-"):
                return [{**base, "id": 1, "inet_down": 8000}, {**base, "id": 2, "inet_down": 2000}]
            return [{**base, "id": 3, "inet_down": 180}, {**base, "id": 2, "inet_down": 2000}]

    gateway = VastSdkGateway("synthetic")
    gateway._client = Client()
    offers = await gateway.search_offers("synthetic", limit=3, storage_gb=60)
    assert [row.offer_id for row in offers] == [1, 2, 3]
    assert len(calls) == 2


@pytest.mark.parametrize("invalid", [0, "bad", "nan", "inf", -10])
def test_supplied_bad_speed_is_not_treated_as_missing(invalid):
    value = normalize_offer({"id": 1, "inet_down": invalid})
    assert value.inet_down_mbps is not None
    assert value.inet_down_mbps <= 0
    assert normalize_offer({"id": 1}).inet_down_mbps is None
    assert normalize_offer({"id": 1, "verified": "false"}).verified is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        "bad",
        {},
        {"success": False, "instances": []},
        {"instances": [], "next_token": "next"},
        {"instances": [], "total": 1},
        ["bad"],
        [{"label": "x"}],
    ],
)
async def test_bad_inventory_never_means_absent_or_rejected(payload):
    class Client:
        def show_instances(self):
            return payload

    gateway = VastSdkGateway("synthetic")
    gateway._client = Client()
    with pytest.raises(VastError):
        await gateway.instance_exists(123)
    with pytest.raises(VastError):
        await gateway.find_instances_by_label("x")


@pytest.mark.asyncio
async def test_sdk_does_not_replay_create_after_transport_timeout(monkeypatch):
    import requests

    calls = []

    def fail(self, request, **kwargs):
        calls.append(request.method)
        raise requests.Timeout("synthetic")

    monkeypatch.setattr(requests.Session, "send", fail)
    gateway = VastSdkGateway("synthetic")
    with pytest.raises(VastError):
        await gateway.create_instance(123, image="synthetic", disk_gb=60)
    assert calls == ["PUT"]


@pytest.mark.parametrize("inherited,expected", [(False, "9090|cu128|1"), (True, "7070|cu129|0")])
def test_bootstrap_pid1_values_precede_defaults_and_do_not_override_shell(tmp_path, inherited, expected):
    path = tmp_path / "environment"
    path.write_bytes(b"FISH_API_PORT=9090\0FISH_UV_EXTRA=cu128\0FISH_COMPILE=1\0PATH=malicious\0")
    helper = Path(__file__).parents[1] / "scripts/bootstrap_env.sh"
    script = f'source "{helper}"; '
    if inherited:
        script += "export FISH_API_PORT=7070 FISH_UV_EXTRA=cu129 FISH_COMPILE=0; "
    script += f'voxpilot_load_environment "{path}"; '
    script += 'printf "%s|%s|%s" "${FISH_API_PORT:-8080}" "${FISH_UV_EXTRA:-cu126}" "${FISH_COMPILE:-0}"; test "$PATH" != malicious'
    result = subprocess.run(
        ["bash", "-c", script], env={"PATH": "/usr/bin:/bin"}, capture_output=True, text=True, check=True
    )
    assert result.stdout == expected


def test_bootstrap_no_values_uses_defaults(tmp_path):
    helper = Path(__file__).parents[1] / "scripts/bootstrap_env.sh"
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source "{helper}"; voxpilot_load_environment /nonexistent; printf "%s" "${{FISH_API_PORT:-8080}}"',
        ],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "8080"


class Message:
    def __init__(self, bot=None):
        self.bot = bot
        self.chat = SimpleNamespace(id=1)
        self.message_thread_id = None
        self.replies = []

    async def answer(self, text, **kwargs):
        self.replies.append(text)

    async def edit_text(self, text=None, **kwargs):
        self.replies.append(text)


@pytest.mark.asyncio
@pytest.mark.parametrize("step", [voices.VoiceWizard.name, voices.VoiceWizard.audio, voices.VoiceWizard.transcript])
@pytest.mark.parametrize("action", ["start", "home", "cancel"])
async def test_wizard_navigation_cancels_every_step(step, action, monkeypatch):
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))
    await state.set_state(step)
    await state.update_data(name="synthetic", audio=b"not-real-audio")
    message = Message()

    async def acknowledge(*args, **kwargs):
        pass

    monkeypatch.setattr(home, "safe_callback_answer", acknowledge)
    if action == "home":
        await home.home(SimpleNamespace(message=message), state)
    else:
        await getattr(home, action)(message, state)
    assert await state.get_state() is None
    assert await state.get_data() == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["network", "oversize", "advertised"])
async def test_upload_failure_preserves_audio_step_and_existing_voices(db, failure):
    class Bot:
        async def download(self, file_id, destination):
            if failure == "network":
                raise RuntimeError("synthetic")
            if failure == "advertised":
                raise AssertionError("must not download")
            destination.write(b"a" * (1024 * 1024 + 1))

    class Store:
        async def validate_audio(self, *args):
            raise AssertionError("must not reach validation")

    await db.set("voice.active_id", "preserved")
    voices.configure(db, Store(), Settings(telegram_max_voice_mb=1))
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))
    await state.set_state(voices.VoiceWizard.audio)
    message = Message(Bot())
    await voices._accept_audio(
        message,
        state,
        file_id="synthetic",
        file_size=2 * 1024 * 1024 if failure == "advertised" else None,
        mime_type="audio/ogg",
        filename="test.ogg",
    )
    assert await state.get_state() == voices.VoiceWizard.audio.state
    assert len(message.replies) == 1
    assert await db.get("voice.active_id") == "preserved"


@pytest.mark.asyncio
async def test_legacy_25mb_setting_is_clamped_for_public_telegram(db):
    class Bot:
        async def download(self, *args, **kwargs):
            raise AssertionError("must reject before download")

    voices.configure(db, object(), Settings(telegram_max_voice_mb=25))
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))
    message = Message(Bot())
    await voices._accept_audio(
        message, state, file_id="synthetic", file_size=21 * 1024 * 1024, mime_type="audio/ogg", filename="test.ogg"
    )
    assert "20 MB" in message.replies[0]


@pytest.mark.asyncio
async def test_legacy_destroy_callback_never_calls_provider(monkeypatch):
    edits = []

    async def ack(*args, **kwargs):
        pass

    async def edit(message, text, **kwargs):
        edits.append(text)

    monkeypatch.setattr(servers, "safe_callback_answer", ack)
    monkeypatch.setattr(servers, "safe_edit_text", edit)
    monkeypatch.setattr(servers, "orch", lambda: (_ for _ in ()).throw(AssertionError("must not destroy")))
    await servers.destroy(SimpleNamespace(data="servers:destroy", message=object()))
    assert "التأكيد قديم" in edits[0]


@pytest.mark.asyncio
async def test_real_sdk_inventory_preserves_all_pages_and_rejects_bad_status(monkeypatch):
    responses = [
        {"instances": [{"id": 1, "label": "first"}], "next_token": "page2", "total_instances": 2},
        {"instances": [{"id": 2, "label": "target"}], "total_instances": 2},
    ]
    calls = []

    def page(client, params):
        calls.append(dict(params))
        return responses[len(calls) - 1]

    monkeypatch.setattr("vastai.api.instances.show_instances_v1", page)
    gateway = VastSdkGateway("synthetic")
    assert (await gateway.find_instances_by_label("target"))[0].instance_id == 2
    assert calls[1]["after_token"] == "page2"
    monkeypatch.setattr("vastai.api.instances.show_instances_v1", lambda *args: {"success": False, "instances": []})
    with pytest.raises(VastError):
        await gateway.instance_exists(999)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "page",
    [
        {"instances": []},
        {"instances": [], "total_instances": 1},
        {"instances": [{"id": 1}], "next_token": "repeating"},
    ],
)
async def test_real_sdk_empty_or_incomplete_inventory_is_handled_conservatively(monkeypatch, page):
    monkeypatch.setattr("vastai.api.instances.show_instances_v1", lambda *args: page)
    gateway = VastSdkGateway("synthetic")
    if page == {"instances": []}:
        assert not await gateway.instance_exists(999)
    else:
        with pytest.raises(VastError):
            await gateway.instance_exists(999)


def test_bootstrap_checkout_accepts_commit_sha_and_stops_before_launch_on_failure():
    from voxpilot.services.provisioning import build_onstart_cmd, build_vast_env

    sha = "a" * 40
    settings = Settings(voxpilot_repo_ref=sha, fish_model_revision="b" * 40)
    command = build_onstart_cmd(settings)
    assert "set -e" in command and f"fetch --depth 1 origin {sha}" in command
    assert "--branch" not in command
    assert "FISH_MODEL_REVISION=" + "b" * 40 in build_vast_env(settings, "synthetic")


@pytest.mark.parametrize("invalid", ["not-a-number", float("nan"), float("inf")])
def test_invalid_total_price_never_falls_back_to_cheaper_base(invalid):
    item = normalize_offer({"id": 1, "gpu_ram": 24000, "dph_total": invalid, "dph_base": 0.01})
    assert item.price_per_hour == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_stage", ["download", "validation"])
async def test_cancel_during_upload_cannot_restore_wizard(db, cancel_stage):
    state = FSMContext(MemoryStorage(), StorageKey(bot_id=1, chat_id=1, user_id=1))
    await state.set_state(voices.VoiceWizard.audio)

    class Bot:
        async def download(self, file_id, destination):
            destination.write(b"synthetic")
            if cancel_stage == "download":
                await state.clear()

    class Store:
        async def validate_audio(self, *args):
            if cancel_stage == "validation":
                await state.clear()

    voices.configure(db, Store(), Settings())
    message = Message(Bot())
    await voices._accept_audio(
        message, state, file_id="synthetic", file_size=None, mime_type="audio/ogg", filename="test.ogg"
    )
    assert await state.get_state() is None
    assert await state.get_data() == {}
    assert message.replies == []
