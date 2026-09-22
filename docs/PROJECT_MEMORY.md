# VoxPilot — Project Memory

## Current goal

VoxPilot is a personal, owner-only Telegram bot for generating speech and cloning voices with Fish Audio S2 Pro on temporary Vast.ai GPU instances rented by the hour.

The controller remains online separately from the GPU instance. It owns Telegram interaction, local voice-reference storage, Vast credentials, lifecycle state, billing metadata, TTS settings, and recovery. A rented GPU runs the pinned official Fish Speech API server.

## Non-negotiable product behavior

1. VoxPilot is TTS/voice cloning, not a conversational assistant.
2. Do not add hidden prompts, system prompts, personas, chat history, RAG, text rewriting, or LLM conversation layers.
3. Fish S2 inline tags such as `[whisper]`, `[excited]`, and `[angry]` are native speech controls and may be inserted explicitly by the owner or selected through the bot UI.
4. Voice cloning uses reference audio plus the matching reference text supplied by the owner.
5. Do not add automatic transcription unless it is explicitly approved as a future feature.
6. Only expose controls present in the pinned Fish S2 local API. Never invent unsupported request fields.
7. Voice samples are stored on the controller, not on the ephemeral Vast instance, so they survive instance deletion.
8. User audio, generated audio, secrets, SQLite files, caches, and runtime logs must never be committed.
9. The public Fish API port on Vast must require a generated bearer token.
10. `TELEGRAM_BOT_TOKEN` and `VAST_API_KEY` stay on the controller and are never sent to the rented GPU.
11. Every Vast refresh is a fresh marketplace query.
12. Revalidate the selected offer against the configured hourly price ceiling immediately before rental.
13. Rent/start/stop/destroy operations are serialized so rapid Telegram taps cannot race lifecycle transitions.
14. Lifecycle and active-rental billing state persist in SQLite and are reconciled after a controller restart.
15. Provisioning failure must not auto-delete a paid instance unless the owner explicitly enables that policy.
16. Telegram Rich Messages and styled buttons should be used where useful, with reliable classic-message fallback.
17. Keep normal Telegram screens user-facing; raw stack traces, tokens, model internals, and deployment commands belong in logs/docs.

## Reused lessons from PixelPilot

PixelPilot is a reference implementation, not a codebase to copy wholesale.

Retain these proven patterns:
- official Vast SDK integration
- normalized offer data
- wider live marketplace fetch followed by deterministic local ordering
- stale-offer protection before rental
- unique instance labels and reconciliation when create responses are sparse
- controller restart recovery
- billing meter that pauses on stop and resumes on start
- optional Cost Guard
- owner-only middleware
- stale callback/no-op edit handling
- native Telegram Rich Messages with fallback
- repository memory, decisions, status, progress, tests, and CI discipline

Explicitly exclude:
- Qwen
- vLLM
- Whisper
- chat history
- assistant personality/tone prompt layers
- image/video understanding
- multimodal chat routing
- PixelPilot inference gateway
- unrelated migrations and compatibility code

## Fish Audio integration baseline

Pinned upstream repository:
- repository: `fishaudio/fish-speech`
- pinned source commit: `214da3cd841bda85da2496b96cd3c4d7edb1337e`
- model weights: `fishaudio/s2-pro`

The pin is intentional. A new upstream Fish commit must be adopted deliberately and validated before changing the pin.

Official local-server interface used by VoxPilot:
- health: `GET /v1/health`
- synthesis: `POST /v1/tts`
- bearer authentication: official `--api-key` server option
- request body: MessagePack using Fish's `ServeTTSRequest` shape
- base model is selected when the Fish server starts; it is not a per-request field

Supported request controls used by VoxPilot:
- text
- reference audio + matching reference text
- format: wav/mp3/opus
- normalize
- seed
- chunk length
- max new tokens
- top-p
- repetition penalty
- temperature
- streaming remains disabled initially

Fish documentation currently recommends at least 24 GB VRAM for inference. VoxPilot therefore defaults the Vast search policy to 24 GB minimum GPU VRAM.

## Voice-reference lifecycle

A saved voice belongs to the controller:
- one generated internal ID
- owner-facing name
- reference audio file
- exact reference transcript
- MIME type / extension metadata
- creation timestamp

The active voice ID is stored in SQLite. Reference audio bytes are sent with each TTS request. Deleting a temporary Vast server does not delete saved voices.

## TTS control model

A global emotion/performance selection may prepend one model-native Fish tag to the requested text. The owner can still write Fish tags inline manually for sub-word or phrase-level control.

Initial curated controls:
- normal
- excited
- delight
- sad
- angry
- whisper
- low voice
- shouting
- surprised
- laughing
- singing

Initial sampling defaults follow Fish's official API client:
- temperature: 0.8
- top_p: 0.8
- repetition_penalty: 1.1
- chunk_length: 300
- max_new_tokens: 1024
- normalize: true
- seed: random
- output format: mp3

## Vast baseline

Initial policy defaults are configurable:
- 1 GPU
- >= 24 GB VRAM
- >= 0.98 reliability
- <= $0.50/hour
- >= 60 GB disk
- verified offers only
- >= 1 direct port
- >= 100 Mbps advertised download
- up to 8 displayed offers

Search/ranking favors lowest total hourly price first, then stronger performance/network when prices tie.

## Runtime boundary

Controller:
- Telegram bot
- voice storage
- SQLite metadata
- Vast SDK
- Fish HTTP client
- TTS controls
- billing / Cost Guard

Temporary Vast instance:
- pinned Fish Speech source
- S2 Pro weights
- official Fish API server
- generated bearer token
- public mapped API port

No custom inference gateway is required because the official Fish server already provides health, TTS, and bearer authentication.


## Operational recovery details

- A rental always performs a fresh Vast marketplace query immediately before create. The selected offer must still exist in the fresh result set and remain under the configured hard price ceiling.
- Vast create uses a unique `VoxPilot-<random>` label. If the create response does not expose an instance ID, the controller attempts to reconcile exactly one instance with that label.
- If the controller restarts while only a pending label is known, recovery searches by that label. When a paid instance is recovered and no billing meter exists yet, the meter is initialized from the cached contracted offer price before readiness probing continues.
- Provisioning failure changes the lifecycle to ERROR but does not silently destroy the instance unless `VAST_AUTO_DESTROY_ON_PROVISION_FAILURE=true`.
- The current code baseline passed GitHub Actions on 2026-09-22: bootstrap shell syntax, Python compileall and 14 pytest tests.


## Vast selected-offer revalidation

Live acceptance established that the selected offer must never be revalidated by merely checking whether it still appears in the current top displayed search results.

Current rule:
- normal offer search uses `VAST_DISK_GB` as Vast SDK allocated storage so `dph_total` reflects the same disk size VoxPilot will rent;
- click-time rental validation performs an exact `id=<offer_id>` query combined with the full VoxPilot policy;
- an offer is considered unavailable only when that exact-ID policy query returns no matching row;
- if exact revalidation fails, no instance is created and Telegram immediately shows a fresh offer list.

This behavior was introduced after live rental attempt #1 falsely rejected an offer using top-result membership.
