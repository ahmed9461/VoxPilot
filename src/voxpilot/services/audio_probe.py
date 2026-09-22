from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path


MAX_REFERENCE_SECONDS = 30.0


class ReferenceAudioError(ValueError):
    pass


class ReferenceAudioTooLong(ReferenceAudioError):
    def __init__(self, duration_seconds: float):
        self.duration_seconds = duration_seconds
        super().__init__(f"Reference audio exceeds {MAX_REFERENCE_SECONDS:g} seconds")


def inspect_reference_file(path: str | Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=codec_type:format=duration",
                "-of", "json", str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReferenceAudioError("Reference audio inspection is unavailable") from exc
    if result.returncode != 0:
        raise ReferenceAudioError("Reference audio could not be decoded")
    try:
        metadata = json.loads(result.stdout)
        if not metadata.get("streams"):
            raise ValueError("No audio stream")
        duration = float(metadata["format"]["duration"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ReferenceAudioError("Reference audio duration is unavailable") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ReferenceAudioError("Reference audio duration is invalid")
    if duration > MAX_REFERENCE_SECONDS:
        raise ReferenceAudioTooLong(duration)
    return duration


def inspect_reference_bytes(audio: bytes, extension: str, private_root: Path) -> float:
    private_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".probe-", dir=private_root) as directory:
        path = Path(directory) / f"reference.{extension}"
        path.write_bytes(audio)
        return inspect_reference_file(path)
