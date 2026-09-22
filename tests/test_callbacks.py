import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import AnswerCallbackQuery, EditMessageText

from voxpilot.bot.callbacks import safe_callback_answer, safe_edit_text
from voxpilot.bot.keyboards import voices_keyboard


class StaleCallback:
    async def answer(self, **kwargs):
        raise TelegramBadRequest(
            AnswerCallbackQuery(callback_query_id="old"),
            "Bad Request: query is too old and response timeout expired",
        )


class UnchangedMessage:
    async def edit_text(self, text, **kwargs):
        raise TelegramBadRequest(
            EditMessageText(chat_id=1, message_id=1, text=text),
            "Bad Request: message is not modified",
        )


@pytest.mark.asyncio
async def test_expired_callback_is_acknowledged_safely():
    assert await safe_callback_answer(StaleCallback()) is False


@pytest.mark.asyncio
async def test_unchanged_callback_screen_is_safe():
    assert await safe_edit_text(UnchangedMessage(), "same screen") is False


def test_voice_menu_can_select_default_voice():
    keyboard = voices_keyboard([], "a" * 16)
    assert keyboard.inline_keyboard[0][0].callback_data == "voices:default"
