import pytest

from voxpilot.services.tts_settings import (
    EMOTION_TAGS,
    compose_performance_text,
    normalize_stage_directions,
)


def test_normal_does_not_modify_text():
    assert compose_performance_text("النص المطلوب", "normal") == "النص المطلوب"


def test_emotion_prepends_native_tag_only():
    assert compose_performance_text("النص المطلوب", "whisper") == "[whisper] النص المطلوب"
    assert EMOTION_TAGS["angry"][1] == "[angry]"


def test_unknown_emotion_is_rejected():
    with pytest.raises(ValueError):
        compose_performance_text("hello", "invented")


@pytest.mark.parametrize(
    ("direction", "tag"),
    [
        ("تتنهد بهدوء", "sigh"),
        ("تضحك", "laughing"),
        ("تضحك بخفة", "chuckle"),
        ("تأخذ نفسًا", "inhale"),
        ("تزفر", "exhale"),
        ("تلهث", "panting"),
        ("تهمس", "whisper"),
        ("تصرخ", "screaming"),
        ("ترفع صوتها", "shouting"),
        ("تتوقف قليلًا", "short pause"),
        ("تتنحنح", "clearing throat"),
        ("تتأوه", "moaning"),
    ],
)
def test_common_arabic_stage_directions_prefer_documented_native_tags(direction, tag):
    assert normalize_stage_directions(f"({direction}) النص") == f"[{tag}] النص"


def test_direction_alias_matching_ignores_arabic_diacritics_and_spacing():
    assert normalize_stage_directions("(  تَأْخُذُ   نَفَسًا  ) النص") == "[inhale] النص"


def test_unknown_complex_direction_remains_free_form():
    text = "(بصوت متردد وكأنه يحاول ألا يبكي) أهلًا"
    assert normalize_stage_directions(text) == "[بصوت متردد وكأنه يحاول ألا يبكي] أهلًا"


def test_multiple_stage_directions_convert_independently():
    text = "(تتردد قليلًا) مرحبًا... (تضحك بخفة) أخيرًا شفتك"
    assert normalize_stage_directions(text) == "[تتردد قليلًا] مرحبًا... [chuckle] أخيرًا شفتك"


def test_existing_manual_fish_tags_are_preserved():
    assert normalize_stage_directions("[laughing] hello") == "[laughing] hello"


def test_non_direction_parentheses_stay_literal():
    assert normalize_stage_directions("الإصدار (2026) جاهز") == "الإصدار (2026) جاهز"
    assert normalize_stage_directions("() نص") == "() نص"
    assert normalize_stage_directions("(تتنهد\nبهدوء) نص") == "(تتنهد\nبهدوء) نص"
    assert normalize_stage_directions("(تتنهد نص") == "(تتنهد نص"


def test_global_emotion_and_stage_direction_work_together():
    assert compose_performance_text("(بصوت متردد) أهلًا", "sad") == "[sad] [بصوت متردد] أهلًا"


def test_full_width_parentheses_are_supported():
    assert normalize_stage_directions("（تضحك بخفة） أهلًا") == "[chuckle] أهلًا"
