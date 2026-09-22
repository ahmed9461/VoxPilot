from __future__ import annotations

from dataclasses import dataclass

from voxpilot.config import Settings


@dataclass(slots=True, frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def run_local_preflight(settings: Settings) -> list[Check]:
    return [
        Check("Telegram token", bool(settings.telegram_bot_token), "configured" if settings.telegram_bot_token else "missing"),
        Check("Owner Telegram ID", settings.owner_telegram_id > 0, str(settings.owner_telegram_id or "missing")),
        Check("Vast API key", bool(settings.vast_api_key), "configured" if settings.vast_api_key else "missing"),
        Check("Vast disk", settings.vast_disk_gb >= 40, f"{settings.vast_disk_gb} GB"),
        Check("GPU VRAM policy", settings.vast_min_gpu_ram_gb >= 24, f">= {settings.vast_min_gpu_ram_gb} GB"),
        Check("VoxPilot bootstrap source", bool(settings.voxpilot_repo_url or settings.vast_template_hash), "configured" if settings.voxpilot_repo_url or settings.vast_template_hash else "missing"),
        Check("Fish source pin", len(settings.fish_speech_ref) >= 7, settings.fish_speech_ref),
    ]
