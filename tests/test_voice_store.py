import pytest
from io import BytesIO
import wave

from voxpilot.services.audio_probe import ReferenceAudioTooLong
from voxpilot.services.voice_store import VoiceStore, safe_extension


@pytest.mark.asyncio
async def test_voice_store_persists_and_deletes(tmp_path):
    store = VoiceStore(tmp_path / "voices")
    await store.init()
    buffer = BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 16000)
    audio = buffer.getvalue()
    profile = await store.save(
        name="My Voice",
        audio=audio,
        reference_text="هذا هو النص",
        mime_type="audio/wav",
        filename="../../unsafe.wav",
    )
    assert len(profile.voice_id) == 16
    assert profile.extension == "wav"
    loaded = await store.get(profile.voice_id)
    assert loaded is not None
    assert loaded.name == "My Voice"
    assert await store.read_audio(loaded) == audio
    assert 0.9 < await store.validate_profile(loaded) < 1.1
    assert len(await store.list()) == 1
    assert await store.delete(profile.voice_id) is True
    assert await store.get(profile.voice_id) is None


def test_safe_extension_does_not_trust_arbitrary_suffix():
    assert safe_extension("../../x.exe", "audio/ogg") == "ogg"


@pytest.mark.asyncio
async def test_voice_store_rejects_long_audio_without_creating_profile(tmp_path):
    store = VoiceStore(tmp_path / "voices")
    await store.init()
    buffer = BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes(b"\0\0" * (31 * 8000))

    with pytest.raises(ReferenceAudioTooLong):
        await store.save(
            name="Long",
            audio=buffer.getvalue(),
            reference_text="matching text",
            mime_type="audio/wav",
            filename="reference.wav",
        )

    assert await store.list() == []
    assert list(store.root.iterdir()) == []
