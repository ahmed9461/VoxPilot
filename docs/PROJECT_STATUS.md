# VoxPilot — Project Status

Last updated: 2026-09-22

## Current phase

**Phase 1 — Foundation and first working controller/runtime**

Planning is complete. Implementation is the next step.

## Active plan

`plans/0001-foundation-and-vast-fish-runtime.md`

## Repository state

- Repository initialized.
- `AGENTS.md` contains mandatory workflow, memory discipline, invariants, and PixelPilot reuse boundaries.
- PixelPilot architecture and recent Vast/Rich Message implementation were inspected as a reference.
- Current Fish Speech server/API/docs were inspected from the official upstream repository.
- Fish source baseline is pinned to commit `214da3cd841bda85da2496b96cd3c4d7edb1337e`.
- No application code has been committed yet.

## Decisions already locked

- Use Fish Audio S2 Pro.
- Use temporary Vast.ai GPU instances.
- 24 GB VRAM minimum by default.
- Use the official Fish API directly instead of a custom inference gateway.
- Keep saved voice references on the controller.
- Require matching reference text supplied by the owner.
- No Whisper.
- No chat model and no prompt/persona subsystem.
- Use model-native emotion/performance tags.
- Preserve the useful Vast lifecycle, billing, recovery, Cost Guard, safe callback, and Rich Message patterns learned from PixelPilot.

## Validation state

Reference audit:
- PixelPilot structure: complete.
- Vast lifecycle patterns: complete.
- Telegram Rich Message pattern: complete.
- Fish S2 official server endpoint/auth schema: complete.
- Fish S2 official inference hardware baseline: complete.

Code validation:
- not started yet.

## Current blockers

None.

## Next action

Implement the controller foundation, Fish client, local voice store, Vast lifecycle, Telegram flows, bootstrap script, tests, and CI according to plan 0001.
