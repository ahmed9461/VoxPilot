from __future__ import annotations

import logging
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

_STALE = ("query is too old", "query id is invalid", "response timeout expired")
_NOT_MODIFIED = ("message is not modified", "message not modified")


async def safe_callback_answer(callback: CallbackQuery, text: str | None = None, *, show_alert: bool = False) -> bool:
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as exc:
        if any(marker in str(exc).lower() for marker in _STALE):
            logger.info("Ignoring expired callback: %s", exc)
            return False
        raise


async def safe_edit_text(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = None,
) -> bool:
    kwargs: dict[str, Any] = {"reply_markup": reply_markup}
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode
    try:
        await message.edit_text(text, **kwargs)
        return True
    except TelegramBadRequest as exc:
        if any(marker in str(exc).lower() for marker in _NOT_MODIFIED):
            return False
        raise
