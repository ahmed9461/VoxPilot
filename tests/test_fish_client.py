import msgpack
import pytest

from voxpilot.domain import TTSSettings
from voxpilot.services.fish_client import build_tts_payload


def test_build_payload_matches_official_controls():
    settings = TTSSettings()
    payload = build_tts_payload("مرحبا", settings)
    assert payload["text"] == "مرحبا"
    assert payload["format"] == "mp3"
    assert payload["temperature"] == 0.8
    assert payload["top_p"] == 0.8
    assert payload["repetition_penalty"] == 1.1
    assert payload["chunk_length"] == 300
    assert payload["max_new_tokens"] == 1024
    assert payload["references"] == []
    packed = msgpack.packb(payload, use_bin_type=True)
    assert msgpack.unpackb(packed, raw=False)["text"] == "مرحبا"


def test_reference_audio_and_text_must_be_paired():
    with pytest.raises(ValueError):
        build_tts_payload("hello", TTSSettings(), reference_audio=b"abc")


def test_reference_is_embedded_without_rewrite():
    payload = build_tts_payload(
        "target",
        TTSSettings(),
        reference_audio=b"audio",
        reference_text="reference text",
    )
    assert payload["references"] == [{"audio": b"audio", "text": "reference text"}]
