from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Literal


class InstancePhase(StrEnum):
    NONE = "none"
    RENTING = "renting"
    BOOTING = "booting"
    PROVISIONING = "provisioning"
    READY = "ready"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DESTROYING = "destroying"
    ERROR = "error"


@dataclass(slots=True, frozen=True)
class GpuOffer:
    offer_id: int
    gpu_name: str
    gpu_ram_gb: float
    price_per_hour: float
    reliability: float | None
    dlperf: float | None
    location: str | None = None
    inet_down_mbps: float | None = None
    disk_space_gb: float | None = None
    verified: bool | None = None
    raw: dict[str, Any] | None = None

    @property
    def display_name(self) -> str:
        rel = "?" if self.reliability is None else f"{self.reliability * 100:.1f}%"
        return f"{self.gpu_name} • {self.gpu_ram_gb:.0f}GB • ${self.price_per_hour:.3f}/h • R {rel}"

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw", None)
        return data


@dataclass(slots=True, frozen=True)
class InstanceRef:
    instance_id: int
    status: str
    public_ip: str | None = None
    mapped_port: int | None = None
    raw: dict[str, Any] | None = None


AudioFormat = Literal["wav", "mp3", "opus"]


@dataclass(slots=True, frozen=True)
class TTSSettings:
    emotion_key: str = "normal"
    format: AudioFormat = "mp3"
    temperature: float = 0.8
    top_p: float = 0.8
    repetition_penalty: float = 1.1
    chunk_length: int = 300
    max_new_tokens: int = 1024
    normalize: bool = True
    seed: int | None = None


@dataclass(slots=True, frozen=True)
class VoiceProfile:
    voice_id: str
    name: str
    audio_path: str
    reference_text: str
    mime_type: str
    extension: str
    created_at: str
