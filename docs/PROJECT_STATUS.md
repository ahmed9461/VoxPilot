# VoxPilot — Project Status

Last updated: 2026-09-22

## Current phase

**Phase 2 — Live Vast/Fish acceptance and hardening**

The Phase 1 controller/runtime foundation is implemented on `main`. The next work is a real Vast rental and end-to-end Fish S2 validation.

## Active plan

`plans/0002-live-vast-offer-revalidation.md`

Previous completed plan: `plans/0001-foundation-and-vast-fish-runtime.md`

## Repository state

- Owner-only Telegram controller implemented.
- Controller-side voice storage implemented.
- Active voice selection and deletion implemented.
- Fish-native emotion/performance presets implemented.
- Advanced Fish request controls implemented.
- Official Fish MessagePack TTS client implemented.
- Vast live search, normalized offers and deterministic ordering implemented.
- Rental re-fetches the marketplace before create so a stale offer cannot be rented blindly.
- Unique-label instance reconciliation implemented.
- Start/stop/destroy and controller restart recovery implemented.
- Per-second active rental billing and Cost Guard implemented.
- Pending-label recovery restores billing from the cached contracted offer when needed.
- Pinned Fish bootstrap implemented.
- Rich Message home UI and styled Telegram buttons implemented with classic fallback.
- CI workflow implemented.

## Locked runtime baseline

- Fish source: `fishaudio/fish-speech@214da3cd841bda85da2496b96cd3c4d7edb1337e`
- weights: `fishaudio/s2-pro`
- minimum Vast VRAM: 24 GB
- default Vast disk: 60 GB
- default hard price ceiling: $0.50/hour
- controller keeps voice references; Vast remains disposable
- official Fish API is used directly with a generated bearer token
- no Qwen, vLLM, Whisper, chat history, personas, RAG, or hidden prompts

## Validation state

GitHub Actions run `35772753349` for HEAD `958bdb6910f07ab3e2d8260720bde9e6e37f0100` completed successfully:
- dependency install: passed
- `bash -n scripts/bootstrap_vast.sh`: passed
- `python -m compileall -q src tests`: passed
- `pytest -q`: **14 passed**

## Current blockers

Live rental attempt #1 exposed an offer-revalidation bug before instance creation: the selected offer could be rejected when it fell outside the top displayed result set. No Vast instance was created and no GPU billing started. Plan 0002 is active to harden exact-ID revalidation and storage-aware pricing.

## Next action

Complete plan 0002, deploy the fix to the controller, then retry the first controlled Vast rental:
1. configure controller secrets in `.env`
2. run the bot
3. add one 10–30 second reference voice + exact transcript
4. search Vast offers
5. rent a suitable 24 GB+ offer
6. record bootstrap/model-download readiness behavior
7. generate neutral Arabic speech
8. test multiple Fish emotion tags
9. verify stop/start billing behavior
10. destroy the instance and verify the final billing snapshot
