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


## 2026-09-22 — Phase 1 implementation completed

Completed:
- Built the Python controller package and environment configuration.
- Added owner-only Telegram middleware.
- Added safe callback/no-op handling and Telegram Rich Message home UI with styled controls.
- Added local SQLite state/events storage.
- Added controller-side voice-reference storage with generated internal IDs.
- Added voice add/list/select/delete Telegram flows.
- Added Fish-native performance controls and advanced supported sampling settings.
- Added direct authenticated Fish API client using MessagePack and the pinned official request shape.
- Added fresh Vast marketplace search, normalized offers, deterministic sorting and cached display snapshots.
- Added rental-time marketplace revalidation before instance creation.
- Added unique instance labels and reconciliation for sparse/ambiguous Vast create responses.
- Added start/stop/destroy lifecycle, restart recovery, billing meter and Cost Guard.
- Added recovery hardening so a pending-label-recovered paid instance restores a billing meter from the cached contracted offer.
- Added pinned Fish S2 bootstrap with official Fish server, bearer authentication and model download.
- Added CI and focused unit tests.

Validation:
- GitHub Actions run `35772753349` succeeded for commit `958bdb6910f07ab3e2d8260720bde9e6e37f0100`.
- dependency install: success
- bootstrap shell syntax: success
- Python compileall: success
- pytest: **14 passed in 0.25s**

Review outcome:
- No Qwen/vLLM/Whisper/chat/persona/prompt subsystem was copied into VoxPilot.
- Fish emotion handling is model-native tag composition only.
- Voice samples remain on the durable controller and survive Vast deletion.
- Vast credentials remain controller-only; the GPU receives only its generated Fish API token and runtime configuration.

Remaining:
- live Vast rental acceptance
- real S2 model download/startup timing
- Arabic voice-clone quality validation
- real Telegram audio delivery validation
- stop/start/destroy behavior against a live Vast instance


## 2026-09-22 — Live rental attempt #1: precise offer revalidation fix

Observed:
- User selected RTX 3090 25 GB at about $0.148/hour.
- Rental failed before instance creation with `Offer is no longer available; refresh the market`.
- Bot status confirmed there was no current instance, so no GPU rental billing began.

Root cause:
- Click-time revalidation searched the normal top displayed result set and then looked for the selected ID inside it.
- Vast search results are a limited/ranked subset, so an offer could still exist while no longer appearing in that top set.
- Marketplace requests also used the SDK default 5 GB allocated storage for pricing while VoxPilot rents 60 GB.

Fix:
- Revalidate the selected offer directly with the supported Vast `id=<offer_id>` filter plus all VoxPilot rental policy filters.
- Use `VAST_DISK_GB` as `storage_gb` for both displayed marketplace prices and exact revalidation.
- Show a specific unavailable/changed-offer message and fresh offer list instead of the generic provisioning failure.

Validation:
- Confirmed Vast SDK 1.6.0 supports the `id` offer filter.
- GitHub Actions run `35776271041` on commit `1f37aa13f04932947893f1f0f13da8ff1927ec18`: success.
- shell syntax: passed
- compileall: passed
- pytest: **14 passed in 1.85s**

Remaining:
- deploy fix to the controller server
- retry live rental and continue Fish bootstrap acceptance


## 2026-09-22 — Live rental attempt #2: robust Vast selected-offer resolution

Observed:
- Plan 0002 was deployed successfully.
- Selecting an offer and pressing rent still returned the specific "offer changed or unavailable" path before instance creation.
- The freshly rendered marketplace continued to contain visually matching offers.
- No Vast instance was created, therefore no GPU rental billing began.

Reassessment:
- The exact text query `id=<offer_id>` remained a brittle dependency.
- Vast SDK 1.6.0 accepts pre-parsed query dictionaries directly.
- Vast create-instance itself uses the offer ID returned by search and sends a PUT to `/asks/<offer_id>/`.

Plan 0003 fix:
- Added dedicated selected-offer lookup in the Vast gateway.
- First lookup uses a pre-parsed numeric filter: `{"id": {"eq": offer_id}}`.
- If Vast returns no exact row, VoxPilot performs a fresh policy search up to 200 offers and matches the selected ID locally.
- The resolved offer is validated locally against VRAM, reliability, total hourly price ceiling, disk capacity, verification, download speed, direct ports, datacenter policy, rentable state, and single-GPU policy.
- Final create still uses `cancel_unavail=true` to reject a real last-moment availability race.
- Display/search pricing continues to use the actual configured 60 GB storage amount.

Validation:
- GitHub Actions run `35777567902` on commit `e0f890749b86fe154c340c8c03ea58b07fd0856a`: success.
- shell syntax: passed
- compileall: passed
- pytest: **17 passed in 0.91s**

Remaining:
- deploy latest main to controller
- retry live Vast rental
- continue Fish bootstrap/model acceptance after first successful instance creation


## 2026-09-22 — Live rental attempt #3: first successful Vast instance creation

Observed:
- The plan 0003 rental lookup was deployed to the controller.
- User selected an RTX 3090 offer with 25 GB VRAM at approximately $0.177/hour.
- VoxPilot successfully passed rental validation and created a real Vast instance.
- Telegram immediately switched to Fish Audio S2 Pro provisioning.
- Local active-rental meter started successfully; first visible checkpoint was about 2 seconds active time and $0.0001 estimated cost.

Significance:
- The false offer-rejection problem from live attempts #1 and #2 is resolved.
- Vast instance creation and billing-state initialization are now confirmed working in live use.
- The project has advanced from marketplace/rental acceptance into real Fish bootstrap/model readiness testing.

