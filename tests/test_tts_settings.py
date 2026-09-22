import pytest

from voxpilot.services.tts_settings import EMOTION_TAGS, compose_performance_text


def test_normal_does_not_modify_text():
    assert compose_performance_text("النص المطلوب", "normal") == "النص المطلوب"


def test_emotion_prepends_native_tag_only():
    assert compose_performance_text("النص المطلوب", "whisper") == "[whisper] النص المطلوب"
    assert EMOTION_TAGS["angry"][1] == "[angry]"


def test_unknown_emotion_is_rejected():
    with pytest.raises(ValueError):
        compose_performance_text("hello", "invented")
