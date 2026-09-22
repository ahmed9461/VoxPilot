from __future__ import annotations

from typing import Any

import httpx
import msgpack

from voxpilot.domain import TTSSettings


class FishClientError(RuntimeError):
    pass


def build_tts_payload(
    text: str,
    settings: TTSSettings,
    *,
    reference_audio: bytes | None = None,
    reference_text: str | None = None,
) -> dict[str, Any]:
    references: list[dict[str, Any]] = []
    if reference_audio is not None or reference_text is not None:
        if not reference_audio or not reference_text or not reference_text.strip():
            raise ValueError("Reference audio and matching reference text must be provided together")
        references.append({"audio": reference_audio, "text": reference_text.strip()})
    return {
        "text": text,
        "references": references,
        "reference_id": None,
        "format": settings.format,
        "latency": "normal",
        "max_new_tokens": settings.max_new_tokens,
        "chunk_length": settings.chunk_length,
        "top_p": settings.top_p,
        "repetition_penalty": settings.repetition_penalty,
        "temperature": settings.temperature,
        "streaming": False,
        "use_memory_cache": "off",
        "seed": settings.seed,
        "normalize": settings.normalize,
    }


class FishClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        verify_tls: bool = False,
        timeout_seconds: int = 600,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.verify_tls = verify_tls
        self.timeout_seconds = timeout_seconds

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def is_ready(self) -> bool:
        try:
            async with httpx.AsyncClient(verify=self.verify_tls, timeout=15) as client:
                response = await client.get(f"{self.base_url}/v1/health", headers=self._headers)
            return response.status_code == 200 and response.json().get("status") == "ok"
        except Exception:
            return False

    async def synthesize(
        self,
        text: str,
        settings: TTSSettings,
        *,
        reference_audio: bytes | None = None,
        reference_text: str | None = None,
    ) -> bytes:
        payload = build_tts_payload(
            text,
            settings,
            reference_audio=reference_audio,
            reference_text=reference_text,
        )
        body = msgpack.packb(payload, use_bin_type=True)
        headers = {**self._headers, "Content-Type": "application/msgpack"}
        try:
            async with httpx.AsyncClient(
                verify=self.verify_tls,
                timeout=httpx.Timeout(self.timeout_seconds),
            ) as client:
                response = await client.post(
                    f"{self.base_url}/v1/tts",
                    params={"format": "msgpack"},
                    content=body,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise FishClientError(f"Fish request failed: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise FishClientError(f"Fish TTS returned HTTP {response.status_code}")
        if not response.content:
            raise FishClientError("Fish TTS returned an empty audio response")
        return response.content
