# Plan 0008 — Audit repairs and network-aware offers

Created: 2026-10-27
Status: IMPLEMENTED — matching CI/integration tracked in the maintenance PR; not deployed
Base: main at 54b08588a224d0b2baa9e58d87c6100cfd1deecd

## Owner authorization and exclusions

Implement the audit fixes, improve rental recovery and prioritize faster internet offers without raising the configured price ceiling. Clean up only branches proven merged and genuinely disposable development artifacts. HTTPS changes are explicitly deferred by the owner. Do not rent, start, stop or destroy paid resources for tests; do not delete voices, configuration, databases, useful project history or secrets. No live deployment is implied by a repository-only test result.

## Work

1. Preserve the current baseline and validate against matching CI.
2. Add regression tests for atomic billing, stale readiness tasks, resource-bound destructive confirmations, pending rental recovery, environment precedence, Telegram upload errors and wizard cancellation.
3. Search a broad live offer pool with network-aware ordering, configurable download/upload thresholds and explicit fallback. Preserve price/reliability/VRAM/disk/port constraints and exact offer revalidation. Distinguish advertised Mbps from measured end-to-end download throughput.
4. Repair ambiguity handling without retrying an unknown create or silently deleting paid instances; provide pending status, periodic reconciliation and warnings.
5. Strengthen CI across supported Python baselines, dependency/security checks and reproducibility where verifiable.
6. Update project memory, status, decisions, architecture, test plan and progress with actual validation and remaining live acceptance.
7. Merge only after successful checks, then remove only fully merged branches with a guarded allowlist and fresh ancestry verification.

## Validation

Use isolated temporary databases, fake provider clients and synthetic audio only. Record actual test counts and failures. A successful automated suite does not establish real Vast inventory, download speeds, Fish audio quality or controller deployment.

## Implementation checkpoint — 2026-10-27

All scoped code repairs and network-aware selection are implemented with 149 local passing tests and Ruff/syntax/compilation checks. Documentation, exact dependency locks and a Python 3.11/3.12/3.13 test matrix are synchronized. See `docs/AUDIT_REPAIRS_2026-10-27.md` for upgrade and pending-recovery boundaries.

Not claimed complete: HTTPS (owner deferral), clean dependency security scan (upstream incompatible pins), branch protection (missing administration permission), current controller deployment, live GPU/voice/market acceptance. Do not infer those from a successful regression suite. Cleanup is gated on fresh ancestry and exact expected heads; its result is recorded in the integration Actions log rather than assumed.
