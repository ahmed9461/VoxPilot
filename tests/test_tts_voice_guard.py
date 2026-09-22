import pytest

from voxpilot.bot.routers import tts
from voxpilot.db import Database
from voxpilot.domain import VoiceProfile
from voxpilot.services.audio_probe import ReferenceAudioTooLong
from voxpilot.services.tts_settings import ensure_defaults


@pytest.mark.asyncio
async def test_long_active_voice_is_rejected_before_fish_request(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    await db.init()
    await ensure_defaults(db)
    await db.set("voice.active_id", "a" * 16)
    profile = VoiceProfile("a" * 16, "Saved", "unused.ogg", "private transcript", "audio/ogg", "ogg", "now")

    class Store:
        async def get(self, voice_id):
            return profile

        async def validate_profile(self, item):
            raise ReferenceAudioTooLong(89.8)

    class Orchestrator:
        async def synthesize(self, *args, **kwargs):
            raise AssertionError("Fish must not receive an oversized reference")

    class Message:
        def __init__(self):
            self.replies = []

        async def answer(self, text, **kwargs):
            self.replies.append(text)

    tts.configure(Orchestrator(), db, Store())
    message = Message()
    await tts._generate(message, "مرحبا")

    assert len(message.replies) == 1
    assert "30 ثانية" in message.replies[0]
    assert "الصوت الافتراضي" in message.replies[0]
    assert "private transcript" not in message.replies[0]
