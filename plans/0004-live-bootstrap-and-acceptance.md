# Plan 0004 — Live bootstrap recovery and Fish acceptance

Status: ACTIVE — remaining owner live acceptance only; controller deployment COMPLETED
Created: 2026-09-22
Last reconciled: 2026-10-20

## Authoritative checkpoint — 2026-10-20

Controller deployment and verification are complete under `plans/0007-authorized-controller-update.md`. PR #1 application merge `93efbea89d20f23b13d8aacac7952dc26b499ada` passed [matching CI](https://github.com/ahmed9461/VoxPilot/actions/runs/39428688670) with 90 tests and was deployed with owner approval. Documentation synchronization `f307b494a6d8ee1cd95d666bf383819ce40ce82f` also passed [matching CI](https://github.com/ahmed9461/VoxPilot/actions/runs/39431904923). Configuration and voice data were preserved.

This checkpoint supersedes the controller-update/restart work and deployment-pending statements in the September history below. Do not repeat deployment or restart the service to complete this plan's documentation reconciliation. No server or provider check is part of this follow-up. September rental observations do not establish current Vast inventory, running/stopped state, or billing; any later live action requires fresh evidence and appropriate owner authorization.

## Remaining owner live acceptance

These items require a suitable instance and/or owner-provided input and are separate from the completed controller update:

- Real Arabic synthesis, short-reference voice cloning with its matching transcript, native performance directions, and Telegram audio delivery/quality acceptance.
- Post-patch Fish log privacy verification using a synthetic marker without exposing owner text.
- Live marketplace/rejection diagnosis, bootstrap/warm-start behavior, and lifecycle/billing acceptance where the required instance and explicit owner authorization are available. Do not rent, start, stop, or destroy an instance merely to reconcile this document or exercise a test.

## Historical evidence and work — 2026-09-22 to 2026-09-24

The sections below retain the observations and work plan from their recorded dates. Their provider states, billing statements, and operational instructions are historical context, not current instructions or evidence of current resources. The checkpoint and remaining-acceptance list above define the current scope.

### Evidence at start

- `main` is at `1c46248558375eb8836100552ae502a0cc2c4d80`; the matching GitHub Actions run `35777732756` succeeded.
- New-VPS runs the same commit, with `voxpilot.service` active and one tracked Vast rental.
- The rental is `running`, has a mapped API port, and is accruing charges. Fish `/v1/health` is not ready.
- Vast logs stop after `Cloning into '/workspace/VoxPilot'...`; the controller has no later readiness event. Disk usage alone does not establish bootstrap progress.
- Controller SSH keys are not yet authorized on the rented instance. Read-only Vast remote execution returned `invalid_args`, so a direct shell diagnostic is needed.

### Live findings after diagnostic access

- Scoped SSH access was attached to the original rental. The clone, Fish environment, and S2 Pro download had completed. Fish had stalled during CUDA initialization with error 804.
- The image's compatibility `libcuda` was loaded ahead of the mounted host driver. Selecting the host library made an actual CUDA operation pass; the existing rental then completed Fish warmup and authenticated health.
- Arabic TTS and a synthetic-reference request with `[whisper]` returned MP3 responses. Quality with the owner's own voice and Telegram delivery remain to be accepted.
- Controller restart recovered the same rental. A live stop exposed asynchronous provider state and the `exited`/`stopped` payload mismatch. The rental is preserved and currently stopped.

### Warm-start finding — 2026-09-23

- The first live warm-start request returned without a provider-running confirmation. The controller timed out after 120 seconds, then recovered a local `stopped` phase while the provider subsequently became `running`. Fish health was ready and the local meter resumed, but recovery refused to enter provisioning from `stopped`, leaving the displayed phase stale.
- Vast also reports `actual=exited`, `intended=running`, `cur=running` during startup. That is a transition, not a confirmed failure. The Vast SDK lifecycle methods return a response body with `success`; the gateway currently ignores a possible `success=false`.
- Repair response validation, transient status normalization, and stopped-to-running recovery. Add focused tests, rerun the full gate and CI, then revalidate on the original rental. Keep the existing data and rental throughout.
- Review also found that a restart during a pending stop could lose stop intent, and a retry after delayed provider startup could send a redundant start request. Cover both with the same lifecycle repair.

### Deployed acceptance checkpoint — 2026-09-23

- Lifecycle follow-up `e226bf0` passed local checks and matching GitHub Actions run `35787451378` with 40 tests. New-VPS is on the same code after a consistent SQLite backup; the service is active and recovered the original rental as `ready` with active billing.
- Vast inventory has one tracked running rental. Authenticated Fish health, mapped listener, GPU compute process, Arabic MP3 generation, and synthetic-reference `[whisper]` generation passed on the preserved disk. The synthetic prompt marker was absent from the Fish log.
- Owner voice quality and Telegram delivery need owner-provided input. Live destroy is deferred because the existing working paid rental should not be removed merely to exercise that path. The rental continues to accrue provider charges while running.

