# VoxPilot — Project Status

Last updated: 2026-10-20

## Current phase

**Phase 2 — Live Vast/Fish acceptance and hardening**

Completed integration plan: `plans/0007-authorized-controller-update.md`, following review plan 0006 and implementation plan 0005.

PR #1 review is complete against main `818163bb1fc7dc6d96305a4a8b59d97fe7789e81`, which is an ancestor of the PR. Repaired code `427843c30484a0e7f1adbbdd8130cbf108d179d0` passed the local Python 3.12 gate (90 pytest tests, compileall, bootstrap shell syntax, and diff whitespace) and matching [PR CI](https://github.com/ahmed9461/VoxPilot/actions/runs/39426261177) / [push CI](https://github.com/ahmed9461/VoxPilot/actions/runs/39426251484). The PR job log independently confirms 90 passing tests. Both workflow trees contain only the test workflow, with no deployment step; no unresolved review threads or reviews were present at inspection. The simulated merge tree equals the tested tree. Integration uses the normal GitHub merge path with an expected head SHA and successful CI on the final documentation-synchronized head. Branch protection/rules were inspected without changing security settings.

The owner explicitly approved draft removal, merge, and the existing-controller update. PR #1 is merged and its application code deployed at `93efbea89d20f23b13d8aacac7952dc26b499ada`. Matching [merge CI](https://github.com/ahmed9461/VoxPilot/actions/runs/39428688670) passed 90 tests. Controller deployment and verification are complete; configuration, saved voices, active selection, and sampling settings were preserved. Private deployment records retain backup and rollback details outside the public repository. The original local checkout remains clean and unchanged.

The live Vast/Fish acceptance track in `plans/0004-live-bootstrap-and-acceptance.md` remains open; plan 0005 is a scoped owner-requested UX improvement and does not create or modify a Vast rental.

Marketplace/rental repair `ad597212a850fea5c2ede864ad8263bf073ff458` is included in the deployed application code. Its live marketplace/rental acceptance remains separate work; this update did not rent another server or GPU.

The existing controller passed offline checks, service imports, actual polling readiness, stable operation, and configuration/data preservation checks. Historical deployment observations below are retained as history and superseded by this checkpoint.

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
- Natural parenthetical stage directions are merged and deployed from PR #1. Common Arabic effect phrases prefer documented Fish-native tags, unknown compound directions remain free-form, and manual tags/nested parentheses stay literal. Reversible consistency mode defaults on for fresh settings; upgrades retain effective legacy sampling until opt-in. The 90-test local and matching CI gate supersedes the earlier 78-test reliability checkpoint.
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

Current application code passed 90 local Python 3.12 tests and final PR/push/merge CI. The existing controller passed offline compilation/settings/parser checks, dependency consistency, imports as the service user, service/polling readiness, stable operation, data integrity, and settings/voice/environment preservation checks. No test dependencies were added to the production environment.

### Historical validation — 2026-09-23 (superseded)

Repair commit `5229d1f` passed 48 local pytest tests, Python compileall, bootstrap shell syntax, and diff whitespace checks. The Fish privacy patch applies cleanly to the exact pinned upstream commit. Matching GitHub Actions run `35794540192` succeeded. New-VPS was fast-forwarded after a consistent SQLite backup; service is active, repository clean, `.env` metadata unchanged, both saved voice profiles present, and no new service errors were counted after deployment. The live controller probes both profiles and confirms durations about 47.7 and 89.8 seconds, so the new guard will reject them until the owner chooses default voice or uploads a shorter reference.

The previous deployed lifecycle baseline `e226bf0` passed GitHub Actions run `35787451378` with 40 tests.

## Current blockers

No blocking controller review or deployment issue remains. Real speech quality, voice cloning, Telegram audio delivery, and GPU log privacy require separate owner acceptance; these were not claimed from offline checks. Historical long-reference findings below do not assert the quality or duration of every currently saved voice.

## Current next action

