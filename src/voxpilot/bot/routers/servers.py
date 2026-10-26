from __future__ import annotations

import logging
from html import escape
from typing import Any

from aiogram import Router
from aiogram.types import CallbackQuery

from voxpilot.bot.callbacks import safe_callback_answer, safe_edit_text
from voxpilot.bot.keyboards import (
    destroy_confirm_keyboard, main_menu, offer_confirm_keyboard, offers_keyboard, pending_rental_keyboard,
)
from voxpilot.services.instance_runtime import StaleConfirmation
from voxpilot.services.audio_probe import ReferenceAudioError, ReferenceAudioTooLong
from voxpilot.services.orchestrator import OfferUnavailableError, Orchestrator
from voxpilot.services.voice_store import VoiceStore

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
    label = "التكلفة النهائية المقدرة" if final else "تكلفة التشغيل المقدرة"
    return [
        f"⏱ وقت التشغيل المحتسب: <b>{_format_duration(active_seconds)}</b>",
        f"💵 {label}: <b>${cost:.4f}</b>",
        *(["ℹ️ تقدير محافظ بعد استعادة الطلب؛ قد تختلف الفاتورة الفعلية."] if billing.get("recovered_estimate") else []),
    ]


@router.callback_query(lambda q: q.data in {"servers:search", "servers:search_slow"})
async def search(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "جاري التحديث...")
    await safe_edit_text(callback.message, "🔎 أبحث عن عروض مناسبة الآن...")
    previous = await orch().db.get("offers.last", [])
    if not isinstance(previous, list):
        previous = []
    try:
        offers = await orch().offers(allow_slow=callback.data == "servers:search_slow")
    except Exception:
        logger.warning("Vast offer search failed")
        await safe_edit_text(callback.message, "❌ تعذر البحث في Vast.ai الآن.", reply_markup=main_menu())
        return
    refresh_no = int(await orch().db.get("offers.refresh_serial", 0) or 0) + 1
    await orch().db.set("offers.refresh_serial", refresh_no)
    if not offers:
        await safe_edit_text(
            callback.message,
            f"🔄 <b>تحديث السوق #{refresh_no}</b>\n\nلا توجد عروض مطابقة لشروط هذا البحث حاليًا. "
            "يمكنك إعادة البحث أو اختيار بدائل أبطأ دون رفع سقف السعر.",
            reply_markup=offers_keyboard([]),
        )
        return
    note = _refresh_note(previous, offers, refresh_no)
    await safe_edit_text(
        callback.message,
        f"🧾 <b>العروض المناسبة</b>\n{note}\n"
        f"المطابق الآن: <b>{len(offers)}</b>\n"
        + ("⚠️ هذه بدائل أبطأ اخترت إظهارها يدويًا.\n" if callback.data == "servers:search_slow" else "الأولوية لفئات سرعة التنزيل الأعلى، ثم السعر داخل الفئة.\n")
        + "سرعات الشبكة معلنة من المزود وليست قياسًا مضمونًا.\n\nاختر عرضًا لمراجعة التفاصيل:",
        reply_markup=offers_keyboard(offers),
    )


@router.callback_query(lambda q: q.data and q.data.startswith("servers:offer:"))
async def offer_details(callback: CallbackQuery) -> None:
    offer_id = int(callback.data.rsplit(":", 1)[1])
    offer = await orch().cached_offer(offer_id)
    await safe_callback_answer(callback)
    if offer is None:
        await safe_edit_text(callback.message, "العرض لم يعد في آخر نتائج البحث.", reply_markup=main_menu())
        return
    lines = [
        "🖥 <b>تفاصيل العرض</b>",
        f"GPU: <b>{escape(offer.gpu_name)}</b>",
        f"VRAM: <b>{offer.gpu_ram_gb:.0f} GB</b>",
        f"السعر: <b>${offer.price_per_hour:.3f}/ساعة</b>",
        f"الموثوقية: <b>{'?' if offer.reliability is None else f'{offer.reliability * 100:.1f}%'} </b>",
    ]
    if offer.inet_down_mbps:
        lines.append(f"التنزيل المعلن: <b>{offer.inet_down_mbps:.0f} Mbps</b> (نظريًا {offer.inet_down_mbps / 8:.1f} MB/s)")
    if offer.inet_up_mbps is not None:
        lines.append(f"الرفع المعلن: <b>{offer.inet_up_mbps:.0f} Mbps</b>")
    if offer.disk_bw_mbps is not None:
        lines.append(f"قراءة القرص المعلنة: <b>{offer.disk_bw_mbps:.0f} MB/s</b>")
    for direction, cost in (("التنزيل", offer.inet_down_cost_per_gb), ("الرفع", offer.inet_up_cost_per_gb)):
        if cost is not None:
            lines.append(f"رسوم نقل {direction}: <b>${cost:.4f}/GB</b>")
    if offer.network_fallback:
        lines.append("⚠️ عرض من البحث الاختياري الأبطأ؛ قد يستغرق التحميل وقتًا أطول.")
    if offer.location:
        lines.append(f"الموقع: <b>{escape(offer.location)}</b>")
    lines += ["", "السرعات معلنة؛ قد يحد مصدر التحميل أو القرص من السرعة الفعلية.",
              "عداد التشغيل تقديري، ولا يشمل كل رسوم النقل أو التخزين المتغيرة.",
              "سيُعاد فحص السوق والسعر قبل الاستئجار مباشرة."]
    await safe_edit_text(callback.message, "\n".join(lines), reply_markup=offer_confirm_keyboard(offer_id))


