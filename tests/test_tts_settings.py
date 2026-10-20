import pytest
from dataclasses import asdict

from voxpilot.db import Database
from voxpilot.domain import TTSSettings
from voxpilot.services.fish_client import build_tts_payload

from voxpilot.services.tts_settings import (
    EMOTION_TAGS,
    compose_performance_text,
    ensure_defaults,
    load_tts_settings,
    normalize_stage_directions,
    set_tts_value,
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


@pytest.mark.parametrize("text", [
    "(outer (sigh) text)",
    "(outer (sigh)",
    "（outer (sigh) text）",
    "(outer （sigh） text)",
    "(outer\n(sigh) text)",
    "（mismatched)",
    "[whisper (very quietly)] hello",
    "[whisper （very quietly）] hello",
    "([sigh]) hello",
])
def test_nested_malformed_and_manual_tag_regions_remain_literal(text):
    assert normalize_stage_directions(text) == text


def test_protected_regions_do_not_block_independent_directions():
    text = "[whisper (quietly)] (inhale) hello (outer (sigh)) （exhale）"
    assert normalize_stage_directions(text) == "[whisper (quietly)] [inhale] hello (outer (sigh)) [exhale]"


@pytest.mark.asyncio
async def test_legacy_upgrade_preserves_effective_controls_and_voice(tmp_path):
    database = Database(tmp_path / "legacy.sqlite3")
    await database.init()
    legacy = asdict(TTSSettings(temperature=0.9, top_p=0.6, seed=123, emotion_key="sad"))
    legacy.pop("stability_mode")
    saved = {f"tts.{key}": value for key, value in legacy.items()}
    saved["voice.active_id"] = "existing-voice"
    await database.set_many(saved)

    # The fallback must be safe even before startup initializes missing keys.
    assert (await load_tts_settings(database)).stability_mode is False
    await ensure_defaults(database)
    settings = await load_tts_settings(database)
    assert settings.stability_mode is False
    payload = build_tts_payload("hello", settings)
    assert (payload["temperature"], payload["top_p"], payload["seed"]) == (0.9, 0.6, 123)
    assert await database.get_many(saved) == saved

    await set_tts_value(database, "stability_mode", True)
    # A new Database object models the settings path after a controller restart.
    restarted = Database(database.path)
    await ensure_defaults(restarted)
    settings = await load_tts_settings(restarted)
    assert settings.stability_mode is True
    payload = build_tts_payload("hello", settings)
    assert (payload["temperature"], payload["top_p"], payload["seed"]) == (0.6, 0.7, 42)
    await set_tts_value(restarted, "stability_mode", False)
    await ensure_defaults(restarted)
    assert await database.get_many(saved) == saved
    assert (await load_tts_settings(restarted)).stability_mode is False


@pytest.mark.asyncio
async def test_fresh_install_persists_default_on_stability(tmp_path):
    database = Database(tmp_path / "fresh.sqlite3")
    await database.init()
    assert (await load_tts_settings(database)).stability_mode is True
    await ensure_defaults(database)
    await ensure_defaults(database)
    assert await database.get("tts.stability_mode") is True
