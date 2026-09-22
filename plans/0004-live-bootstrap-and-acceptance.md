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

## Warm-start finding — 2026-09-23

- The first live warm-start request returned without a provider-running confirmation. The controller timed out after 120 seconds, then recovered a local `stopped` phase while the provider subsequently became `running`. Fish health was ready and the local meter resumed, but recovery refused to enter provisioning from `stopped`, leaving the displayed phase stale.
- Vast also reports `actual=exited`, `intended=running`, `cur=running` during startup. That is a transition, not a confirmed failure. The Vast SDK lifecycle methods return a response body with `success`; the gateway currently ignores a possible `success=false`.
- Repair response validation, transient status normalization, and stopped-to-running recovery. Add focused tests, rerun the full gate and CI, then revalidate on the original rental. Keep the existing data and rental throughout.
- Review also found that a restart during a pending stop could lose stop intent, and a retry after delayed provider startup could send a redundant start request. Cover both with the same lifecycle repair.

## Deployed acceptance checkpoint — 2026-09-23

- Lifecycle follow-up `e226bf0` passed local checks and matching GitHub Actions run `35787451378` with 40 tests. New-VPS is on the same code after a consistent SQLite backup; the service is active and recovered the original rental as `ready` with active billing.
- Vast inventory has one tracked running rental. Authenticated Fish health, mapped listener, GPU compute process, Arabic MP3 generation, and synthetic-reference `[whisper]` generation passed on the preserved disk. The synthetic prompt marker was absent from the Fish log.
- Owner voice quality and Telegram delivery need owner-provided input. Live destroy is deferred because the existing working paid rental should not be removed merely to exercise that path. The rental continues to accrue provider charges while running.

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