@router.callback_query(lambda q: q.data and q.data.startswith("servers:rent:"))
async def rent(callback: CallbackQuery) -> None:
    offer_id = int(callback.data.rsplit(":", 1)[1])
    await safe_callback_answer(callback, "بدء الاستئجار")
    await safe_edit_text(callback.message, "🚀 أعيد فحص العرض ثم أبدأ تجهيز السيرفر...")

    async def progress(_text: str) -> None:
        try:
            state = await orch().current_state(probe_fish=False)
            lines = ["⏳ <b>جاري تجهيز Fish Audio S2 Pro...</b>", "", "يتم تنزيل البيئة والنموذج عند أول تشغيل."]
            lines += _billing_lines(state.get("billing"))
            await safe_edit_text(callback.message, "\n".join(lines))
        except Exception:
            pass

    try:
        await orch().rent_and_prepare(offer_id, progress=progress)
    except OfferUnavailableError:
        logger.info("Selected Vast offer %s disappeared or became ineligible before rental", offer_id)
        try:
            offers = await orch().offers(exclude_offer_ids={offer_id})
        except Exception:
            logger.warning("Vast refresh after unavailable offer failed")
            await safe_edit_text(
                callback.message,
                "⚠️ <b>العرض لم يعد متاحًا</b>\n\nلم يتم إنشاء أي سيرفر. حدّث العروض واختر عرضًا آخر.",
                reply_markup=main_menu(),
            )
            return
        if not offers:
            await safe_edit_text(
                callback.message,
                "⚠️ <b>العرض لم يعد متاحًا</b>\n\nلم يتم إنشاء أي سيرفر، ولا توجد عروض مطابقة حاليًا.",
                reply_markup=main_menu(),
            )
            return
        await safe_edit_text(
            callback.message,
            "⚠️ <b>العرض تغيّر أو لم يعد متاحًا</b>\n\n"
            "لم يتم إنشاء أي سيرفر ولم يبدأ عداد التكلفة. استبعدت العرض المرفوض؛ اختر من العروض الأخرى:",
            reply_markup=offers_keyboard(offers),
        )
        return
    except Exception:
        logger.warning("Vast rent/provision failed")
        try:
            state = await orch().current_state(probe_fish=False)
            billing = state.get("billing")
            if state.get("pending"):
                await safe_edit_text(callback.message, _pending_text(state), reply_markup=pending_rental_keyboard())
                return
        except Exception:
            billing = None
        lines = [
            "❌ <b>تعذر تجهيز السيرفر</b>",
            "",
            "إذا تم إنشاء السيرفر بالفعل فسيبقى ظاهرًا حتى تحذفه يدويًا، حتى لا نفقده أو نحذفه بصمت.",
        ]
        lines += _billing_lines(billing)
        await safe_edit_text(callback.message, "\n".join(lines), reply_markup=main_menu())
        return
    state = await orch().current_state(probe_fish=False)
    lines = ["✅ <b>السيرفر جاهز</b>", "", "يمكنك الآن إرسال النص لتوليد الصوت."]
    lines += _billing_lines(state.get("billing"))
    await safe_edit_text(callback.message, "\n".join(lines), reply_markup=main_menu())