Current state:
- paid Vast instance exists and is provisioning
- do not create another instance while this one is active
- next evidence needed is either Fish-ready success or the first provisioning/bootstrap failure from this instance

## 2026-09-22 — Plan 0004: first live Fish success and stop-state defects

Observed:
- One paid Vast instance was already present and tracked at the beginning of plan 0004.
- GPU checkout, Fish environment setup, and S2 Pro weight download completed. Fish startup then stopped at CUDA error 804; the log did not advance for over twenty minutes and GPU usage stayed idle.
- Loader tracing showed the image's CUDA compatibility library was selected. Preloading the mounted host driver made PyTorch GPU allocation work on the same RTX 3090. The revised bootstrap restarted Fish on that rental; both models loaded, warmup finished, and authenticated health passed.
- Direct Arabic neutral TTS returned an MP3 response. A second request using that synthetic sample as reference with the native `[whisper]` tag also returned MP3. This is a protocol smoke test, not user voice quality acceptance or Telegram delivery acceptance.
- Restarting the controller recovered the same instance, with no duplicate rental.
- Vast accepted stop before the provider status became stopped. The old controller paused its meter immediately; later Vast reported `actual=exited`, `intended=stopped`, `cur=stopped`, which old recovery classified as an error. The provider is now stopped and the local meter is paused.

Root causes and changes in progress:
- Bootstrap did not control which `libcuda` Fish loaded and had no early GPU check. Select the host library when present and perform a real CUDA allocation before downloading weights.
- A failed Fish worker could remain alive after SIGTERM. Wait briefly and force-kill the stale process before replacement.
- Stop billing was based on request acceptance rather than provider confirmation, and stopped Vast payloads were misnormalized. Poll to confirmed stop and normalize the observed payload.
- Cost Guard watched only ready idle instances. Warn on active billed non-ready states.
- An unresolved create label did not prevent a second create. Hold further rentals until reconciliation.
- Repeated start taps and unchanged Telegram edits could produce duplicate requests or harmless callback errors. Handle no-op paths explicitly.

Validation so far:
- Direct GPU allocation with the mounted host driver: passed.
- Fish model warmup and authenticated health on the existing rental: passed.
- Direct neutral Arabic TTS and synthetic-reference native-tag request: passed.
- Controller restart inventory: one instance before and after.
- Local pytest after initial runtime fixes: 24 passed. Final gate is still pending.

Next:
- Complete focused tests and code review, run full gate, confirm CI on final HEAD, deploy safely to New-VPS, and verify stopped-state recovery and a warm start from the preserved GPU disk.
- Verify owner-provided voice quality and Telegram audio delivery when the owner exercises those flows. Do not claim them from synthetic API checks.

## 2026-09-23 — Plan 0004 code review checkpoint

Second review found that a failed start could leave phase `provisioning`, making subsequent start taps appear to be no-ops. It now records a retryable error unless Vast actually stopped. The live stop also showed that Vast accepts lifecycle requests before completion, so destroy now waits for two valid inventory snapshots without the instance before clearing the record or finalizing the meter. Restart recovery handles an interrupted owner-requested destroy. Malformed inventory cannot count as absence.

The Fish launch now defaults Loguru to WARNING because pinned Fish logs prompt text at INFO; this still needs a live post-start check. Telegram callback screens use the existing safe edit helper, and voice names are escaped before HTML rendering.

Validation: final local gate passed with **30 pytest tests**, Python compileall, bootstrap `bash -n` on New-VPS, and diff whitespace check. GitHub Actions on the final HEAD, production deployment, and warm-start acceptance remain.

## 2026-09-23 — First plan 0004 deployment and warm-start review

GitHub Actions run `35784581217` succeeded on code HEAD `8cc5bd843f5253ad3fde20af8cfaab26acd7c22c`. After a consistent SQLite backup, New-VPS fast-forwarded to the same commit; `.env` and voice/runtime data were untouched. `voxpilot.service` restarted successfully. Its recovery recognized the original Vast instance as stopped, with the active meter paused and no duplicate rental.

Before starting the preserved instance, a second lifecycle review found that the start path resumed billing immediately and entered Fish readiness polling while Vast could still report `stopped` during scheduling. That could fail a valid start before the GPU was running. The follow-up fix waits for provider `running`/`frozen`, then resumes the meter and probes Fish, while preserving an in-progress stop/destroy phase if operations overlap. Focused tests passed; final gate, CI, redeployment, and live warm start remain.

A focused concurrency test also showed why Fish health must not write `ready` after a stop begins. The final ready transition is now guarded by the same control lock as stop/destroy, with a regression test that pauses health while stop completes.

Follow-up local gate: **32 pytest tests passed**, Python compileall passed, bootstrap `bash -n` passed on New-VPS, and diff whitespace check passed. CI and redeployment remain before the live warm start.

## 2026-09-23 — Pending-boot restart recovery review

GitHub Actions run `35785316001` succeeded for `d9005e35fd96dba05f4026130ba233d40776747a`. Before deploying it and starting the preserved rental, review found the same transient `stopped` response could occur if the controller restarted after a start request but before Vast reported `running`. Recovery previously marked the instance stopped immediately. It now waits for the persisted `booting` operation, resumes billing only after provider running, and records a true stopped or error outcome if that wait fails. A focused regression test reproduces the transient response. Final gate, CI, deployment, and live warm start remain.

Local gate for the recovery follow-up: **33 pytest tests passed**, Python compileall, bootstrap `bash -n`, and diff whitespace check passed. CI and deployment remain.
