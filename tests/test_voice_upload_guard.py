import pytest

from voxpilot.bot.routers import voices
from voxpilot.services.audio_probe import ReferenceAudioTooLong


@pytest.mark.asyncio
async def test_long_upload_keeps_voice_wizard_on_audio_step():
    class Store:
        async def validate_audio(self, audio, mime_type, filename):
            raise ReferenceAudioTooLong(47.7)

    class Settings:
        telegram_max_voice_mb = 10

    class Bot:
        async def download(self, file_id, destination):
            destination.write(b"audio")

    class Message:
        bot = Bot()

        def __init__(self):
            self.replies = []

        async def answer(self, text, **kwargs):
            self.replies.append(text)

    class State:
        async def update_data(self, **kwargs):
            raise AssertionError("Invalid audio must not be stored in wizard state")

        async def set_state(self, state):
            raise AssertionError("Wizard must remain on audio step")

    voices.configure(object(), Store(), Settings())
    message = Message()
    await voices._accept_audio(
        message, State(), file_id="opaque", file_size=5,
        mime_type="audio/ogg", filename="sample.ogg",
    )

    assert len(message.replies) == 1
    assert "30 ثانية" in message.replies[0]


@pytest.mark.asyncio
async def test_select_default_clears_active_voice(monkeypatch):
    saved = []

    class Database:
        async def set(self, key, value):
            saved.append((key, value))

    async def acknowledge(callback, text):
        saved.append(("ack", text))

    async def show(callback):
        saved.append(("shown", True))

    monkeypatch.setattr(voices, "safe_callback_answer", acknowledge)
    monkeypatch.setattr(voices, "_show_voices", show)
    voices.configure(Database(), object(), object())
    await voices.select_default(object())

    assert saved[0] == ("voice.active_id", None)
    assert saved[-1] == ("shown", True)