Follow only the [remaining owner live acceptance in plan 0004](../plans/0004-live-bootstrap-and-acceptance.md#remaining-owner-live-acceptance). Controller deployment is complete under plan 0007; it is not a pending update/restart task. Instance-dependent tests require fresh resource evidence, appropriate owner authorization, and the necessary input. Do not infer current Vast inventory, running/stopped state, or billing from the historical record below.

## Historical live and deployment record — 2026-09-22 to 2026-09-23

The following observations and then-next actions apply only to their recorded September checkpoints. They are retained as history, not current work instructions. In particular, references to a preserved/paid/stopped rental and requests to confirm CI, update New-VPS, or restart the controller are superseded by the completed 2026-10-20 checkpoint and current next action above.

### Original provisioning next action — 2026-09-22 (superseded)

Wait for the current Vast instance to finish provisioning:
1. keep the instance running
2. wait for Fish API readiness
3. if ready, perform the first real Arabic synthesis
4. if provisioning fails, inspect the new controller/Vast bootstrap logs without creating another instance
5. after synthesis, validate emotion tags, stop/start recovery, and final destroy/billing behavior

### Historical Plan 0004 live evidence — 2026-09-22

- Exactly one Vast rental was created and tracked. Bootstrap completed source checkout, Fish environment setup, and S2 Pro weight download.
- Fish initially failed during GPU initialization with CUDA error 804 because the image's forward-compatibility `libcuda` took precedence over the mounted host driver. With the host library selected, the same GPU loaded both models, completed warmup, and passed authenticated `/v1/health`.
- Direct live Fish requests returned MP3 data for Arabic neutral TTS and a synthetic-reference cloning request with `[whisper]`. User-provided reference quality and Telegram delivery remain unverified.
- A controller restart recovered the same rental as ready without creating a second instance.
- Vast accepted stop before the provider state changed. The old controller paused billing immediately and later treated Vast's `actual=exited`/`intended=stopped`/`cur=stopped` response as an error. Vast is now stopped, the original rental is preserved, and its local active meter is paused. Storage charges can continue.
- Plan 0004 changes cover the CUDA loader, stale Fish process cleanup, confirmed stop and status normalization, inventory-confirmed destroy, paid provisioning Cost Guard warnings, unresolved rental guard, repeated-start no-op, failed-start recovery, and safe Telegram no-op edits. The final local gate passed: 30 pytest tests, compileall, bootstrap `bash -n`, and diff whitespace check. Confirm CI on the final HEAD, then update New-VPS and verify warm start from the preserved disk.

### Historical deployment checkpoint — 2026-09-23

- GitHub Actions run `35784581217` succeeded for `8cc5bd843f5253ad3fde20af8cfaab26acd7c22c`.
- New-VPS was fast-forwarded to that commit after a consistent SQLite backup. `.env` kept its mode, size, and modification time. `voxpilot.service` restarted and is active; recovery now recognizes the stopped Vast rental correctly with billing paused. Vast inventory still contains exactly one tracked instance.
- Before warm start, code review found the transient-stopped start bug. The fix now passes 32 local pytest tests, compileall, bootstrap `bash -n`, and diff whitespace checks; CI and redeployment are next. This checkpoint is not final acceptance.

### Historical warm-start recovery review — 2026-09-23

- GitHub Actions run `35785316001` succeeded for `d9005e35fd96dba05f4026130ba233d40776747a`.
- A controller restart during a persisted `booting` phase could still classify a transient provider `stopped` response as final. The follow-up recovery fix passed its local gate: 33 pytest tests, compileall, bootstrap `bash -n`, and diff whitespace check. Confirm CI and deploy that HEAD before warm-starting the preserved instance.

### Historical live warm start and repair — 2026-09-23

- CI run `35785635675` succeeded for `d0c7576`, and New-VPS was safely fast-forwarded to that commit with a consistent SQLite backup. The original Vast rental stayed tracked and stopped before the warm start.
- The controller's first warm-start wait expired while Vast still reported stopped. A later accepted start of the same rental reached `running` and Fish health became ready, but the controller restart found a stale local `stopped` phase and could not provision from it. A backed-up, guarded phase reconciliation restored `ready` with an active local meter; one rental remains in inventory.
- Follow-up code now checks Vast lifecycle `success=false`, treats `actual=exited` with running intent/current state as `starting`, recovers local stopped state when Vast is already starting/running, preserves pending stop across restart, and avoids a redundant start request when Vast is already starting/running.
- CI run `35787451378` passed with 40 tests for `e226bf0`; New-VPS was fast-forwarded after a consistent SQLite backup. `.env` metadata and voice count were unchanged. `voxpilot.service` is active with zero restarts and no new application errors in the deployment window.
- After deployment, provider inventory contained exactly one instance, the tracked rental was `running`, controller phase `ready`, local billing active, authenticated Fish health true, the Fish API port listening, and a GPU compute process present. Direct warm-start Arabic TTS and a synthetic-reference request with `[whisper]` both returned MP3 bytes. The synthetic marker did not appear in the Fish log.
- Next: obtain a real owner voice/reference transcript and owner Telegram acceptance when available. Keep the current rental until the owner stops or destroys it; do not delete a working paid instance just to exercise the destroy endpoint.
