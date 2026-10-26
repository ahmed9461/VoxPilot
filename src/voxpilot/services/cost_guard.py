from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from aiogram import Bot

from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.domain import InstancePhase
from voxpilot.services.billing import billing_snapshot
from voxpilot.services.orchestrator import Orchestrator


logger = logging.getLogger(__name__)


async def cost_guard_loop(bot: Bot, settings: Settings, db: Database, orchestrator: Orchestrator) -> None:
    while True:
        try:
            await _tick(bot, settings, db, orchestrator)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Cost Guard check failed: %s", type(exc).__name__)
        await asyncio.sleep(max(10, settings.cost_guard_poll_seconds))


async def _tick(bot: Bot, settings: Settings, db: Database, orchestrator: Orchestrator) -> None:
    values = await db.get_many(["instance.id", "instance.phase", "instance.generation",
                                "instance.pending_label", "instance.pending_since"])
    instance_id = values.get("instance.id")
    phase = values.get("instance.phase", InstancePhase.NONE.value)
    if not instance_id:
        label = values.get("instance.pending_label")
        if not label or orchestrator is None:
            return
        result = await orchestrator.reconcile_pending()
        if result["status"] == "recovered":
            await bot.send_message(settings.owner_telegram_id,
                "✅ عُثر على السيرفر الناتج عن الطلب السابق واستُعيد تتبعه. يجري التحقق من جاهزيته دون استئجار سيرفر آخر.")
            return
        if result["status"] in {"rejected", "not_pending"}:
            return
        try:
            since = datetime.fromisoformat(str(values.get("instance.pending_since")))
            if since.tzinfo is None:
                since = since.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - since).total_seconds()
        except (TypeError, ValueError):
            age = settings.pending_rental_warn_seconds  # Legacy unresolved request: warn now.
        if age >= settings.pending_rental_warn_seconds and await db.get("cost_guard.warned_pending") != label:
            await bot.send_message(settings.owner_telegram_id,
                "⚠️ <b>طلب استئجار غير محسوم</b>\nقد يكون لدى Vast سيرفر مدفوع لم يظهر بعد. "
                "أعيد التحقق دوريًا، ولن أكرر طلب الإنشاء. استخدم «حالة السيرفر» ثم «إعادة التحقق»؛ "
                "إن استمر الغموض راجع لوحة Vast قبل أي استئجار يدوي.")
            await db.set("cost_guard.warned_pending", label)
        return

    if phase in {
        InstancePhase.RENTING.value,
        InstancePhase.BOOTING.value,
        InstancePhase.PROVISIONING.value,
        InstancePhase.STOPPING.value,
        InstancePhase.DESTROYING.value,
        InstancePhase.ERROR.value,
    }:
        billing = await billing_snapshot(db)
        warn_after = settings.cost_guard_warn_minutes
        warning_group = (
            "provisioning"
            if phase in {InstancePhase.RENTING.value, InstancePhase.BOOTING.value, InstancePhase.PROVISIONING.value}
            else phase
        )
        warning_key = f"{instance_id}:{warning_group}"
        if (
            billing
            and billing["active"]
            and warn_after > 0
            and billing["active_seconds"] >= warn_after * 60
            and await db.get("cost_guard.warned_paid_phase") != warning_key
        ):
            detail = {
                "provisioning": "السيرفر المستأجر لم يصل إلى جاهزية Fish بعد.",
                InstancePhase.STOPPING.value: "لم يؤكد Vast إيقاف السيرفر بعد.",
                InstancePhase.DESTROYING.value: "لم يؤكد Vast حذف السيرفر بعد.",
                InstancePhase.ERROR.value: "حالة السيرفر تحتاج مراجعة.",
            }[warning_group]
            await bot.send_message(
                settings.owner_telegram_id,
                "💸 <b>تنبيه تكلفة</b>\n"
                f"{detail} العداد المحلي ما زال نشطًا؛ راجع حالة Vast والتكلفة.",
            )
            await db.set("cost_guard.warned_paid_phase", warning_key)
        return

    if phase != InstancePhase.READY.value or await db.get("tts.active", False):
        return
    stamp = await db.get("instance.last_activity_at")
    if not stamp:
        return
    try:
        last = datetime.fromisoformat(str(stamp))
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
    except ValueError:
        return
    idle_minutes = (datetime.now(UTC) - last).total_seconds() / 60

    auto_after = settings.cost_guard_auto_destroy_minutes
    if auto_after > 0 and idle_minutes >= auto_after:
        try:
            destroyed = await orchestrator.destroy_current(
                expected_instance_id=instance_id, expected_generation=values.get("instance.generation"),
                expected_idle_since=stamp,
            )
        except Exception:
            await bot.send_message(settings.owner_telegram_id, "⚠️ تعذر على حارس التكلفة حذف السيرفر تلقائيًا. راجع حالته من البوت.")
            return
        if destroyed:
            await bot.send_message(settings.owner_telegram_id, f"🛡 تم حذف السيرفر تلقائيًا بعد نحو {idle_minutes:.0f} دقيقة خمول.")
        return

    warn_after = settings.cost_guard_warn_minutes
    if warn_after <= 0 or idle_minutes < warn_after:
        return
    warned_stamp = await db.get("cost_guard.warned_activity_at")
    if warned_stamp == stamp:
        return
    await bot.send_message(
        settings.owner_telegram_id,
        f"💸 <b>تنبيه تكلفة</b>\nالسيرفر جاهز لكنه خامل منذ نحو {idle_minutes:.0f} دقيقة. إذا انتهيت، أوقفه أو احذفه.",
    )
    await db.set("cost_guard.warned_activity_at", stamp)
