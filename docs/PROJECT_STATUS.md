# VoxPilot — Project Status

Last updated: 2026-09-23

## Current phase

**Phase 2 — Live Vast/Fish acceptance and hardening**

Active plan: `plans/0004-live-bootstrap-and-acceptance.md`.

At this repair checkpoint, New-VPS runs `120f4ec` and `voxpilot.service` is active. The owner deleted the GPU rental while the generation repair is being completed. A fresh provider inventory returned zero instances; the controller reports phase `none`, no tracked instance, no active meter, and a final billing snapshot. Do not create a replacement rental as part of this repair.

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

The current repair passes 48 local pytest tests, Python compileall, bootstrap shell syntax, and diff whitespace checks. The Fish privacy patch applies cleanly to the exact pinned upstream commit. CI and New-VPS deployment of this repair remain pending.

The previous deployed lifecycle baseline `e226bf0` passed GitHub Actions run `35787451378` with 40 tests.

## Current blockers

The owner exercised Telegram generation. Fish health returned 200 while `/v1/tts` returned 500 with CUDA out of memory. Both saved references exceed 30 seconds. The original voice files remain stored on the controller. Duration validation, a default-voice escape path, clearer status/errors, and suppression of pinned Fish's unconditional prompt visualization are implemented locally and require CI/deployment. The GPU rental is gone; live post-fix synthesis must wait for a new owner-provisioned rental.

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
