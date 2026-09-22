from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from voxpilot.bot.callbacks import safe_callback_answer
from voxpilot.bot.keyboards import main_menu
from voxpilot.db import Database
from voxpilot.services.orchestrator import Orchestrator
from voxpilot.services.tts_settings import compose_performance_text, load_tts_settings
from voxpilot.services.voice_store import VoiceStore

logger = logging.getLogger(__name__)
router = Router(name="tts")
_orch: Orchestrator | None = None
_db: Database | None = None
_store: VoiceStore | None = None


class GenerateState(StatesGroup):
    text = State()


def configure(orchestrator: Orchestrator, db: Database, store: VoiceStore) -> None:
    global _orch, _db, _store
    _orch, _db, _store = orchestrator, db, store


def deps() -> tuple[Orchestrator, Database, VoiceStore]:
    if _orch is None or _db is None or _store is None:
        raise RuntimeError("TTS router is not configured")
    return _orch, _db, _store


@router.callback_query(lambda q: q.data == "tts:generate")
async def generate_prompt(callback: CallbackQuery, state: FSMContext) -> None:
    await safe_callback_answer(callback)
    await state.set_state(GenerateState.text)
    await callback.message.edit_text("📝 أرسل النص الذي تريد تحويله إلى صوت. يمكنك وضع وسوم Fish داخل النص يدويًا أيضًا.")


@router.message(GenerateState.text, F.text)
async def generate_from_prompt(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    await state.clear()
    await _generate(message, text)


@router.message(F.text)
async def direct_text(message: Message, state: FSMContext) -> None:
    if await state.get_state() is not None:
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    await _generate(message, text)


async def _generate(message: Message, text: str) -> None:
    orchestrator, database, store = deps()
    if not text:
        await message.answer("أرسل نصًا غير فارغ.")
        return
    settings = await load_tts_settings(database)
    try:
        final_text = compose_performance_text(text, settings.emotion_key)
    except ValueError:
        await message.answer("النص أو إعداد المشاعر غير صالح.")
        return

    reference_audio = None
    reference_text = None
    active_id = await database.get("voice.active_id")
    if active_id:
        profile = await store.get(str(active_id))
        if profile is not None:
            try:
                reference_audio = await store.read_audio(profile)
                reference_text = profile.reference_text
            except OSError:
                logger.exception("Active voice audio is missing")

    status = await message.answer("🎙 جاري توليد الصوت...")
    try:
        audio = await orchestrator.synthesize(
            final_text,
            settings,
            reference_audio=reference_audio,
            reference_text=reference_text,
        )
    except Exception:
        logger.exception("TTS generation failed")
        await status.edit_text("❌ تعذر توليد الصوت. تأكد أن السيرفر جاهز ثم أعد المحاولة.", reply_markup=main_menu())
        return

    filename = f"voxpilot.{settings.format}"
    file = BufferedInputFile(audio, filename=filename)
    try:
        if settings.format == "mp3":
            await message.answer_audio(file, title="VoxPilot")
        elif settings.format == "opus":
            await message.answer_voice(file)
        else:
            await message.answer_document(file, caption="🎙 VoxPilot")
        await status.delete()
    except Exception:
        logger.exception("Telegram audio delivery failed")
        await status.edit_text("❌ تم التوليد لكن تعذر إرسال الملف الصوتي.", reply_markup=main_menu())
