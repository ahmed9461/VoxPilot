# Plan 0006 — Review and safely integrate PR #1

Created: 2026-10-20

## Scope and constraints

Review every changed file against current main `818163bb1fc7dc6d96305a4a8b59d97fe7789e81`. Preserve the owner's original clean checkout, saved voices, runtime data, and effective sampling settings. Work in an isolated local clone. Do not rent a Vast instance, deploy, restart a service, read private-key contents, or change security settings. Server deployment awaits explicit clarification.

## Work

1. Inspect repository instructions, original local status, both workflow trees, complete diff, and matching CI.
2. Reproduce parser boundary failures (nested/unbalanced parentheses and existing manual tags) and legacy settings migration behavior in regression tests.
3. Preserve protected syntax and leave consistency mode disabled for legacy settings without an explicit toggle; retain default-on behavior for fresh installations.
4. Verify pinned Fish tags/request fields, run full Python 3.12 tests, compilation, bootstrap syntax, and whitespace checks locally.
5. Synchronize architecture, memory, status, decisions, and progress with actual evidence. Push scoped fixes and require successful CI for the final SHA.
6. Recheck current main/head and branch protection through the normal GitHub merge path. Merge only if all gates pass and merging cannot trigger deployment.

## Rollback

Before merge, main remains unchanged. After merge, revert the merge commit with a separate PR and normal checks; never force-push main. No controller rollback is needed while deployment is paused. A later authorized deployment must first back up SQLite and voice data and retain its previous code SHA; that action is outside this review.

## Initial evidence

- Original local checkout: clean main at `4fc38067c1357a78728899825718e0a38ad220ac`.
- Reviewed PR head: `cc43b38f21a62c9577f4a89562782ccc089fafb0`; current main is an ancestor.
- Both branches contain only `.github/workflows/tests.yml`, which installs dependencies and runs shell syntax, compilation, and pytest. No deployment step.
- GitHub Actions PR run `36482561868` succeeded for the original PR head; local tests must still be run independently.

## Local review result

Parser protected-region and legacy settings migration repairs are implemented with regression tests. Full Python 3.12.10 gate passed: 90 tests, compileall, bootstrap syntax, and diff whitespace. Pinned Fish README/schema were checked directly. No blocking code finding remains from the local review. Push/final-head CI and merge are the remaining integration gates; deployment remains paused.

Repair SHA `427843c30484a0e7f1adbbdd8130cbf108d179d0` passed both matching CI runs (`39426261177` PR, `39426251484` push), with 90 tests confirmed in the PR job log. Main is unchanged, the simulated merge tree matches the tested tree, and the original checkout remains clean. Final documentation synchronization also requires matching CI; merge must use the expected final head SHA. Deployment is a separate pending owner decision.
