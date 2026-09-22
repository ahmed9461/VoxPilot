from __future__ import annotations

import logging
from html import escape
from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from voxpilot.bot.callbacks import safe_callback_answer, safe_edit_text
from voxpilot.bot.keyboards import delete_voice_confirm_keyboard, main_menu, voices_keyboard
from voxpilot.config import Settings
from voxpilot.db import Database
from voxpilot.services.voice_store import VoiceStore

logger = logging.getLogger(__name__)
router = Router(name="voices")
_db: Database | None = None
_store: VoiceStore | None = None
_settings: Settings | None = None


class VoiceWizard(StatesGroup):
    name = State()
    audio = State()
    transcript = State()


def configure(db: Database, store: VoiceStore, settings: Settings) -> None:
    global _db, _store, _settings
    _db, _store, _settings = db, store, settings


def deps() -> tuple[Database, VoiceStore, Settings]:
    if _db is None or _store is None or _settings is None:
        raise RuntimeError("Voice router is not configured")
    return _db, _store, _settings


async def _show_voices(callback: CallbackQuery) -> None:
    database, store, _ = deps()
    voices = await store.list()
    active_id = await database.get("voice.active_id")
    active = next((v.name for v in voices if v.voice_id == active_id), None)
    text = "🗣 <b>الأصوات المحفوظة</b>\n\n"
    if voices:
        text += f"المحفوظ: <b>{len(voices)}</b>\nالصوت الحالي: <b>{escape(active) if active else 'غير محدد'}</b>"
    else:
        text += "لا يوجد صوت محفوظ بعد."
    await safe_edit_text(callback.message, text, reply_markup=voices_keyboard(voices, active_id))


@router.callback_query(lambda q: q.data == "voices:list")
async def list_voices(callback: CallbackQuery) -> None:
    await safe_callback_answer(callback)
    await _show_voices(callback)


@router.callback_query(lambda q: q.data == "voices:add")
async def add_voice(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_callback_answer(callback)
    await state.clear()
    await state.set_state(VoiceWizard.name)
    await safe_edit_text(callback.message, "➕ <b>إضافة صوت</b>\n\nأرسل اسمًا لهذا الصوت.")


@router.message(VoiceWizard.name, F.text)
async def voice_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > 80:
        await message.answer("أرسل اسمًا واضحًا لا يتجاوز 80 حرفًا.")
        return
    await state.update_data(name=name)
    await state.set_state(VoiceWizard.audio)
    await message.answer("🎤 أرسل الآن عينة الصوت كـ Voice أو ملف صوتي. الأفضل عينة نظيفة مدتها نحو 10–30 ثانية.")


async def _accept_audio(
    message: Message,
    state: FSMContext,
    *,
    file_id: str,
    file_size: int | None,
    mime_type: str,
    filename: str | None,
) -> None:
    _, _, settings = deps()
    limit = settings.telegram_max_voice_mb * 1024 * 1024
    if file_size and file_size > limit:
        await message.answer(f"العينة أكبر من الحد المسموح ({settings.telegram_max_voice_mb} MB).")
        return
    buffer = BytesIO()
    await message.bot.download(file_id, destination=buffer)
    data = buffer.getvalue()
    if not data or len(data) > limit:
        await message.answer("تعذر قبول العينة أو حجمها أكبر من الحد.")
        return
    await state.update_data(audio=data, mime_type=mime_type, filename=filename)
    await state.set_state(VoiceWizard.transcript)
    await message.answer("📝 الآن أرسل <b>النص المطابق لما قيل في العينة</b>. Fish يستخدمه لاستنساخ الصوت بدقة.")


@router.message(VoiceWizard.audio, F.voice)
async def voice_audio(message: Message, state: FSMContext) -> None:
    await _accept_audio(
        message,
        state,
        file_id=message.voice.file_id,
        file_size=message.voice.file_size,
        mime_type=message.voice.mime_type or "audio/ogg",
        filename="voice.ogg",
    )


@router.message(VoiceWizard.audio, F.audio)
async def file_audio(message: Message, state: FSMContext) -> None:
    await _accept_audio(
        message,
        state,
        file_id=message.audio.file_id,
        file_size=message.audio.file_size,
        mime_type=message.audio.mime_type or "audio/mpeg",
        filename=message.audio.file_name,
    )


@router.message(VoiceWizard.audio, F.document)
async def document_audio(message: Message, state: FSMContext) -> None:
    mime = message.document.mime_type or ""
    if not mime.startswith("audio/"):
        await message.answer("أرسل ملفًا صوتيًا فقط.")
        return
    await _accept_audio(
        message,
        state,
        file_id=message.document.file_id,
        file_size=message.document.file_size,
        mime_type=mime,
        filename=message.document.file_name,
    )


@router.message(VoiceWizard.transcript, F.text)
async def voice_transcript(message: Message, state: FSMContext) -> None:
    database, store, _ = deps()
    transcript = (message.text or "").strip()
    if not transcript:
        await message.answer("أرسل النص الذي قيل في العينة.")
        return
    data = await state.get_data()
    try:
        profile = await store.save(
            name=str(data["name"]),
            audio=bytes(data["audio"]),
            reference_text=transcript,
            mime_type=str(data.get("mime_type") or "application/octet-stream"),
            filename=data.get("filename"),
        )
    except Exception:
        logger.exception("Failed to save reference voice")
        await message.answer("❌ تعذر حفظ الصوت. أعد المحاولة.", reply_markup=main_menu())
        await state.clear()
        return
    await database.set("voice.active_id", profile.voice_id)
    await database.event("voice.saved", {"voice_id": profile.voice_id, "name": profile.name})
    await state.clear()
    await message.answer(f"✅ تم حفظ <b>{escape(profile.name)}</b> وتعيينه كصوت حالي.", reply_markup=main_menu())


@router.callback_query(lambda q: q.data and q.data.startswith("voices:select:"))
async def select_voice(callback: CallbackQuery) -> None:
    database, store, _ = deps()
    voice_id = callback.data.rsplit(":", 1)[1]
    profile = await store.get(voice_id)
    if profile is None:
        await safe_callback_answer(callback, "الصوت غير موجود", show_alert=True)
        return
    await database.set("voice.active_id", voice_id)
    await safe_callback_answer(callback, "تم اختيار الصوت")
    await _show_voices(callback)


@router.callback_query(lambda q: q.data and q.data.startswith("voices:delete_confirm:"))
async def delete_confirm(callback: CallbackQuery) -> None:
    _, store, _ = deps()
    voice_id = callback.data.rsplit(":", 1)[1]
    profile = await store.get(voice_id)
    await safe_callback_answer(callback)
    if profile is None:
        await _show_voices(callback)
        return
    await safe_edit_text(
        callback.message,
        f"⚠️ حذف الصوت <b>{escape(profile.name)}</b> نهائيًا من الكنترولر؟",
        reply_markup=delete_voice_confirm_keyboard(voice_id),
    )


@router.callback_query(lambda q: q.data and q.data.startswith("voices:delete:"))
async def delete_voice(callback: CallbackQuery) -> None:
    database, store, _ = deps()
    voice_id = callback.data.rsplit(":", 1)[1]
    deleted = await store.delete(voice_id)
    if await database.get("voice.active_id") == voice_id:
        await database.set("voice.active_id", None)
    await database.event("voice.deleted", {"voice_id": voice_id, "deleted": deleted})
    await safe_callback_answer(callback, "تم الحذف" if deleted else "الصوت غير موجود")
    await _show_voices(callback)
