from __future__ import annotations

from html import escape

from aiogram import Router
from aiogram.types import CallbackQuery

from voxpilot.bot.callbacks import safe_callback_answer, safe_edit_text
from voxpilot.bot.keyboards import choices_keyboard, emotions_keyboard, tts_settings_keyboard
from voxpilot.db import Database
from voxpilot.services.tts_settings import (
    EMOTION_TAGS,
    STABILITY_SEED,
    STABILITY_TEMPERATURE,
    STABILITY_TOP_P,
    load_tts_settings,
    set_tts_value,
)

router = Router(name="tts_settings")
_db: Database | None = None


def configure(db: Database) -> None:
    global _db
    _db = db


def db() -> Database:
    if _db is None:
        raise RuntimeError("Settings router is not configured")
    return _db


def _settings_text(settings) -> str:
    emotion = EMOTION_TAGS[settings.emotion_key][0]
    seed = "عشوائي" if settings.seed is None else str(settings.seed)
    stability = (
        f"مفعّل — T {STABILITY_TEMPERATURE:.1f} / P {STABILITY_TOP_P:.1f} / Seed {STABILITY_SEED}"
        if settings.stability_mode
        else "متوقف"
    )
    saved_suffix = " (محفوظ للوضع العادي)" if settings.stability_mode else ""
    return (
        "⚙️ <b>إعدادات الصوت</b>\n\n"
        f"🎭 المشاعر: <b>{escape(emotion)}</b>\n"
        f"🧷 ثبات الأداء: <b>{escape(stability)}</b>\n"
        f"🌡 الحرارة{saved_suffix}: <b>{settings.temperature:.1f}</b>\n"
        f"🎯 Top‑P{saved_suffix}: <b>{settings.top_p:.1f}</b>\n"
        f"🔁 منع التكرار: <b>{settings.repetition_penalty:.1f}</b>\n"
        f"🧩 طول القطعة: <b>{settings.chunk_length}</b>\n"
        f"🪙 حد الرموز: <b>{settings.max_new_tokens}</b>\n"
        f"🎵 الصيغة: <b>{escape(settings.format.upper())}</b>\n"
        f"🧹 التطبيع: <b>{'مفعّل' if settings.normalize else 'متوقف'}</b>\n"
        f"🔢 Seed{saved_suffix}: <b>{escape(seed)}</b>"
    )


async def _show_settings(callback: CallbackQuery) -> None:
    settings = await load_tts_settings(db())
    await safe_edit_text(
        callback.message,
        _settings_text(settings),
        reply_markup=tts_settings_keyboard(settings.stability_mode),
    )


