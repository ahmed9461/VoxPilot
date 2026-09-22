from __future__ import annotations

import logging
from html import escape
from typing import Any

from aiogram import Router
from aiogram.types import CallbackQuery

from voxpilot.bot.callbacks import safe_callback_answer
from voxpilot.bot.keyboards import destroy_confirm_keyboard, main_menu, offer_confirm_keyboard, offers_keyboard
from voxpilot.services.orchestrator import Orchestrator

logger = logging.getLogger(__name__)
router = Router(name="servers")
_orch: Orchestrator | None = None


def configure(orchestrator: Orchestrator) -> None:
    global _orch
    _orch = orchestrator


def orch() -> Orchestrator:
    if _orch is None:
        raise RuntimeError("Servers router is not configured")
    return _orch


def _offer_signature(item: Any) -> tuple[int, float, float, str]:
    if isinstance(item, dict):
        return (
            int(item.get("offer_id") or 0),
            round(float(item.get("price_per_hour") or 0.0), 6),
            round(float(item.get("inet_down_mbps") or 0.0), 3),
            str(item.get("gpu_name") or ""),
        )
    return (
        int(getattr(item, "offer_id", 0)),
        round(float(getattr(item, "price_per_hour", 0.0)), 6),
        round(float(getattr(item, "inet_down_mbps", 0.0) or 0.0), 3),
        str(getattr(item, "gpu_name", "")),
    )


def _refresh_note(previous: list[Any], current: list[Any], refresh_no: int) -> str:
    prefix = f"🔄 تحديث السوق #{refresh_no}"
    if not previous:
        return f"{prefix} — تم فحص السوق الآن."
    old = [_offer_signature(item) for item in previous]
    new = [_offer_signature(item) for item in current]
    if old == new:
        return f"{prefix} — نفس النتائج ما زالت متاحة."
    old_ids = {item[0] for item in old}
    new_ids = {item[0] for item in new}
    added = len(new_ids - old_ids)
    removed = len(old_ids - new_ids)
    if added or removed:
        return f"{prefix} — {added} عرض جديد و{removed} عرض اختفى."
    return f"{prefix} — تغيّرت الأسعار أو ترتيب العروض."


def _format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _billing_lines(billing: Any, *, final: bool = False) -> list[str]:
    if not isinstance(billing, dict):
        return []
    active_seconds = float(billing.get("active_seconds") or 0.0)
    cost = float(billing.get("estimated_cost_usd") or 0.0)
    label = "التكلفة النهائية المقدرة" if final else "التكلفة حتى الآن"
    return [
        f"⏱ وقت التشغيل المحتسب: <b>{_format_duration(active_seconds)}</b>",
        f"💵 {label}: <b>${cost:.4f}</b>",
    ]


@router.callback_query(lambda q: q.data == "servers:search")
async def search(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "جاري التحديث...")
    await callback.message.edit_text("🔎 أبحث عن عروض مناسبة الآن...")
    previous = await orch().db.get("offers.last", [])
    if not isinstance(previous, list):
        previous = []
    try:
        offers = await orch().offers()
    except Exception:
        logger.exception("Vast offer search failed")
        await callback.message.edit_text("❌ تعذر البحث في Vast.ai الآن.", reply_markup=main_menu())
        return
    refresh_no = int(await orch().db.get("offers.refresh_serial", 0) or 0) + 1
    await orch().db.set("offers.refresh_serial", refresh_no)
    if not offers:
        await callback.message.edit_text(
            f"🔄 <b>تحديث السوق #{refresh_no}</b>\n\nلا توجد عروض مطابقة للشروط حاليًا.",
            reply_markup=main_menu(),
        )
        return
    note = _refresh_note(previous, offers, refresh_no)
    await callback.message.edit_text(
        f"🧾 <b>العروض المناسبة</b>\n{note}\n"
        f"المطابق الآن: <b>{len(offers)}</b>\n\nاختر عرضًا لمراجعة التفاصيل:",
        reply_markup=offers_keyboard(offers),
    )


@router.callback_query(lambda q: q.data and q.data.startswith("servers:offer:"))
async def offer_details(callback: CallbackQuery) -> None:
    offer_id = int(callback.data.rsplit(":", 1)[1])
    offer = await orch().cached_offer(offer_id)
    await safe_callback_answer(callback)
    if offer is None:
        await callback.message.edit_text("العرض لم يعد في آخر نتائج البحث.", reply_markup=main_menu())
        return
    lines = [
        "🖥 <b>تفاصيل العرض</b>",
        f"GPU: <b>{escape(offer.gpu_name)}</b>",
        f"VRAM: <b>{offer.gpu_ram_gb:.0f} GB</b>",
        f"السعر: <b>${offer.price_per_hour:.3f}/ساعة</b>",
        f"الموثوقية: <b>{'?' if offer.reliability is None else f'{offer.reliability * 100:.1f}%'} </b>",
    ]
    if offer.inet_down_mbps:
        lines.append(f"سرعة التنزيل: <b>{offer.inet_down_mbps:.0f} Mbps</b>")
    if offer.location:
        lines.append(f"الموقع: <b>{escape(offer.location)}</b>")
    lines += ["", "سيُعاد فحص السوق والسعر قبل الاستئجار مباشرة."]
    await callback.message.edit_text("\n".join(lines), reply_markup=offer_confirm_keyboard(offer_id))


