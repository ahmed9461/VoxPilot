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
