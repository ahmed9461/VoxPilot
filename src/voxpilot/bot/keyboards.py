from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from voxpilot.domain import GpuOffer, VoiceProfile
from voxpilot.services.tts_settings import EMOTION_TAGS


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎙 توليد صوت", callback_data="tts:generate", style="success")],
            [
                InlineKeyboardButton(text="🗣 الأصوات", callback_data="voices:list", style="primary"),
                InlineKeyboardButton(text="🎭 المشاعر", callback_data="settings:emotions", style="primary"),
            ],
            [InlineKeyboardButton(text="⚙️ إعدادات الصوت", callback_data="settings:tts")],
            [InlineKeyboardButton(text="🔎 البحث عن سيرفر", callback_data="servers:search", style="primary")],
            [
                InlineKeyboardButton(text="📊 حالة السيرفر", callback_data="servers:status"),
                InlineKeyboardButton(text="▶️ تشغيل", callback_data="servers:start", style="success"),
                InlineKeyboardButton(text="⏹ إيقاف", callback_data="servers:stop", style="danger"),
            ],
            [InlineKeyboardButton(text="🗑 حذف السيرفر", callback_data="servers:destroy_confirm", style="danger")],
        ]
    )


def offers_keyboard(offers: list[GpuOffer]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"🔍 {offer.display_name}", callback_data=f"servers:offer:{offer.offer_id}", style="primary")]
        for offer in offers
    ]
    rows += [
        [InlineKeyboardButton(text="🔄 تحديث العروض", callback_data="servers:search", style="primary")],
        [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def offer_confirm_keyboard(offer_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 استئجار وتجهيز", callback_data=f"servers:rent:{offer_id}", style="success")],
            [InlineKeyboardButton(text="⬅️ رجوع", callback_data="servers:search")],
        ]
    )


def destroy_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 نعم، احذف نهائيًا", callback_data="servers:destroy", style="danger")],
            [InlineKeyboardButton(text="إلغاء", callback_data="home")],
        ]
    )


def voices_keyboard(voices: list[VoiceProfile], active_id: str | None) -> InlineKeyboardMarkup:
    rows = []
    for voice in voices:
        marker = "✅ " if voice.voice_id == active_id else ""
        rows.append([InlineKeyboardButton(text=f"{marker}{voice.name}", callback_data=f"voices:select:{voice.voice_id}")])
        rows.append([InlineKeyboardButton(text=f"🗑 حذف {voice.name}", callback_data=f"voices:delete_confirm:{voice.voice_id}", style="danger")])
    rows.append([InlineKeyboardButton(text="➕ إضافة صوت", callback_data="voices:add", style="success")])
    rows.append([InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_voice_confirm_keyboard(voice_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 نعم، احذف الصوت", callback_data=f"voices:delete:{voice_id}", style="danger")],
            [InlineKeyboardButton(text="إلغاء", callback_data="voices:list")],
        ]
    )


def emotions_keyboard(active_key: str) -> InlineKeyboardMarkup:
    rows = []
    items = list(EMOTION_TAGS.items())
    for index in range(0, len(items), 2):
        row = []
        for key, (label, _tag) in items[index:index + 2]:
            prefix = "✅ " if key == active_key else ""
            row.append(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"settings:emotion:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def tts_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌡 الحرارة", callback_data="settings:temperature"),
                InlineKeyboardButton(text="🎯 Top‑P", callback_data="settings:top_p"),
            ],
            [
                InlineKeyboardButton(text="🔁 منع التكرار", callback_data="settings:repetition"),
                InlineKeyboardButton(text="🧩 طول القطعة", callback_data="settings:chunk"),
            ],
            [
                InlineKeyboardButton(text="🎵 الصيغة", callback_data="settings:format"),
                InlineKeyboardButton(text="🪙 حد الرموز", callback_data="settings:max_tokens"),
            ],
            [InlineKeyboardButton(text="🔢 Seed عشوائي", callback_data="settings:seed_random")],
            [InlineKeyboardButton(text="🧹 التطبيع", callback_data="settings:normalize")],
            [InlineKeyboardButton(text="⬅️ الرئيسية", callback_data="home")],
        ]
    )


def choices_keyboard(prefix: str, choices: list[tuple[str, str]], back: str = "settings:tts") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=label, callback_data=f"{prefix}:{value}")] for label, value in choices]
    rows.append([InlineKeyboardButton(text="⬅️ رجوع", callback_data=back)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
