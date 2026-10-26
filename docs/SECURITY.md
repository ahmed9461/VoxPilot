# VoxPilot — Security

## Secrets

Never commit:
- `TELEGRAM_BOT_TOKEN`
- `VAST_API_KEY`
- generated Fish API bearer tokens
- private voice samples
- SQLite runtime state

Use `.env` locally and runtime environment variables on the Vast instance.

## Fish API exposure

The Fish API is bound to the Vast instance's public mapped port, therefore it must always start with `--api-key`.

The controller generates a fresh random token when a new rental is created. The token is stored only in controller runtime state/SQLite and passed to the temporary instance through Vast environment injection.

## Voice data

Voice samples may be biometric/sensitive data. VoxPilot stores them only in the configured controller voice directory and keeps that directory out of Git.

The controller must:
- enforce a size limit
- use generated internal IDs instead of raw filenames as storage paths
- reject unsafe extensions/path traversal
- remove the voice directory atomically/best-effort on owner deletion

## Telegram access

All bot updates pass through owner-only middleware. Unapproved user IDs receive no bot actions.

## Vast credentials

`VAST_API_KEY` never leaves the controller. The rented server does not need it.

## Logs

Do not log:
- Telegram/Vast/Fish tokens
- full voice audio bytes
- full generated audio bytes
- raw MessagePack request bodies

Operational logs may include:
- instance ID
- offer ID
- lifecycle phase
- GPU metadata
- durations
- HTTP status codes
- sanitized exception classes/messages


## Transport deferral (2026-10-27)

The owner explicitly deferred HTTPS changes. The existing HTTP defaults and TLS verification flags are unchanged. Bearer authentication does not encrypt text, reference audio or tokens in transit. Do not represent this deferral as secure public transport; revisit TLS or a private tunnel separately.

## Known upstream dependency blocker (2026-10-27)

The official `vastai==1.6.0` dependency metadata pins `cryptography==49.0.0` and `pillow==12.2.0`. A full `pip-audit` run on the newly resolved runtime lock reported 64 advisory records in those two distributions (some records repeat the same advisory; this is not 64 distinct confirmed exploitable application bugs). The cryptography advisory includes PYSEC-2026-3552, fixed in 50.0.0; Pillow reports fixes through 13.0.0. Attempted resolution of the current Vast 1.9.1 with patched minimums also fails because it still requires Pillow 12.2.0.

These are existing upstream dependency risks, not evidence of compromise or proof that VoxPilot exercises every vulnerable image/PKCS7 path. They are NOT fixed by this maintenance. Do not force-install conflicting versions, edit installed dependency metadata, ignore advisories silently, or claim that tests prove security. Use the artifact from `Dependency audit (report only)` for all findings. That step is nonblocking specifically to expose this pre-existing upstream blocker while delivering independent lifecycle/rental fixes; it has a warning and an explicit outcome in the job summary. Review upstream pins or replace the SDK in a separate contract-tested change, then make the audit a required gate once clean.

The maintenance regression suite uses synthetic input and fake provider calls only. New resource-generation/nonces and atomic billing protect lifecycle integrity but do not remove transport or dependency risks.
