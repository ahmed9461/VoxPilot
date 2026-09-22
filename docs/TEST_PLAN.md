# VoxPilot — Test Plan

## Automated unit tests

### Vast
- query uses GB units for `gpu_ram`
- raw offer VRAM MB normalizes to GB
- reliability normalization
- price sorting
- hard maximum price enforcement before rental
- mapped-port extraction from known Vast payload shapes

### Fish client
- health request includes bearer auth
- TTS endpoint and MessagePack content type are correct
- reference audio/text are encoded together
- official defaults/ranges are preserved
- non-2xx responses become sanitized client errors

### TTS settings
- emotion key maps only to curated native Fish tags
- normal mode adds no tag
- selected global tag prepends without rewriting the target text
- invalid settings are rejected

### Voice store
- generated internal IDs
- safe extension handling
- save/load/list/delete
- metadata survives process restart
- traversal-like filenames cannot control storage paths

### Billing
- begin
- pause
- resume
- active cost calculation
- final snapshot

### Telegram helpers
- stale callback errors are ignored
- no-op message edits are ignored

## Static validation

CI must run:
- Python compileall on `src` and `scripts`
- pytest

## Live acceptance

After automated tests pass:

1. Configure controller secrets.
2. Search Vast and verify results are fresh and respect policy.
3. Rent a 24 GB+ GPU.
4. Verify bootstrap reaches Fish health.
5. Upload a 10–30 second reference audio sample and matching transcript.
6. Generate neutral Arabic speech.
7. Generate with at least three emotion/performance presets.
8. Verify output is delivered through Telegram.
9. Stop the server and verify billing meter pauses.
10. Start it and verify Fish becomes ready again.
11. Destroy it and verify final billing snapshot remains.
12. Rent another instance and verify the saved controller voice can be reused without re-uploading.
13. Rapidly tap lifecycle/settings buttons and verify no duplicate rental or broken callback state.
14. Review logs for secrets/audio leakage.
