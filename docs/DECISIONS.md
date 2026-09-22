# VoxPilot — Decisions

## 2026-09-22 — PixelPilot is a reference, not a clone

Reuse only the parts of PixelPilot that solve the same operational problem: Vast search/lifecycle/recovery, stale-offer protection, billing, Cost Guard, owner-only middleware, safe Telegram callbacks, Rich Messages, and project-state discipline.

Do not carry over Qwen, vLLM, Whisper, chat history, prompt profiles, assistant personalities, image/video understanding, or unrelated migration logic.

Reason: VoxPilot is a focused TTS product and unnecessary copied layers would make it heavier and harder to maintain.

## 2026-09-22 — Use the official Fish API directly

Do not build a VoxPilot inference gateway in front of Fish.

The official Fish server already provides:
- `GET /v1/health`
- `POST /v1/tts`
- bearer authentication via `--api-key`

The controller talks directly to the mapped Fish API port.

Reason: fewer processes, fewer dependencies, fewer failure points, and less custom protocol code.

## 2026-09-22 — Pin Fish upstream source

Use Fish Speech source commit:

`214da3cd841bda85da2496b96cd3c4d7edb1337e`

Do not deploy from a floating `main` by default.

Reason: temporary servers must remain reproducible. Upstream upgrades should be deliberate and validated.

## 2026-09-22 — Keep voice references on the controller

Saved voices persist on the durable controller as audio + exact transcript + metadata.

Each synthesis request sends the active reference to the Fish API.

Reason: Vast instances are disposable and may be deleted after a short test. Storing voices only on the GPU would force the owner to upload them again after every rental.

## 2026-09-22 — No automatic transcription in the first version

Voice cloning asks the owner to supply the text spoken in the reference sample.

Do not add Whisper or another speech recognizer.

Reason: Fish S2 needs the reference text, and adding a speech recognizer would increase runtime cost, complexity, dependencies, and failure modes without being required for the requested product.

## 2026-09-22 — Native Fish controls only

Expose only request fields supported by the pinned official `ServeTTSRequest`.

Initial advanced controls:
- temperature
- top-p
- repetition penalty
- chunk length
- max new tokens
- normalize
- seed
- output format

Do not create fake speed or pitch fields. Voice performance is controlled with S2's native inline natural-language tags.

## 2026-09-22 — Controller-side global performance tag

A selected emotion/performance preset prepends one Fish-native tag to the target text. The owner may still place inline tags manually for finer control.

Reason: it gives Telegram-friendly one-tap emotion control without introducing text generation or hidden prompts.

## 2026-09-22 — 24 GB VRAM Vast baseline

Default Vast search requires at least 24 GB VRAM because the current Fish documentation recommends at least 24 GB for inference.

Disk defaults to 60 GB to leave room for source, environment, model weights, and caches while avoiding the much larger PixelPilot/Qwen disk profile.

## 2026-09-22 — Persistent lifecycle and billing metadata

Retain PixelPilot's per-second active rental meter and lifecycle recovery model.

The meter:
- begins at successful rental
- pauses on stop
- resumes on start
- finalizes on destroy

It is an estimate of active rental cost from the contracted hourly rate. Storage/network fees can be separate provider charges.

## 2026-09-22 — Provisioning failure is non-destructive by default

Do not automatically destroy a rented instance when bootstrap/readiness fails unless the owner explicitly enables that option.

Reason: a failed provisioning attempt may be recoverable, and silent deletion can destroy useful logs/state while the owner is paying for the instance.


## 2026-09-22 — Revalidate Vast rental by exact offer ID

Click-time rental validation must query the selected offer ID directly together with the full VoxPilot policy. Do not decide that an offer disappeared merely because it no longer appears in the current top displayed result set.

All marketplace searches and revalidation queries must use the configured rental disk size as Vast's allocated storage input so displayed `dph_total` and rental policy are price-consistent.

Reason: the first live rental attempt exposed a false unavailable result caused by top-result membership, and the prior 5 GB SDK pricing default did not match VoxPilot's 60 GB rental.
