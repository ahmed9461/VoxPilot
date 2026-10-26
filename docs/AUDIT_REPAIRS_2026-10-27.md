# Audit repairs and upgrade checklist — 2026-10-27

## Delivered scope

| Area | Change |
|---|---|
| Billing | Atomic SQLite read/modify/write, idempotent finalization, explicit connection closure |
| Rental | One create attempt, durable unique-label intent, complete paged inventory, startup/periodic/manual reconciliation and warning |
| Lifecycle | Shared lock, generation-aware readiness/status/recovery, stale task rejection, activity-aware idle cleanup |
| Delete | Current resource ID + generation + expiring single-use confirmation; legacy callbacks rejected |
| Marketplace | Download-first + price-first search pools, speed tiers then price, exact pre-rent revalidation |
| Bootstrap | Restore allowlisted PID1 environment before defaults, fail-fast branch/tag/commit checkout, configurable model revision |
| Telegram | Public 20 MB cap including actual received bytes, handled retry errors, home/start/cancel and in-flight cancellation safety |
| Maintenance | Exact runtime/development dependency locks, static checks, measured coverage and 3-version CI |

## Network defaults

```dotenv
VAST_MIN_INET_DOWN_MBPS=500
VAST_PREFERRED_INET_DOWN_MBPS=1000
VAST_MIN_INET_UP_MBPS=50
VAST_SLOW_INET_DOWN_MBPS=100
```

Higher speed tiers (500/1000/2000/5000 Mbps at the preferred default) rank first; price decides within a tier. Slow alternatives require pressing their separate UI button and do not relax price, VRAM, reliability, disk or port constraints. Market refreshes query the API, not a shuffled cache. Existing environment values remain explicit overrides. Advertised speeds are not end-to-end tests; Mbps divided by eight is only a theoretical MB/s conversion. Disk/GPU initialization, provider congestion, model hosting and transfer charges still affect cost/readiness. No paid resource was used to measure improvement.

## Safe pending recovery

The SDK no longer automatically replays an uncertain create. A label is written before the request; periodic/status recovery can adopt the matching instance later. A clear provider rejection followed by complete absence frees the failed attempt. Timeouts plus empty inventory remain unresolved rather than risking a second paid rental. The UI displays the pending label/status and can re-check it. An indefinitely ambiguous case still needs provider/account investigation; never delete the local guard blindly. Multiple matches are surfaced instead of picking or deleting one arbitrarily.

## Upgrade checklist — not a deployment record

1. Record the approved merge commit; back up `.env`, SQLite using SQLite's backup API, and the controller's voice directory. Do not print secret values or place backups in Git.
2. Check that the controller checkout is clean. Fast-forward only to the approved merge; do not reset over local work.
3. In the existing isolated controller environment, install `requirements.lock`, then install the project with `pip install --no-deps -e .`; run `pip check`. Development tools belong in CI, not the production service.
4. Update only the four network keys above in the existing `.env` if the faster policy is desired. Do not copy `.env.example` over credentials, lower safety thresholds automatically, increase the hourly ceiling, or modify HTTPS/TLS flags.
5. Restart only the existing controller service using its actual known unit name, verify polling and data preservation, and inspect pending state before any paid action. This maintenance did not perform those steps on a server.
6. Pin `VOXPILOT_REPO_REF` to the approved tested commit for reproducible future bootstrap. Pin `FISH_MODEL_REVISION` only after verifying the intended official model revision; it remains `main` here rather than inventing a hash. Docker automatic tags and model contents are not claimed fully immutable.

## Validation and remaining risk

149 local Python 3.13 tests passed; matching remote Python 3.11/3.12/3.13 runs are required for integration. Tests use temporary databases, synthetic inputs and mocked provider requests. The security report is not clean: SDK-pinned Pillow/cryptography have unresolved advisories, documented in SECURITY.md. HTTPS is explicitly deferred. Branch protection was not enabled because administration permission is unavailable. Live marketplace speeds, real voice quality and actual deployment remain separate acceptance items.

Cleanup is restricted to exact old branch heads already reachable from fresh main. A changed/unmerged branch must be preserved. Temporary maintenance workflows and generated build/test caches are excluded from the final application tree. No runtime database, saved voice, user configuration, useful historical plan or paid server is a cleanup target.
