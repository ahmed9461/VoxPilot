# Plan 0001 — Foundation and Vast/Fish Runtime

Status: COMPLETE
Created: 2026-09-22

## Goal

Produce a small, coherent first VoxPilot implementation that can:
- run as an owner-only Telegram bot
- search/rent/control a suitable Vast instance
- bootstrap pinned Fish Audio S2 Pro
- save a reference voice on the controller
- generate speech through the official authenticated Fish API
- expose native emotion/prosody presets and real Fish sampling controls
- recover lifecycle/billing state after controller restart

## Constraints

- No Qwen, vLLM, Whisper, chat history, personas, RAG, or hidden prompts.
- Do not copy unused PixelPilot code.
- Use Fish API fields exactly as supported by the pinned upstream schema.
- Keep credentials out of Git.
- Keep voice/generated audio out of Git.
- No automatic instance destruction on provisioning failure by default.
- All meaningful changes must update status/progress/memory as appropriate.

## Phase A — Controller foundation

Create:
- Python package / dependency manifest
- environment configuration
- SQLite metadata store
- owner-only middleware
- safe Telegram callback/edit helpers
- base Rich Message home UI
- CI

Validation:
- imports compile
- config/db/security unit tests

## Phase B — Vast lifecycle

Adapt only the proven PixelPilot subset:
- offer query / normalization
- fresh search
- deterministic ranking
- offer cache
- price-cap recheck
- unique-label rental reconciliation
- start/stop/destroy
- restart recovery
- billing meter
- Cost Guard

Validation:
- unit tests for query/normalization/price protection/billing
- no dependency on PixelPilot modules

## Phase C — Fish runtime

Create:
- Vast bootstrap script
- pinned Fish source checkout
- Fish environment setup
- S2 Pro weight download
- official API server launch with bearer auth
- health polling
- Fish MessagePack TTS client

Validation:
- unit tests for request encoding/auth/error handling
- bootstrap shell syntax
- no custom inference gateway

## Phase D — Voice references and TTS controls

Create:
- controller-side voice store
- Telegram add/list/select/delete flows
- active voice state
- curated native Fish performance tags
- advanced sampling settings
- direct text-to-speech generation path

Validation:
- voice persistence tests
- tag composition tests
- manual inspection that target text is not rewritten

## Phase E — Integration review

- run full compileall + pytest
- fix all failures
- update README
- update project memory/status/progress
- confirm CI for exact HEAD
- leave a precise live-acceptance checklist

## Completion criteria

Plan 0001 is complete only when:
- application code exists and imports cleanly
- automated tests pass
- CI is configured
- docs match implementation
- repository status identifies live Vast testing as the next phase
- no unwanted PixelPilot chat/model code is present


## Completion checkpoint — 2026-09-22

Implemented:
- all Phase A controller foundation items
- all Phase B Vast lifecycle items
- all Phase C Fish runtime items
- all Phase D voice/TTS control items
- Phase E README, memory/status/progress and CI setup

Validation:
- GitHub Actions run `35772753349` on commit `958bdb6910f07ab3e2d8260720bde9e6e37f0100` completed successfully.
- `bash -n scripts/bootstrap_vast.sh`: passed
- `python -m compileall -q src tests`: passed
- `pytest -q`: 14 passed

Next phase:
- live Vast/Fish acceptance and evidence-driven hardening
