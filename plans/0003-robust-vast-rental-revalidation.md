# Plan 0003 — Robust Vast Rental Revalidation

Status: ACTIVE
Created: 2026-09-22

## Trigger

After deploying plan 0002, live rental attempts still returned "offer changed or unavailable" immediately, while visually equivalent offers remained in the refreshed marketplace list.

This indicates the exact text-query revalidation path is still too brittle for live Vast marketplace behavior.

## Goal

Keep price/policy protection without false rejecting every rental.

## Approach

1. Add a dedicated Vast gateway lookup for the selected offer.
2. First query Vast with a pre-parsed numeric query dict:
   `{"id": {"eq": <offer_id>}}`
   so the offer ID bypasses the text query parser entirely.
3. If that direct lookup returns no row, perform a wide fresh policy search (up to 200 rows) and match the selected ID locally.
4. Validate the returned selected offer locally against VoxPilot policy:
   - one GPU
   - minimum VRAM
   - minimum reliability
   - hard total hourly price ceiling
   - required disk capacity
   - verified policy
   - direct port count
   - minimum download speed
   - datacenter policy when enabled
5. Only then call Vast create-instance.
6. Preserve `cancel_unavail=true` so Vast rejects a race where the offer disappears between validation and create.
7. Add focused tests covering:
   - numeric ID lookup
   - wide-search fallback
   - policy rejection
   - successful create after exact lookup
8. Update project status/memory/progress and validate CI.

## Completion

The plan is complete when CI is green and the controller can be updated for a third live rental attempt.
