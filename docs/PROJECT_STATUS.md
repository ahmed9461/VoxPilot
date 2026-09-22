# VoxPilot — Project Status

Last updated: 2026-09-23

## Current phase

**Phase 2 — Live Vast/Fish acceptance and hardening**

Active plan: `plans/0004-live-bootstrap-and-acceptance.md`.

Live checkpoint on 2026-09-23: New-VPS runs the validated lifecycle code from `e226bf03ab938cf23c45a0284106184598b8eab5`; `voxpilot.service` is active. The single tracked Vast rental is running on its preserved disk. Fish authenticated health is ready, the controller phase is `ready`, and the local active meter is running. A documentation-only checkpoint may advance Git HEAD without changing this runtime code.

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

GitHub Actions run `35787451378` for deployed code commit `e226bf03ab938cf23c45a0284106184598b8eab5` completed successfully:
- dependency install: passed
- `bash -n scripts/bootstrap_vast.sh`: passed
- `python -m compileall -q src tests`: passed
- `pytest -q`: **40 passed**

## Current blockers

The owner has not supplied a voice reference or exercised the Telegram audio flow in this session, so those quality and delivery gates remain open. Live destroy/billing closeout remains untested to preserve the working paid rental; the unit/integration boundary is covered by tests. The rental is currently running and accruing provider charges.

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

## Warm-start recovery review — 2026-09-23

- GitHub Actions run `35785316001` succeeded for `d9005e35fd96dba05f4026130ba233d40776747a`.
- A controller restart during a persisted `booting` phase could still classify a transient provider `stopped` response as final. The follow-up recovery fix passed its local gate: 33 pytest tests, compileall, bootstrap `bash -n`, and diff whitespace check. Confirm CI and deploy that HEAD before warm-starting the preserved instance.

## Live warm start and pending repair — 2026-09-23

- CI run `35785635675` succeeded for `d0c7576`, and New-VPS was safely fast-forwarded to that commit with a consistent SQLite backup. The original Vast rental stayed tracked and stopped before the warm start.
- The controller's first warm-start wait expired while Vast still reported stopped. A later accepted start of the same rental reached `running` and Fish health became ready, but the controller restart found a stale local `stopped` phase and could not provision from it. A backed-up, guarded phase reconciliation restored `ready` with an active local meter; one rental remains in inventory.
- Follow-up code now checks Vast lifecycle `success=false`, treats `actual=exited` with running intent/current state as `starting`, recovers local stopped state when Vast is already starting/running, preserves pending stop across restart, and avoids a redundant start request when Vast is already starting/running.
- CI run `35787451378` passed with 40 tests for `e226bf0`; New-VPS was fast-forwarded after a consistent SQLite backup. `.env` metadata and voice count were unchanged. `voxpilot.service` is active with zero restarts and no new application errors in the deployment window.
- After deployment, provider inventory contained exactly one instance, the tracked rental was `running`, controller phase `ready`, local billing active, authenticated Fish health true, the Fish API port listening, and a GPU compute process present. Direct warm-start Arabic TTS and a synthetic-reference request with `[whisper]` both returned MP3 bytes. The synthetic marker did not appear in the Fish log.
- Next: obtain a real owner voice/reference transcript and owner Telegram acceptance when available. Keep the current rental until the owner stops or destroys it; do not delete a working paid instance just to exercise the destroy endpoint.
