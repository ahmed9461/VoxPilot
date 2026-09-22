from __future__ import annotations

import shlex
from typing import Any

from voxpilot.config import Settings


def extract_instance_id(result: dict[str, Any]) -> int | None:
    for key in ("new_contract", "instance_id", "id"):
        value = result.get(key)
        if value:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    for key in ("instance", "contract", "result"):
        nested = result.get(key)
        if isinstance(nested, dict):
            found = extract_instance_id(nested)
            if found:
                return found
    return None


def fish_url(settings: Settings, public_ip: str, mapped_port: int) -> str:
    scheme = "https" if settings.fish_use_https else "http"
    return f"{scheme}://{public_ip}:{mapped_port}"


def build_vast_env(settings: Settings, fish_token: str) -> str:
    values = {
        "VOXPILOT_FISH_TOKEN": fish_token,
        "FISH_API_PORT": str(settings.fish_api_port),
        "FISH_SPEECH_REPO_URL": settings.fish_speech_repo_url,
        "FISH_SPEECH_REF": settings.fish_speech_ref,
        "FISH_MODEL_REPO": settings.fish_model_repo,
        "FISH_UV_EXTRA": settings.fish_uv_extra,
        "FISH_COMPILE": "1" if settings.fish_compile else "0",
        "FISH_HALF": "1" if settings.fish_half else "0",
        "HF_HOME": "/workspace/hf-cache",
        "HF_TOKEN": settings.hf_token,
    }
    parts = [f"-e {shlex.quote(f'{key}={value}')}" for key, value in values.items() if value != ""]
    parts.append(f"-p {settings.fish_api_port}:{settings.fish_api_port}")
    return " ".join(parts)


def build_onstart_cmd(settings: Settings) -> str | None:
    if not settings.voxpilot_repo_url:
        return None
    root = "/workspace/VoxPilot"
    repo = shlex.quote(settings.voxpilot_repo_url)
    ref = shlex.quote(settings.voxpilot_repo_ref)
    return (
        f"if [ ! -d {root}/.git ]; then "
        f"git clone --depth 1 --branch {ref} {repo} {root}; "
        f"else git -C {root} fetch --depth 1 origin {ref} && git -C {root} reset --hard FETCH_HEAD; fi; "
        f"nohup bash {root}/scripts/bootstrap_vast.sh > /workspace/voxpilot-bootstrap.log 2>&1 &"
    )
