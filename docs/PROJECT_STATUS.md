# VoxPilot — Project Status

Last updated: 2026-09-23

## Current phase

**Phase 2 — Live Vast/Fish acceptance and hardening**

Active plan: `plans/0004-live-bootstrap-and-acceptance.md`.

Live checkpoint on 2026-09-23: New-VPS runs `8cc5bd843f5253ad3fde20af8cfaab26acd7c22c`; `voxpilot.service` is active. The single tracked Vast rental completed Fish bootstrap after a live CUDA loader repair, passed authenticated health and direct TTS, and is now stopped with the local active meter paused. A warm-start timing fix has been identified in review and is not yet deployed.

The Phase 1 controller/runtime foundation is implemented on `main`. Phase 2 continues with live hardening and final acceptance.

## Completed hardening plan

`plans/0003-robust-vast-rental-revalidation.md`

Previous completed hardening plan: `plans/0002-live-vast-offer-revalidation.md`

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

The warm-start timing fix passed the final local gate but needs CI on its resulting HEAD and safe deployment before starting the preserved rental. User-provided voice quality, Telegram audio delivery, and final destroy/billing remain unverified.

## Previous next action (superseded by plan 0004)

Wait for the current Vast instance to finish provisioning:
1. keep the instance running
2. wait for Fish API readiness
3. if ready, perform the first real Arabic synthesis
4. if provisioning fails, inspect the new controller/Vast bootstrap logs without creating another instance
5. after synthesis, validate emotion tags, stop/start recovery, and final destroy/billing behavior

## Plan 0004 live evidence and next action

- Exactly one Vast rental was created and tracked. Bootstrap completed source checkout, Fish environment setup, and S2 Pro weight download.
- Fish initially failed during GPU initialization with CUDA error 804 because the image's forward-compatibility `libcuda` took precedence over the mounted host driver. With the host library selected, the same GPU loaded both models, completed warmup, and passed authenticated `/v1/health`.
- Direct live Fish requests returned MP3 data for Arabic neutral TTS and a synthetic-reference cloning request with `[whisper]`. User-provided reference quality and Telegram delivery remain unverified.
- A controller restart recovered the same rental as ready without creating a second instance.
- Vast accepted stop before the provider state changed. The old controller paused billing immediately and later treated Vast's `actual=exited`/`intended=stopped`/`cur=stopped` response as an error. Vast is now stopped, the original rental is preserved, and its local active meter is paused. Storage charges can continue.
- Plan 0004 changes cover the CUDA loader, stale Fish process cleanup, confirmed stop and status normalization, inventory-confirmed destroy, paid provisioning Cost Guard warnings, unresolved rental guard, repeated-start no-op, failed-start recovery, and safe Telegram no-op edits. The final local gate passed: 30 pytest tests, compileall, bootstrap `bash -n`, and diff whitespace check. Confirm CI on the final HEAD, then update New-VPS and verify warm start from the preserved disk.

## Deployment checkpoint — 2026-09-23

- GitHub Actions run `35784581217` succeeded for `8cc5bd843f5253ad3fde20af8cfaab26acd7c22c`.
- New-VPS was fast-forwarded to that commit after a consistent SQLite backup. `.env` kept its mode, size, and modification time. `voxpilot.service` restarted and is active; recovery now recognizes the stopped Vast rental correctly with billing paused. Vast inventory still contains exactly one tracked instance.
- Before warm start, code review found the transient-stopped start bug. The fix now passes 32 local pytest tests, compileall, bootstrap `bash -n`, and diff whitespace checks; CI and redeployment are next. This checkpoint is not final acceptance.
