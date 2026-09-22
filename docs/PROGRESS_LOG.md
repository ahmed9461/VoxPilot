# VoxPilot — Progress Log

This file is append-only for meaningful project milestones.

## 2026-09-22 — Repository initialized

Completed:
- Confirmed `ahmed9461/VoxPilot` exists and was empty.
- Added `AGENTS.md`.
- Established repository-as-source-of-truth workflow.
- Established mandatory memory/status/decisions/progress updates.
- Established explicit PixelPilot reuse and exclusion boundaries.

Validation:
- Confirmed write access to VoxPilot main.
- Confirmed initial commit landed successfully.

Remaining:
- write architecture/status/roadmap/active plan
- implement application foundation
- add tests and CI
- perform live Vast/Fish acceptance

## 2026-09-22 — PixelPilot reference audit

Completed:
- Inspected current PixelPilot tree and recent commits.
- Identified reusable Vast SDK query/normalization/lifecycle code patterns.
- Identified unique-label instance reconciliation.
- Identified stale-offer price-cap recheck.
- Identified live marketplace refresh comparison.
- Identified controller restart recovery.
- Identified per-second rental billing and Cost Guard.
- Identified safe stale-callback / no-op-edit handling.
- Identified native Telegram Rich Message and styled-button fallback pattern.

Explicitly rejected for VoxPilot:
- Qwen/vLLM runtime
- Whisper
- chat history
- assistant prompt/personality/settings system
- image/video understanding
- PixelPilot custom inference gateway
- unrelated migration helpers

Remaining:
- implement only the approved reusable subset.

## 2026-09-22 — Fish S2 upstream audit

Completed:
- Verified current official Fish Speech server documentation and implementation.
- Verified local API server supports `/v1/health`, `/v1/tts`, and bearer authentication.
- Verified the official request schema supports reference audio + reference text and sampling controls.
- Verified Fish S2 uses native inline natural-language emotion/prosody tags.
- Verified official inference guidance recommends >=24 GB VRAM.
- Verified model weights are published as `fishaudio/s2-pro`.
- Selected upstream source commit `214da3cd841bda85da2496b96cd3c4d7edb1337e` as the reproducible initial pin.

Architecture simplifications resulting from the audit:
- no VoxPilot inference gateway
- no Whisper
- voice samples persist on controller
- controller sends references with TTS requests
- emotions are native Fish tags, not prompts

Remaining:
- implement plan 0001 and validate locally/CI before a live Vast test.
