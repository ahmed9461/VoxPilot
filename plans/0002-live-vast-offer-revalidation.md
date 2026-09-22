# Plan 0002 — Live Vast Offer Revalidation Hardening

Status: COMPLETE
Created: 2026-09-22

## Trigger

The first live rental attempt failed before instance creation with:

`OrchestratorError: Offer is no longer available; refresh the market`

The selected RTX 3090 may have been falsely rejected because rental revalidation searched only the current displayed/top result set instead of the selected offer ID directly.

A second mismatch was identified: marketplace pricing used the Vast SDK's default allocated storage (5 GB) while VoxPilot actually rents 60 GB.

## Goal

Make live rental revalidation precise, price-consistent, and user-friendly.

## Changes

1. Search/display prices must use `VAST_DISK_GB` as the SDK `storage` amount.
2. Add exact selected-offer lookup using Vast's supported `id=<offer_id>` filter plus the normal VoxPilot rental policy.
3. Before create:
   - query the selected offer ID directly;
   - require it to still be rentable and policy-compliant;
   - enforce the hard hourly price ceiling using the 60 GB storage price;
   - never infer disappearance merely because the offer is not in the top displayed results.
4. Show a specific Telegram message when the selected offer truly disappeared or became ineligible, and refresh the visible offer list.
5. Add focused tests for exact-ID lookup, storage-aware pricing, and stale-offer UX.
6. Update project memory/progress/status with the live finding.

## Completion

- tests and compile pass
- GitHub Actions green on exact HEAD
- controller can be updated on /opt/VoxPilot and rental retried


## Completion checkpoint

Implemented and validated on 2026-09-22.

GitHub Actions:
- run: `35776271041`
- head: `1f37aa13f04932947893f1f0f13da8ff1927ec18`
- conclusion: success
- pytest: 14 passed

The first live attempt created no Vast instance; deployment of this fix is required before retrying.
