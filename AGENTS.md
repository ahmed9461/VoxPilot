# VoxPilot — Repository Working Rules

This repository is the source of truth for VoxPilot.

## Mandatory read order before any change

Before changing code, configuration, deployment, tests, or docs, read in this order:

1. `AGENTS.md`
2. `docs/PROJECT_MEMORY.md`
3. `docs/PROJECT_STATUS.md`
4. `docs/ARCHITECTURE.md`
5. `docs/DECISIONS.md`
6. `ROADMAP.md`
7. the active plan referenced by `docs/PROJECT_STATUS.md`
8. the latest relevant entries in `docs/PROGRESS_LOG.md`
9. recent commits, current branch/HEAD, git status/diff, and the latest CI run that actually matches HEAD

Do not start implementation from a stale prompt or chat summary when the repository says something different.

## Planning and memory discipline

- Every meaningful task must have an active plan before implementation.
- Update `docs/PROJECT_STATUS.md` whenever the current phase, active plan, blockers, validation state, or next step changes.
- Append to `docs/PROGRESS_LOG.md` after each completed logical phase. Record what changed, why, validation performed, and remaining work.
- Update `docs/PROJECT_MEMORY.md` whenever a durable project fact, invariant, integration detail, or operational lesson changes.
- Record architecture/product decisions in `docs/DECISIONS.md`; do not hide important decisions only in commit messages.
- Never delete useful history from memory/progress files just to make them shorter. Summarize old detail only when the retained meaning is complete.
- If work is interrupted, the repository must still contain enough state for another agent to continue without guessing.

## Product invariants

1. VoxPilot is a personal, owner-only Telegram control plane for Fish Audio S2 Pro on temporary Vast.ai GPU instances.
2. It is a text-to-speech / voice-cloning product, not a conversational AI assistant.
3. Do not add LLM system prompts, developer prompts, personas, chat history, RAG, or prompt-enhancement layers.
4. S2 inline performance tags such as `[whisper]`, `[excited]`, and `[angry]` are model-native speech controls, not chat prompts.
5. Use only Fish S2 controls that the pinned official API actually supports. Do not invent speed/pitch/etc. request fields unless upstream adds them and the integration is updated deliberately.
6. Voice cloning uses user-provided reference audio plus its matching reference text. Do not silently transcribe it with another model unless that becomes an explicit product decision.
7. Keep voice samples and generated audio out of Git.
8. Secrets stay in `.env` or runtime environment variables and must never be committed.
9. `VAST_API_KEY` and Telegram credentials stay on the controller. Only the generated Fish API bearer token is sent to the temporary Vast instance.
10. The Fish API must require bearer authentication on the public mapped port.
11. Vast marketplace refreshes must be real API requests, never shuffled cached results presented as fresh.
12. Re-check the selected offer against the configured price ceiling immediately before rental.
13. Instance lifecycle operations must be serialized to tolerate rapid/repeated Telegram taps.
14. Persist lifecycle/billing metadata so controller restarts can recover an existing rental.
15. Automatic destruction after provisioning failure is opt-in; never destroy a paid instance silently by default.
16. Telegram callbacks must acknowledge safely, ignore harmless stale/no-op callback errors, and provide a classic-message fallback when Rich Messages are unavailable.
17. Normal Telegram screens are user-facing: do not expose implementation clutter, raw exceptions, tokens, or secrets.
18. Prefer the smallest maintainable design. Do not copy PixelPilot modules that VoxPilot does not need.

## PixelPilot reuse policy

PixelPilot is a reference implementation only. Reuse/adapt concepts proven useful for:
- Vast.ai search, normalization, rental, recovery, start/stop/destroy
- stale-offer price-cap protection
- offer refresh comparison
- per-second active rental meter
- Cost Guard
- owner-only middleware
- safe Telegram callback/edit helpers
- native Telegram Rich Messages with fallback
- project memory, progress, decisions, tests, and deployment discipline

Do not copy:
- Qwen/vLLM/Whisper paths
- chat history
- assistant personalities, prompt profiles, or prompt composition
- image/video understanding
- inference gateway layers that Fish's authenticated API server already replaces
- any obsolete PixelPilot migration code not needed by VoxPilot

## Quality bar

- No unnecessary dependency or abstraction.
- Validate imports, error paths, concurrency, and cleanup.
- Prefer explicit typed data structures.
- Add tests for every bug-prone boundary: Vast payload normalization, price caps, Fish request encoding, emotion-tag composition, billing, voice file handling, and callback no-ops.
- Documentation and code must stay synchronized in the same change.
