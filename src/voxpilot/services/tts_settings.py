from __future__ import annotations

from dataclasses import asdict
import re
import unicodedata

from voxpilot.db import Database
from voxpilot.domain import TTSSettings


EMOTION_TAGS: dict[str, tuple[str, str]] = {
    "normal": ("عادي", ""),
    "excited": ("متحمس", "[excited]"),
    "delight": ("سعيد", "[delight]"),
    "sad": ("حزين", "[sad]"),
    "angry": ("غاضب", "[angry]"),
    "whisper": ("همس", "[whisper]"),
    "low_voice": ("صوت منخفض", "[low voice]"),
    "shouting": ("صوت مرتفع", "[shouting]"),
    "surprised": ("مندهش", "[surprised]"),
    "laughing": ("ضاحك", "[laughing]"),
    "singing": ("غناء", "[singing]"),
}

# VoxPilot consistency preset. These values use only Fish-native request
# controls and are a product choice, not Fish defaults.
STABILITY_TEMPERATURE = 0.6
STABILITY_TOP_P = 0.7
STABILITY_SEED = 42

DEFAULTS = TTSSettings()

_PAREN_PAIRS = {"(": ")", "（": "）"}


def _direction_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    normalized = without_marks.replace("ـ", "").replace("ى", "ي").casefold()
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.strip(" .،,!؟?؛;:…")


_NATIVE_DIRECTION_ALIASES: dict[str, str] = {
    _direction_key(alias): tag
    for alias, tag in {
        "تتنهد": "sigh",
        "تنهد": "sigh",
        "تنهيدة": "sigh",
        "تتنهد بهدوء": "sigh",
        "تنهد بهدوء": "sigh",
        "تضحك": "laughing",
        "يضحك": "laughing",
        "ضحك": "laughing",
        "تضحك بخفة": "chuckle",
        "يضحك بخفة": "chuckle",
        "ضحكة خفيفة": "chuckle",
        "تأخذ نفسًا": "inhale",
        "يأخذ نفسًا": "inhale",
        "شهيق": "inhale",
        "تستنشق": "inhale",
        "تزفر": "exhale",
        "يزفر": "exhale",
        "زفير": "exhale",
        "تلهث": "panting",
        "يلهث": "panting",
        "لهث": "panting",
        "تهمس": "whisper",
        "يهمس": "whisper",
        "همس": "whisper",
        "بصوت هامس": "whisper",
        "تصرخ": "screaming",
        "يصرخ": "screaming",
        "صراخ": "screaming",
        "ترفع صوتها": "shouting",
        "يرفع صوته": "shouting",
        "بصوت مرتفع": "shouting",
        "تتوقف": "pause",
        "يتوقف": "pause",
        "توقف": "pause",
        "تتوقف قليلًا": "short pause",
        "يتوقف قليلًا": "short pause",
        "توقف قصير": "short pause",
        "صمت قصير": "short pause",
        "تتنحنح": "clearing throat",
        "يتنحنح": "clearing throat",
        "تنحنح": "clearing throat",
        "تنظف حلقها": "clearing throat",
        "ينظف حلقه": "clearing throat",
        "تتأوه": "moaning",
        "يتأوه": "moaning",
        "تأوه": "moaning",
    }.items()
}


def normalize_stage_directions(text: str) -> str:
    parts: list[str] = []
    closers: list[str] = []
    square_depth = 0
    start = last = 0
    nested_or_mismatched = False
    for index, char in enumerate(text):
        # Manual Fish tags are opaque, including any parentheses inside them.
        if not closers and (square_depth or char == "["):
            if char == "[":
                square_depth += 1
            elif char == "]":
                square_depth -= 1
            continue
        if char in _PAREN_PAIRS:
            if not closers:
                start = index
                nested_or_mismatched = False
            else:
                nested_or_mismatched = True
            closers.append(_PAREN_PAIRS[char])
        elif char in _PAREN_PAIRS.values() and closers:
            if char != closers.pop():
                nested_or_mismatched = True
            if closers:
                continue
            raw = text[start + 1:index]
            if (nested_or_mismatched or not 1 <= len(raw) <= 200
                    or any(mark in raw for mark in "\r\n[]")):
                continue
            direction = raw.strip()
            if not any(letter.isalpha() for letter in direction):
                continue
            native_tag = _NATIVE_DIRECTION_ALIASES.get(_direction_key(direction))
            parts.extend((text[last:start], f"[{native_tag or direction}]"))
            last = index + 1
    parts.append(text[last:])
    return "".join(parts)