@router.callback_query(lambda q: q.data == "servers:status")
async def status(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    try:
        state = await orch().current_state(probe_fish=True)
    except Exception:
        logger.warning("Server status failed")
        await safe_edit_text(callback.message, "❌ تعذر قراءة حالة السيرفر.", reply_markup=main_menu())
        return
    if state.get("pending"):
        await safe_edit_text(callback.message, _pending_text(state), reply_markup=pending_rental_keyboard())
        return
    if not state.get("instance_id"):
        await safe_edit_text(callback.message, "📊 <b>حالة السيرفر</b>\n\nلا يوجد سيرفر حالي.", reply_markup=main_menu())
        return
    phase = str(state.get("phase") or "none")
    labels = {
        "renting": "⏳ جاري الاستئجار",
        "booting": "⏳ جاري التشغيل",
        "provisioning": "⏳ جاري التجهيز",
        "ready": "✅ Fish يستجيب لفحص الصحة" if state.get("fish_ready") is not False else "⚠️ Fish غير جاهز",
        "stopping": "⏳ جاري الإيقاف",
        "stopped": "⏹ متوقف",
        "destroying": "⏳ جاري الحذف",
        "error": "⚠️ يحتاج مراجعة",
    }
    lines = ["📊 <b>حالة السيرفر</b>", "", labels.get(phase, phase)]
    offer = state.get("offer")
    if isinstance(offer, dict) and offer.get("price_per_hour") is not None:
        lines.append(f"السعر: <b>${float(offer['price_per_hour']):.3f}/ساعة</b>")
    if phase == "ready":
        active_id = await orch().db.get("voice.active_id")
        if active_id:
            store = VoiceStore(orch().settings.voice_data_dir)
            profile = await store.get(str(active_id))
            if profile is None:
                lines.append("⚠️ الصوت الحالي غير موجود. اختر صوتًا آخر من «الأصوات».")
            else:
                try:
                    await store.validate_profile(profile)
                except ReferenceAudioTooLong as exc:
                    lines.append(
                        f"⚠️ العينة الحالية نحو {exc.duration_seconds:.0f} ثانية؛ "
                        "هذا الطول قد يفشل التوليد. استخدم عينة لا تتجاوز 30 ثانية."
                    )
                except ReferenceAudioError:
                    lines.append("⚠️ تعذر فحص العينة الحالية؛ راجعها من «الأصوات».")
    lines += _billing_lines(state.get("billing"))
    await safe_edit_text(callback.message, "\n".join(lines), reply_markup=main_menu())


@router.callback_query(lambda q: q.data == "servers:stop")
async def stop(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "جاري الإيقاف...")
    try:
        stopped = await orch().stop_current()
    except Exception:
        logger.warning("Server stop failed")
        await safe_edit_text(callback.message, "❌ تعذر إيقاف السيرفر.", reply_markup=main_menu())
        return
    if not stopped:
        state = await orch().current_state(probe_fish=False)
        text = "السيرفر متوقف بالفعل." if state.get("instance_id") else "لا يوجد سيرفر حالي."
        await safe_edit_text(callback.message, text, reply_markup=main_menu())
        return
    state = await orch().current_state(probe_fish=False)
    lines = ["⏹ تم إيقاف السيرفر. قد تستمر رسوم التخزين لدى Vast أثناء التوقف."]
    lines += _billing_lines(state.get("billing"))
    await safe_edit_text(callback.message, "\n".join(lines), reply_markup=main_menu())


@router.callback_query(lambda q: q.data == "servers:start")
async def start_instance(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "جاري التشغيل...")
    await safe_edit_text(callback.message, "▶️ جاري تشغيل السيرفر وانتظار Fish...")
    try:
        started = await orch().start_current()
    except Exception:
        logger.warning("Server start failed")
        await safe_edit_text(callback.message, "❌ تعذر تشغيل السيرفر أو لم يصبح Fish جاهزًا.", reply_markup=main_menu())
        return
    if not started:
        state = await orch().current_state(probe_fish=False)
        text = "السيرفر يعمل أو جارٍ تشغيله بالفعل." if state.get("instance_id") else "لا يوجد سيرفر حالي."
        await safe_edit_text(callback.message, text, reply_markup=main_menu())
        return
    state = await orch().current_state(probe_fish=False)
    lines = ["✅ السيرفر جاهز."]
    lines += _billing_lines(state.get("billing"))
    await safe_edit_text(callback.message, "\n".join(lines), reply_markup=main_menu())


def _pending_text(state: dict[str, Any]) -> str:
    detail = {
        "multiple_matches": "ظهرت عدة موارد بنفس علامة الطلب؛ يلزم مراجعتها في Vast دون اختيار واحد عشوائيًا.",
        "inventory_unavailable": "تعذرت قراءة قائمة السيرفرات من Vast الآن.",
        "awaiting_provider": "لم يتضح بعد هل أنشأ Vast السيرفر أم لا.",
        "creating": "طلب الإنشاء قيد التحقق.",
    }.get(state.get("pending_status"), "لم تُحسم نتيجة الطلب السابق بعد.")
    return ("⚠️ <b>استئجار غير محسوم</b>\n\n" + detail +
            "\nقد يوجد سيرفر مدفوع. أُعيد التحقق دوريًا، وأمنع إنشاء سيرفر ثانٍ حتى حسم الطلب. "
            "لن يُحذف أي سيرفر تلقائيًا بسبب هذا الغموض.")


@router.callback_query(lambda q: q.data == "servers:reconcile")
async def reconcile(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback, "أتحقق من الطلب السابق...")
    try:
        result = await orch().reconcile_pending()
        if result["status"] == "recovered":
            text = "✅ عُثر على السيرفر السابق واستُعيد تتبعه. يجري التحقق من جاهزيته، دون استئجار سيرفر جديد."
        elif result["status"] == "rejected":
            text = "✅ تأكد رفض الطلب السابق ولم يظهر سيرفر مطابق له. يمكنك البحث عن عرض آخر."
        elif result["status"] == "not_pending":
            text = "لا يوجد طلب معلّق الآن. راجع حالة السيرفر الحالية."
        else:
            state = await orch().current_state()
            await safe_edit_text(callback.message, _pending_text(state), reply_markup=pending_rental_keyboard())
            return
        await safe_edit_text(callback.message, text, reply_markup=main_menu())
    except Exception as exc:
        logger.warning("Pending rental check failed: %s", type(exc).__name__)
        await safe_edit_text(callback.message, "تعذر التحقق الآن. احتفظت بحماية منع الاستئجار المكرر.",
                             reply_markup=pending_rental_keyboard())


@router.callback_query(lambda q: q.data == "servers:destroy_confirm")
async def destroy_confirm(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    try:
        confirmation = await orch().prepare_destroy_confirmation()
    except Exception:
        await safe_edit_text(callback.message, "لا يمكن إنشاء تأكيد حذف الآن. راجع حالة السيرفر.", reply_markup=main_menu())
        return
    lines = ["⚠️ سيتم حذف هذا السيرفر نهائيًا وإيقافه."]
    lines += _billing_lines(confirmation.get("billing"))
    lines += ["", "هذا التأكيد مرتبط بالسيرفر الحالي وله صلاحية محدودة. هل أنت متأكد؟"]
    await safe_edit_text(callback.message, "\n".join(lines), reply_markup=destroy_confirm_keyboard(
        confirmation["instance_id"], confirmation["nonce"]))


@router.callback_query(lambda q: q.data == "servers:destroy" or q.data and q.data.startswith("servers:destroy:"))
async def destroy(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    try:
        parts = (callback.data or "").split(":")
        if len(parts) != 4 or not parts[2].isdigit() or len(parts[3]) != 16:
            raise StaleConfirmation("Legacy or invalid confirmation")
        destroyed = await orch().destroy_current(expected_instance_id=int(parts[2]), confirmation_nonce=parts[3])
    except StaleConfirmation:
        await safe_edit_text(callback.message, "⚠️ التأكيد قديم أو تغيّر السيرفر. لم أرسل طلب حذف؛ افتح تأكيدًا جديدًا.", reply_markup=main_menu())
        return
    except Exception as exc:
        logger.warning("Server destroy confirmation failed: %s", type(exc).__name__)
        await safe_edit_text(callback.message, "⚠️ لم يتأكد اكتمال الحذف. احتفظت بتتبع السيرفر والعداد؛ راجع حالته.", reply_markup=main_menu())
        return
    if not destroyed:
        await safe_edit_text(callback.message, "لا يوجد سيرفر حالي.", reply_markup=main_menu())
        return
    billing = await orch().last_billing_snapshot()
    lines = ["🗑 تم تأكيد حذف السيرفر نهائيًا."]
    lines += _billing_lines(billing, final=True)
    await safe_edit_text(callback.message, "\n".join(lines), reply_markup=main_menu())
