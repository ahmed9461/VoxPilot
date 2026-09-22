import pytest

from voxpilot.services.voice_store import VoiceStore, safe_extension


@pytest.mark.asyncio
async def test_voice_store_persists_and_deletes(tmp_path):
    store = VoiceStore(tmp_path / "voices")
    await store.init()
    profile = await store.save(
        name="My Voice",
        audio=b"fake-audio",
        reference_text="هذا هو النص",
        mime_type="audio/ogg",
        filename="../../unsafe.ogg",
    )
    assert len(profile.voice_id) == 16
    assert profile.extension == "ogg"
    loaded = await store.get(profile.voice_id)
    assert loaded is not None
    assert loaded.name == "My Voice"
    assert await store.read_audio(loaded) == b"fake-audio"
    assert len(await store.list()) == 1
    assert await store.delete(profile.voice_id) is True
    assert await store.get(profile.voice_id) is None


def test_safe_extension_does_not_trust_arbitrary_suffix():
    assert safe_extension("../../x.exe", "audio/ogg") == "ogg"