def effective_sampling_controls(settings: TTSSettings) -> tuple[float, float, int | None]:
    if settings.stability_mode:
        return STABILITY_TEMPERATURE, STABILITY_TOP_P, STABILITY_SEED
    return settings.temperature, settings.top_p, settings.seed


_KEYS = {
    "emotion_key": "tts.emotion_key",
    "format": "tts.format",
    "temperature": "tts.temperature",
    "top_p": "tts.top_p",
    "repetition_penalty": "tts.repetition_penalty",
    "chunk_length": "tts.chunk_length",
    "max_new_tokens": "tts.max_new_tokens",
    "normalize": "tts.normalize",
    "seed": "tts.seed",
    "stability_mode": "tts.stability_mode",
}


def _defaults_for(current: dict) -> dict:
    defaults = asdict(DEFAULTS)
    # An existing installation must keep its effective sampling behavior until
    # the owner explicitly enables the new consistency preset.
    if current:
        defaults["stability_mode"] = False
    return defaults


async def ensure_defaults(db: Database) -> None:
    current = await db.get_many(_KEYS.values())
    defaults = _defaults_for(current)
    missing = {_KEYS[field]: value for field, value in defaults.items() if _KEYS[field] not in current}
    if missing:
        await db.set_many(missing)


async def load_tts_settings(db: Database) -> TTSSettings:
    rows = await db.get_many(_KEYS.values())
    defaults = _defaults_for(rows)
    values = {field: rows.get(key, defaults[field]) for field, key in _KEYS.items()}
    return TTSSettings(**values)


async def set_tts_value(db: Database, field: str, value) -> TTSSettings:
    if field not in _KEYS:
        raise ValueError(f"Unknown TTS setting: {field}")
    candidate = asdict(await load_tts_settings(db))
    candidate[field] = value
    validated = TTSSettings(**candidate)
    _validate(validated)
    await db.set(_KEYS[field], getattr(validated, field))
    return validated


def _validate(settings: TTSSettings) -> None:
    if settings.emotion_key not in EMOTION_TAGS:
        raise ValueError("Unsupported emotion")
    if settings.format not in {"wav", "mp3", "opus"}:
        raise ValueError("Unsupported output format")
    if not 0.1 <= settings.temperature <= 1.0:
        raise ValueError("temperature must be between 0.1 and 1.0")
    if not 0.1 <= settings.top_p <= 1.0:
        raise ValueError("top_p must be between 0.1 and 1.0")
    if not 0.9 <= settings.repetition_penalty <= 2.0:
        raise ValueError("repetition_penalty must be between 0.9 and 2.0")
    if not 100 <= settings.chunk_length <= 1000:
        raise ValueError("chunk_length must be between 100 and 1000")
    if settings.max_new_tokens < 1:
        raise ValueError("max_new_tokens must be positive")
    if not isinstance(settings.stability_mode, bool):
        raise ValueError("stability_mode must be boolean")


def compose_performance_text(text: str, emotion_key: str) -> str:
    clean = text.strip()
    if not clean:
        raise ValueError("Text cannot be empty")
    if emotion_key not in EMOTION_TAGS:
        raise ValueError("Unsupported emotion")
    prepared = normalize_stage_directions(clean)
    tag = EMOTION_TAGS[emotion_key][1]
    return f"{tag} {prepared}" if tag else prepared
