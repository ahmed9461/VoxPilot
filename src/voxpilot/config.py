from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


FISH_PIN = "214da3cd841bda85da2496b96cd3c4d7edb1337e"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = ""
    owner_telegram_id: int = 0
    database_path: Path = Path("./data/voxpilot.sqlite3")
    voice_data_dir: Path = Path("./data/voices")
    log_level: str = "INFO"
    telegram_max_voice_mb: int = 25

    vast_api_key: str = ""
    vast_template_hash: str | None = None
    vast_docker_image: str = "vastai/pytorch:@vastai-automatic-tag"
    vast_disk_gb: int = 60
    vast_min_gpu_ram_gb: int = 24
    vast_min_reliability: float = 0.98
    vast_max_price_usd_hour: float = 0.50
    vast_default_limit: int = 8
    vast_verified_only: bool = True
    vast_datacenter_only: bool = False
    vast_min_direct_ports: int = 1
    vast_min_inet_down_mbps: float = 100.0
    vast_cancel_unavailable: bool = True
    vast_auto_destroy_on_provision_failure: bool = False

    voxpilot_repo_url: str = "https://github.com/ahmed9461/VoxPilot.git"
    voxpilot_repo_ref: str = "main"

    fish_speech_repo_url: str = "https://github.com/fishaudio/fish-speech.git"
    fish_speech_ref: str = FISH_PIN
    fish_model_repo: str = "fishaudio/s2-pro"
    fish_uv_extra: str = "cu126"
    fish_api_port: int = 8080
    fish_compile: bool = False
    fish_half: bool = False
    fish_use_https: bool = False
    fish_verify_tls: bool = False
    fish_request_timeout_seconds: int = 600
    fish_ready_timeout_seconds: int = 1800
    provision_poll_seconds: float = 5.0
    hf_token: str = ""

    cost_guard_warn_minutes: int = 30
    cost_guard_auto_destroy_minutes: int = 0
    cost_guard_poll_seconds: int = 60

    @field_validator("owner_telegram_id")
    @classmethod
    def owner_not_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("OWNER_TELEGRAM_ID must be >= 0")
        return value

    @field_validator("vast_min_reliability")
    @classmethod
    def reliability_range(cls, value: float) -> float:
        if not 0 < value <= 1:
            raise ValueError("VAST_MIN_RELIABILITY must be > 0 and <= 1")
        return value

    @field_validator("vast_max_price_usd_hour", "provision_poll_seconds")
    @classmethod
    def positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator(
        "telegram_max_voice_mb",
        "vast_disk_gb",
        "vast_min_gpu_ram_gb",
        "vast_default_limit",
        "vast_min_direct_ports",
        "fish_api_port",
        "fish_request_timeout_seconds",
        "fish_ready_timeout_seconds",
    )
    @classmethod
    def positive_int(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be > 0")
        return value

    @field_validator("vast_min_gpu_ram_gb")
    @classmethod
    def fish_vram_floor(cls, value: int) -> int:
        if value < 24:
            raise ValueError("VAST_MIN_GPU_RAM_GB must be >= 24 for the supported Fish S2 Pro profile")
        return value

    @field_validator("vast_disk_gb")
    @classmethod
    def fish_disk_floor(cls, value: int) -> int:
        if value < 40:
            raise ValueError("VAST_DISK_GB must be >= 40 for Fish S2 Pro runtime and caches")
        return value

    @field_validator("fish_uv_extra")
    @classmethod
    def supported_cuda_extra(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"cu126", "cu128", "cu129"}:
            raise ValueError("FISH_UV_EXTRA must be cu126, cu128, or cu129")
        return normalized

    def validate_runtime(self) -> None:
        missing: list[str] = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.owner_telegram_id:
            missing.append("OWNER_TELEGRAM_ID")
        if not self.vast_api_key:
            missing.append("VAST_API_KEY")
        if missing:
            raise RuntimeError("Missing required settings: " + ", ".join(missing))

    def validate_rent_ready(self) -> None:
        if not self.voxpilot_repo_url and not self.vast_template_hash:
            raise RuntimeError("Cannot rent until VOXPILOT_REPO_URL or VAST_TEMPLATE_HASH is configured")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
