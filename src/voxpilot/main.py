from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from voxpilot.bot.middleware import OwnerOnlyMiddleware
from voxpilot.bot.routers import home, servers, settings as tts_settings_router, tts, voices
from voxpilot.config import get_settings
from voxpilot.db import Database
from voxpilot.services.cost_guard import cost_guard_loop
from voxpilot.services.orchestrator import Orchestrator
from voxpilot.services.tts_settings import ensure_defaults
from voxpilot.services.vast_gateway import VastSdkGateway
from voxpilot.services.voice_store import VoiceStore


async def main() -> None:
    settings = get_settings()
    settings.validate_runtime()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db = Database(settings.database_path)
    await db.init()
    await ensure_defaults(db)
    store = VoiceStore(settings.voice_data_dir)
    await store.init()

    vast = VastSdkGateway(settings.vast_api_key, fish_api_port=settings.fish_api_port)
    orchestrator = Orchestrator(settings, db, vast)

    servers.configure(orchestrator)
    voices.configure(db, store, settings)
    tts_settings_router.configure(db)
    tts.configure(orchestrator, db, store)

    bot = Bot(settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(OwnerOnlyMiddleware(settings.owner_telegram_id))

    dp.include_router(home.router)
    dp.include_router(servers.router)
    dp.include_router(voices.router)
    dp.include_router(tts_settings_router.router)
    # Keep direct text-to-speech last so wizard/settings text handlers win first.
    dp.include_router(tts.router)

    recovery_task = asyncio.create_task(orchestrator.recover_current(), name="voxpilot-recovery")
    guard_task = asyncio.create_task(cost_guard_loop(bot, settings, db, orchestrator), name="voxpilot-cost-guard")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in (recovery_task, guard_task):
            task.cancel()
        await asyncio.gather(recovery_task, guard_task, return_exceptions=True)
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
