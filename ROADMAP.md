# VoxPilot — Roadmap

## Phase 1 — Foundation and first working runtime

Active plan: `plans/0001-foundation-and-vast-fish-runtime.md`

Deliver:
- owner-only Telegram controller
- project memory/status/progress discipline
- Vast marketplace search and deterministic ranking
- rent/start/stop/destroy/recovery
- billing meter and Cost Guard
- Fish S2 pinned bootstrap
- authenticated Fish health/TTS client
- controller-side voice store
- active voice selection
- emotion/performance presets
- advanced Fish sampling controls
- text-to-speech delivery
- Rich Message UI with fallback
- automated tests and CI

## Phase 2 — Live acceptance and hardening

Only after Phase 1 CI is green:
- first real Vast rental
- measure bootstrap/model-download time
- verify 24 GB GPU classes
- verify Arabic cloning quality
- verify emotion tags in real generation
- inspect stop/start behavior and cache persistence
- tighten timeout/retry behavior from evidence
- optimize bootstrap if hourly rental time is being wasted

## Phase 3 — Quality-of-life improvements

Driven by real use, not speculation:
- voice rename/export/import if useful
- favorite emotion presets
- per-voice default settings
- generation history metadata only, if useful
- faster warm starts/templates if live measurements justify them
- optional streaming audio only if Telegram UX and Fish runtime behavior justify the complexity

## Explicitly out of scope unless later requested

- general-purpose AI chat
- LLM prompt engineering
- assistant personalities
- image/video understanding
- automatic voice transcription
- commercial multi-user billing
- public SaaS accounts
