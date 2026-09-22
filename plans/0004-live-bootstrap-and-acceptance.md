# Plan 0004 — Live bootstrap recovery and Fish acceptance

Status: ACTIVE
Created: 2026-09-22

## Evidence at start

- `main` is at `1c46248558375eb8836100552ae502a0cc2c4d80`; the matching GitHub Actions run `35777732756` succeeded.
- New-VPS runs the same commit, with `voxpilot.service` active and one tracked Vast rental.
- The rental is `running`, has a mapped API port, and is accruing charges. Fish `/v1/health` is not ready.
- Vast logs stop after `Cloning into '/workspace/VoxPilot'...`; the controller has no later readiness event. Disk usage alone does not establish bootstrap progress.
- Controller SSH keys are not yet authorized on the rented instance. Read-only Vast remote execution returned `invalid_args`, so a direct shell diagnostic is needed.

## Live findings after diagnostic access

- Scoped SSH access was attached to the original rental. The clone, Fish environment, and S2 Pro download had completed. Fish had stalled during CUDA initialization with error 804.
- The image's compatibility `libcuda` was loaded ahead of the mounted host driver. Selecting the host library made an actual CUDA operation pass; the existing rental then completed Fish warmup and authenticated health.
- Arabic TTS and a synthetic-reference request with `[whisper]` returned MP3 responses. Quality with the owner's own voice and Telegram delivery remain to be accepted.
- Controller restart recovered the same rental. A live stop exposed asynchronous provider state and the `exited`/`stopped` payload mismatch. The rental is preserved and currently stopped.

## Work

1. Gain scoped diagnostic access to the existing rental and inspect on-start process, repository checkout, bootstrap logs, environment, disk/cache, Fish processes, and GPU activity. Compare two observations to distinguish slow progress from a stall.
2. Fix the demonstrated bootstrap or runtime root cause with the smallest maintainable change. Keep the existing rental and its cache when possible. Do not expose credentials or voice files.
3. Review adjacent lifecycle, recovery, billing, marketplace, Fish request, voice-store, Telegram, and logging boundaries against live evidence. Add focused tests for actual defects.
4. Run bootstrap syntax, compile, full pytest, and focused boundary tests. Review diff and push logical commits. Confirm GitHub Actions succeeds for the final HEAD.
5. Update New-VPS code to that HEAD without touching `.env`, SQLite, or voices. Restart the service only when safe; verify recovery, systemd, Vast inventory, and Fish health.
6. Complete real TTS, voice cloning, native emotion tags, stop/start, and cleanup only where the required reference audio and owner interaction are available. Record each live result and any remaining acceptance gate precisely.

## Safety

- Do not rent a second instance while the existing one is repairable.
- Do not stop or destroy the paid instance just to test a code path.
- Preserve local data, existing billing metadata, and temporary GPU cache.
- Before each meaningful edit, identify the root cause and review the proposed fix against restart, network failure, repeated taps, incomplete Vast responses, and secret handling.
