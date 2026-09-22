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
