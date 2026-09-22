from __future__ import annotations

from dataclasses import asdict

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

DEFAULTS = TTSSettings()
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
}


async def ensure_defaults(db: Database) -> None:
    current = await db.get_many(_KEYS.values())
    defaults = asdict(DEFAULTS)
    missing = {_KEYS[field]: value for field, value in defaults.items() if _KEYS[field] not in current}
    if missing:
        await db.set_many(missing)


async def load_tts_settings(db: Database) -> TTSSettings:
    rows = await db.get_many(_KEYS.values())
    defaults = asdict(DEFAULTS)
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


def compose_performance_text(text: str, emotion_key: str) -> str:
    clean = text.strip()
    if not clean:
        raise ValueError("Text cannot be empty")
    if emotion_key not in EMOTION_TAGS:
        raise ValueError("Unsupported emotion")
    tag = EMOTION_TAGS[emotion_key][1]
    return f"{tag} {clean}" if tag else clean