@router.callback_query(lambda q: q.data and q.data.startswith("servers:rent:"))
async def rent(callback: CallbackQuery) -> None:
    offer_id = int(callback.data.rsplit(":", 1)[1])
    await safe_callback_answer(callback, "بدء الاستئجار")
    await callback.message.edit_text("🚀 أعيد فحص العرض ثم أبدأ تجهيز السيرفر...")

    async def progress(_text: str) -> None:
        try:
            state = await orch().current_state(probe_fish=False)
            lines = ["⏳ <b>جاري تجهيز Fish Audio S2 Pro...</b>", "", "يتم تنزيل البيئة والنموذج عند أول تشغيل."]
            lines += _billing_lines(state.get("billing"))
            await callback.message.edit_text("\n".join(lines))
        except Exception:
            pass

    try:
        await orch().rent_and_prepare(offer_id, progress=progress)
    except Exception:
        logger.exception("Vast rent/provision failed")
        try:
            state = await orch().current_state(probe_fish=False)
            billing = state.get("billing")
        except Exception:
            billing = None
        lines = [
            "❌ <b>تعذر تجهيز السيرفر</b>",
            "",
            "إذا تم إنشاء السيرفر بالفعل فسيبقى ظاهرًا حتى تحذفه يدويًا، حتى لا نفقده أو نحذفه بصمت.",
        ]
        lines += _billing_lines(billing)
        await callback.message.edit_text("\n".join(lines), reply_markup=main_menu())
        return
    state = await orch().current_state(probe_fish=False)
    lines = ["✅ <b>السيرفر جاهز</b>", "", "يمكنك الآن إرسال النص لتوليد الصوت."]
    lines += _billing_lines(state.get("billing"))
    await callback.message.edit_text("\n".join(lines), reply_markup=main_menu())


@router.callback_query(lambda q: q.data == "servers:status")
async def status(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    try:
        state = await orch().current_state(probe_fish=True)
    except Exception:
        logger.exception("Server status failed")
        await callback.message.edit_text("❌ تعذر قراءة حالة السيرفر.", reply_markup=main_menu())
        return
    if not state.get("instance_id"):
        await callback.message.edit_text("📊 <b>حالة السيرفر</b>\n\nلا يوجد سيرفر حالي.", reply_markup=main_menu())
        return
    phase = str(state.get("phase") or "none")
    labels = {
        "renting": "⏳ جاري الاستئجار",
        "booting": "⏳ جاري التشغيل",
        "provisioning": "⏳ جاري التجهيز",
        "ready": "✅ جاهز" if state.get("fish_ready") is not False else "⚠️ Fish غير جاهز",
        "stopping": "⏳ جاري الإيقاف",
        "stopped": "⏹ متوقف",
        "destroying": "⏳ جاري الحذف",
        "error": "⚠️ يحتاج مراجعة",
    }
    lines = ["📊 <b>حالة السيرفر</b>", "", labels.get(phase, phase)]
    offer = state.get("offer")
    if isinstance(offer, dict) and offer.get("price_per_hour") is not None:
        lines.append(f"السعر: <b>${float(offer['price_per_hour']):.3f}/ساعة</b>")
    lines += _billing_lines(state.get("billing"))
    await callback.message.edit_text("\n".join(lines), reply_markup=main_menu())


@router.callback_query(lambda q: q.data == "servers:stop")
async def stop(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "جاري الإيقاف...")
    try:
        stopped = await orch().stop_current()
    except Exception:
        logger.exception("Server stop failed")
        await callback.message.edit_text("❌ تعذر إيقاف السيرفر.", reply_markup=main_menu())
        return
    if not stopped:
        await callback.message.edit_text("لا يوجد سيرفر حالي.", reply_markup=main_menu())
        return
    state = await orch().current_state(probe_fish=False)
    lines = ["⏹ تم إيقاف السيرفر. قد تستمر رسوم التخزين لدى Vast أثناء التوقف."]
    lines += _billing_lines(state.get("billing"))
    await callback.message.edit_text("\n".join(lines), reply_markup=main_menu())


@router.callback_query(lambda q: q.data == "servers:start")
async def start_instance(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "جاري التشغيل...")
    await callback.message.edit_text("▶️ جاري تشغيل السيرفر وانتظار Fish...")
    try:
        started = await orch().start_current()
    except Exception:
        logger.exception("Server start failed")
        await callback.message.edit_text("❌ تعذر تشغيل السيرفر أو لم يصبح Fish جاهزًا.", reply_markup=main_menu())
        return
    if not started:
        await callback.message.edit_text("لا يوجد سيرفر حالي.", reply_markup=main_menu())
        return
    state = await orch().current_state(probe_fish=False)
    lines = ["✅ السيرفر جاهز."]
    lines += _billing_lines(state.get("billing"))
    await callback.message.edit_text("\n".join(lines), reply_markup=main_menu())


@router.callback_query(lambda q: q.data == "servers:destroy_confirm")
async def destroy_confirm(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    try:
        state = await orch().current_state(probe_fish=False)
        billing = state.get("billing")
    except Exception:
        billing = None
    lines = ["⚠️ سيتم حذف السيرفر نهائيًا وإيقافه."]
    lines += _billing_lines(billing)
    lines += ["", "هل أنت متأكد؟"]
    await callback.message.edit_text("\n".join(lines), reply_markup=destroy_confirm_keyboard())


@router.callback_query(lambda q: q.data == "servers:destroy")
async def destroy(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "جاري الحذف...")
    try:
        destroyed = await orch().destroy_current()
    except Exception:
        logger.exception("Server destroy failed")
        await callback.message.edit_text("❌ تعذر حذف السيرفر.", reply_markup=main_menu())
        return
    if not destroyed:
        await callback.message.edit_text("لا يوجد سيرفر حالي.", reply_markup=main_menu())
        return
    billing = await orch().last_billing_snapshot()
    lines = ["🗑 تم حذف السيرفر نهائيًا."]
    lines += _billing_lines(billing, final=True)
    await callback.message.edit_text("\n".join(lines), reply_markup=main_menu())
