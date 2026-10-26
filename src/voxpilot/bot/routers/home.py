from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from voxpilot.bot.callbacks import safe_callback_answer, safe_edit_text
from voxpilot.bot.keyboards import main_menu
from voxpilot.bot.rich_ui import home_card

router = Router(name="home")

WELCOME = (
    "🎙 <b>VoxPilot</b>\n\n"
    "استنساخ وتحويل النص إلى صوت باستخدام Fish Audio S2 Pro.\n"
    "احفظ صوتًا، جهّز سيرفرًا، ثم أرسل النص مباشرة."
)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    try:
        await message.bot.send_rich_message(
            chat_id=message.chat.id,
            message_thread_id=message.message_thread_id,
            rich_message=home_card(),
            reply_markup=main_menu(),
        )
    except Exception:
        await message.answer(WELCOME, reply_markup=main_menu())


@router.callback_query(lambda q: q.data == "home")
async def home(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_callback_answer(callback)
    try:
        await callback.message.edit_text(rich_message=home_card(), reply_markup=main_menu())
    except Exception:
        await safe_edit_text(callback.message, WELCOME, reply_markup=main_menu())


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("تم إلغاء الخطوة الحالية. أصواتك وإعداداتك محفوظة.", reply_markup=main_menu())
