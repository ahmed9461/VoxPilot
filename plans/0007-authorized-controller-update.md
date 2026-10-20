# Plan 0007 — Authorized controller update

Created: 2026-10-20

## Scope

The owner explicitly approved PR #1 draft removal, merge, and updating the existing controller. This supersedes plan 0006's initial deployment pause. Preserve configuration, voice data, sampling controls, secrets, and security settings. Do not rent another server or GPU.

## Gates

1. Recheck the reviewed head, main, CI, and workflows before an expected-head normal merge.
2. Inspect the existing installation and preserve a consistent private backup and rollback target before updating.
3. Apply only the tested application update; retain existing dependencies and configuration.
4. Verify imports and offline settings/parser checks as the service user, then confirm actual polling readiness and stable service operation.
5. Compare stored settings, voice data, environment, and service configuration with the pre-update snapshot. Restore the previous code if acceptance fails, without overwriting newer user data.
6. Keep sensitive deployment paths, runtime values, identities, and detailed operational history outside the public repository. Publish only the result and public CI evidence.

## Result

Completed. PR #1 merged with expected head `bd1350764252eb4111fa7ac1d853f1244fec287e` into `93efbea89d20f23b13d8aacac7952dc26b499ada`. Final PR/push CI and [merge CI](https://github.com/ahmed9461/VoxPilot/actions/runs/39428688670) passed 90 tests.

The owner-approved update of the existing controller is deployed and verified. Existing configuration, saved voices, active voice selection, sampling values, and secrets were preserved. Offline checks, service readiness, data integrity, and preservation checks passed. A private backup and code rollback target remain available. No additional server was rented.

Live audio quality, cloning, delivery, and GPU log acceptance remain separate owner acceptance work. Documentation-only synchronization requires matching CI and normal merge; it does not require another application restart when executable sources are identical.
