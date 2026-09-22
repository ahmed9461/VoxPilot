from __future__ import annotations

import asyncio
import json
import re
import shutil
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from voxpilot.domain import VoiceProfile
from voxpilot.services.audio_probe import inspect_reference_bytes, inspect_reference_file


_SAFE_EXTENSIONS = {"wav", "mp3", "ogg", "opus", "m4a", "flac", "aac"}


def safe_extension(filename: str | None, mime_type: str | None) -> str:
    if filename:
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix in _SAFE_EXTENSIONS:
            return suffix
    by_mime = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/ogg": "ogg",
        "audio/opus": "opus",
        "audio/mp4": "m4a",
        "audio/x-m4a": "m4a",
        "audio/flac": "flac",
        "audio/aac": "aac",
    }
    return by_mime.get((mime_type or "").lower(), "ogg")


class VoiceStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self.root.chmod(0o700)
        except OSError:
            pass

    async def save(
        self,
        *,
        name: str,
        audio: bytes,
        reference_text: str,
        mime_type: str,
        filename: str | None = None,
    ) -> VoiceProfile:
        return await asyncio.to_thread(
            self._save_sync,
            name=name,
            audio=audio,
            reference_text=reference_text,
            mime_type=mime_type,
            filename=filename,
        )

    async def validate_audio(self, audio: bytes, mime_type: str, filename: str | None = None) -> float:
        extension = safe_extension(filename, mime_type)
        return await asyncio.to_thread(inspect_reference_bytes, audio, extension, self.root)

    async def validate_profile(self, profile: VoiceProfile) -> float:
        return await asyncio.to_thread(inspect_reference_file, profile.audio_path)

    def _save_sync(self, *, name: str, audio: bytes, reference_text: str, mime_type: str, filename: str | None) -> VoiceProfile:
        display_name = re.sub(r"\s+", " ", name).strip()
        transcript = reference_text.strip()
        if not display_name:
            raise ValueError("Voice name cannot be empty")
        if not audio:
            raise ValueError("Reference audio cannot be empty")
        if not transcript:
            raise ValueError("Reference text cannot be empty")
        extension = safe_extension(filename, mime_type)
        inspect_reference_bytes(audio, extension, self.root)
        voice_id = uuid.uuid4().hex[:16]
        directory = self.root / voice_id
        directory.mkdir(parents=False, exist_ok=False)
        audio_path = directory / f"reference.{extension}"
        audio_path.write_bytes(audio)
        profile = VoiceProfile(
            voice_id=voice_id,
            name=display_name,
            audio_path=str(audio_path),
            reference_text=transcript,
            mime_type=mime_type or "application/octet-stream",
            extension=extension,
            created_at=datetime.now(UTC).isoformat(),
        )
        metadata = asdict(profile)
        metadata["audio_path"] = audio_path.name
        (directory / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return profile

    async def get(self, voice_id: str) -> VoiceProfile | None:
        return await asyncio.to_thread(self._get_sync, voice_id)

    def _get_sync(self, voice_id: str) -> VoiceProfile | None:
        if not re.fullmatch(r"[0-9a-f]{16}", voice_id or ""):
            return None
        directory = self.root / voice_id
        meta_path = directory / "metadata.json"
        if not meta_path.is_file():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            audio_name = Path(str(data["audio_path"])).name
            audio_path = directory / audio_name
            if not audio_path.is_file():
                return None
            return VoiceProfile(
                voice_id=voice_id,
                name=str(data["name"]),
                audio_path=str(audio_path),
                reference_text=str(data["reference_text"]),
                mime_type=str(data["mime_type"]),
                extension=str(data["extension"]),
                created_at=str(data["created_at"]),
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    async def read_audio(self, profile: VoiceProfile) -> bytes:
        return await asyncio.to_thread(Path(profile.audio_path).read_bytes)

    async def list(self) -> list[VoiceProfile]:
        return await asyncio.to_thread(self._list_sync)

    def _list_sync(self) -> list[VoiceProfile]:
        if not self.root.exists():
            return []
        profiles = [self._get_sync(path.name) for path in self.root.iterdir() if path.is_dir()]
        return sorted(
            [profile for profile in profiles if profile is not None],
            key=lambda item: item.created_at,
            reverse=True,
        )

    async def delete(self, voice_id: str) -> bool:
        return await asyncio.to_thread(self._delete_sync, voice_id)

    def _delete_sync(self, voice_id: str) -> bool:
        if not re.fullmatch(r"[0-9a-f]{16}", voice_id or ""):
            return False
        directory = self.root / voice_id
        if not directory.is_dir():
            return False
        shutil.rmtree(directory)
        return True