@router.callback_query(lambda q: q.data == "settings:tts")
async def tts_settings(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    await _show_settings(callback)


@router.callback_query(lambda q: q.data == "settings:emotions")
async def emotions(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    settings = await load_tts_settings(db())
    await safe_edit_text(
        callback.message,
        "🎭 <b>المشاعر والنبرة</b>\n\n"
        "اختر أداءً عامًا. وللتحكم داخل النص اكتب وصف الأداء بين أقواس عادية. "
        "التعليمات الشائعة مثل (تتنهد) و(تضحك بخفة) تتحول إلى وسوم S2 الأصلية، "
        "والوصف المركب يبقى وصفًا حرًا. وسوم Fish اليدوية [ ] تبقى مدعومة.",
        reply_markup=emotions_keyboard(settings.emotion_key),
    )


@router.callback_query(lambda q: q.data and q.data.startswith("settings:emotion:"))
async def set_emotion(callback: CallbackQuery) -> None:
    key = callback.data.rsplit(":", 1)[1]
    if key not in EMOTION_TAGS:
        await safe_callback_answer(callback, "خيار غير صالح", show_alert=True)
        return
    await set_tts_value(db(), "emotion_key", key)
    await safe_callback_answer(callback, "تم الحفظ")
    await callback.message.edit_reply_markup(reply_markup=emotions_keyboard(key))


@router.callback_query(lambda q: q.data == "settings:stability")
async def toggle_stability(callback: CallbackQuery) -> None:
    settings = await load_tts_settings(db())
    updated = await set_tts_value(db(), "stability_mode", not settings.stability_mode)
    await safe_callback_answer(callback, "ثبات الأداء مفعّل" if updated.stability_mode else "ثبات الأداء متوقف")
    await _show_settings(callback)


@router.callback_query(lambda q: q.data == "settings:temperature")
async def temperature_menu(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    await safe_edit_text(
        callback.message,
        "🌡 <b>الحرارة</b>\nالقيمة الافتراضية الرسمية 0.8. "
        "عند تفعيل «ثبات الأداء» يستخدم VoxPilot قيمة 0.6 مؤقتًا دون حذف اختيارك المحفوظ.",
        reply_markup=choices_keyboard("settings:set:temperature", [("0.5", "0.5"), ("0.7", "0.7"), ("0.8 — افتراضي", "0.8"), ("1.0", "1.0")]),
    )


@router.callback_query(lambda q: q.data == "settings:top_p")
async def top_p_menu(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    await safe_edit_text(
        callback.message,
        "🎯 <b>Top‑P</b>\nعند تفعيل «ثبات الأداء» يستخدم VoxPilot قيمة 0.7 مؤقتًا دون حذف اختيارك المحفوظ.",
        reply_markup=choices_keyboard("settings:set:top_p", [("0.6", "0.6"), ("0.7", "0.7"), ("0.8 — افتراضي", "0.8"), ("0.9", "0.9"), ("1.0", "1.0")]),
    )


@router.callback_query(lambda q: q.data == "settings:repetition")
async def repetition_menu(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    await safe_edit_text(
        callback.message,
        "🔁 <b>منع التكرار</b>",
        reply_markup=choices_keyboard("settings:set:repetition_penalty", [("1.0", "1.0"), ("1.1 — افتراضي", "1.1"), ("1.2", "1.2"), ("1.3", "1.3")]),
    )


@router.callback_query(lambda q: q.data == "settings:chunk")
async def chunk_menu(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    await safe_edit_text(
        callback.message,
        "🧩 <b>طول القطعة</b>",
        reply_markup=choices_keyboard("settings:set:chunk_length", [("100", "100"), ("200", "200"), ("300 — افتراضي", "300"), ("500", "500")]),
    )


@router.callback_query(lambda q: q.data == "settings:format")
async def format_menu(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    await safe_edit_text(
        callback.message,
        "🎵 <b>صيغة الإخراج</b>",
        reply_markup=choices_keyboard("settings:set:format", [("MP3 — افتراضي", "mp3"), ("WAV", "wav"), ("OPUS", "opus")]),
    )


@router.callback_query(lambda q: q.data == "settings:max_tokens")
async def max_tokens_menu(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    await safe_edit_text(
        callback.message,
        "🪙 <b>حد الرموز</b>",
        reply_markup=choices_keyboard("settings:set:max_new_tokens", [("512", "512"), ("1024 — افتراضي", "1024"), ("2048", "2048")]),
    )


@router.callback_query(lambda q: q.data == "settings:normalize")
async def toggle_normalize(callback: CallbackQuery) -> None:
    settings = await load_tts_settings(db())
    await set_tts_value(db(), "normalize", not settings.normalize)
    await safe_callback_answer(callback, "تم التغيير")
    await _show_settings(callback)


@router.callback_query(lambda q: q.data == "settings:seed_random")
async def seed_random(callback: CallbackQuery) -> None:
    await set_tts_value(db(), "seed", None)
    await safe_callback_answer(callback, "Seed عشوائي محفوظ للوضع العادي")
    await _show_settings(callback)


@router.callback_query(lambda q: q.data and q.data.startswith("settings:set:"))
async def set_value(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 3)
    if len(parts) != 4:
        await safe_callback_answer(callback, "خيار غير صالح", show_alert=True)
        return
    field, raw = parts[2], parts[3]
    converters = {
        "temperature": float,
        "top_p": float,
        "repetition_penalty": float,
        "chunk_length": int,
        "max_new_tokens": int,
        "format": str,
    }
    converter = converters.get(field)
    if converter is None:
        await safe_callback_answer(callback, "خيار غير صالح", show_alert=True)
        return
    try:
        await set_tts_value(db(), field, converter(raw))
    except ValueError:
        await safe_callback_answer(callback, "قيمة غير صالحة", show_alert=True)
        return
    await safe_callback_answer(callback, "تم الحفظ")
    await _show_settings(callback)