### Owner Telegram generation failure — 2026-09-23

- The owner reported that the server status looked healthy while Telegram generation failed. Controller logs show authenticated Fish `/v1/health` returning 200 but `/v1/tts` returning 500. The live Fish error is CUDA out of memory during those requests.
- The active saved OGG reference is about 89.8 seconds and another saved reference is about 47.7 seconds. Both exceed Fish S2's documented typical 10–30 second reference length. The active transcript is unusually short for the recording; its match to the audio cannot be inferred. The audio files must remain preserved.
- Upload and generation paths currently accept references based only on bytes/file size, with no decoded-duration check. The generic Telegram failure text incorrectly suggests Fish is not ready. There is no direct way to select the default, non-cloned voice while a long reference is active.
- Pinned Fish unconditionally calls `conversation_gen.visualize(...)`, which writes request text to stdout even with Loguru set to WARNING. The current Fish log contains prompt material. The bootstrap patch removes that call; `git apply --check` passed against the actual pinned Fish checkout. The owner is deleting the GPU rental, so its ephemeral logs will be removed with it. Verify no new prompt text appears when a later rental is available.
- Duration validation for new and existing references, an actionable Telegram message and default-voice choice, and distinct health/generation status were deployed in `5229d1f`. Local 48-test gate and matching GitHub Actions run `35794540192` passed. A consistent SQLite backup preceded New-VPS deployment; `.env` metadata and two saved voices were preserved. The owner deleted the GPU rental during this repair. Fresh provider inventory shows zero instances; the controller has no tracked instance or active meter and retains a final billing snapshot. Live short-reference generation and post-patch GPU log acceptance remain pending a future owner rental.

### Historical work plan

#### 2026-09-24 — Repeated rental rejection

- The owner reports that selecting a displayed offer returns “offer changed or unavailable” and immediately shows the same offer cards again; the controller has no tracked rental in the latest deployment checkpoint.
- Code review found that marketplace display trusts the provider query while click-time rental applies additional local policy checks. `vastai==1.6.0` also sends different default `rented` filters for string versus pre-parsed dictionary searches. These discrepancies can make a displayed offer fail its own validation; the exact live rejection needs controller evidence.
- Align search and exact-ID validation with the same rental policy, filter locally invalid offers before display, report a specific safe rejection reason in operational events, and avoid immediately re-offering a failed ID in the response. Distinguish a definitive Vast create rejection from an ambiguous create outcome without losing the existing duplicate-rental guard.
- Cover mismatched offer metadata, changing prices, definitive provider rejection, ambiguous errors, and repeated taps with focused tests. Run the local gate, push the fix, and verify matching CI. No Vast instance should be created by this repair; live acceptance requires the owner to use the deployed controller.
- Repair commit `ad597212` is on `main`. Local gate: 58 pytest tests, compileall, `bash -n`, and `git diff --check` passed. Matching GitHub Actions run `36037444914` completed successfully. At that September checkpoint, controller deployment and live owner acceptance were pending. The 2026-10-20 checkpoint above closes the controller deployment item; tests alone still do not establish the live rejection cause or a successful rental.

1. **Historical investigation completed:** scoped diagnostics examined the on-start process, checkout, bootstrap logs, environment, disk/cache, Fish processes, and GPU activity to distinguish slow progress from a stall.
2. **Historical repairs completed:** demonstrated bootstrap/runtime defects were repaired while preserving data and avoiding disclosure of credentials or voice files.
3. **Review completed:** lifecycle, recovery, billing, marketplace, Fish requests, voice storage, Telegram, and logging boundaries received focused regression coverage.
4. **Automated gate completed:** the reviewed application passed bootstrap syntax, compilation, full pytest, whitespace checks, and matching CI; the current checkpoint records the later 90-test gate.
5. **Controller deployment completed:** the owner-approved update and controller verification are recorded in plan 0007 and the checkpoint above. This is not an instruction to update or restart New-VPS again.
6. **Live acceptance remains:** real TTS, cloning, performance controls, delivery, lifecycle, and cleanup acceptance are limited to the explicitly listed remaining work above and require the appropriate instance, input, and owner authorization.

### Historical safety constraints — September context

- Do not rent a new instance while the owner is deleting the original.
- Do not issue a second stop/destroy request while the owner handles deletion.
- Preserve controller data and billing metadata.
- Before each meaningful edit, identify the root cause and review the proposed fix against restart, network failure, repeated taps, incomplete Vast responses, and secret handling.
