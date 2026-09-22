# VoxPilot — Architecture

## Overview

```text
Telegram
   |
   v
VoxPilot Controller
   |-- owner-only Telegram UI
   |-- local voice reference store
   |-- SQLite lifecycle/settings/billing metadata
   |-- Vast.ai SDK
   |-- Fish API client
   |
   |  rent / start / stop / destroy
   v
Temporary Vast GPU
   |
   |-- pinned fish-speech source
   |-- Fish Audio S2 Pro weights
   |-- official Fish API server :8080
   |-- bearer authentication
   |
   +-- GET  /v1/health
   +-- POST /v1/tts
```

## Controller responsibilities

The controller is the durable part of VoxPilot. It runs independently of the rented GPU and owns:

- Telegram polling and owner-only authorization.
- Rich Message / styled-button UI with classic fallback.
- saved voice reference files and metadata.
- active voice selection.
- TTS sampling/output settings.
- emotion/performance selection.
- Vast marketplace search and offer cache.
- instance lifecycle and recovery.
- per-second active rental meter.
- Cost Guard.
- operational events and state in SQLite.
- authenticated requests to the Fish API.

The controller does not host a language model and does not rewrite user text.

## Temporary Vast instance

The rented machine is disposable.

Provisioning flow:

1. Controller creates a random Fish API bearer token.
2. Controller rents the selected Vast offer.
3. Vast starts the configured CUDA/PyTorch image.
4. The on-start command checks out VoxPilot.
5. `scripts/bootstrap_vast.sh` checks out the pinned Fish Speech source.
6. Bootstrap prepares the Fish environment, selects the mounted host `libcuda` when present, verifies a GPU allocation, and downloads `fishaudio/s2-pro` weights into `/workspace`.
7. Bootstrap launches the official Fish API server on `0.0.0.0:8080` with `--api-key`.
8. Controller discovers the public mapped port and polls `/v1/health` using the generated bearer token.
9. When health succeeds, the lifecycle becomes READY.

Stopping the instance pauses the local active GPU meter after Vast confirms the stopped state. Starting it resumes the meter and waits for Fish health again. Destroying it finalizes the local billing snapshot and clears the temporary runtime state only after two Vast inventory checks confirm deletion. Stopped instances can continue incurring storage charges.

## Voice cloning path

```text
Owner uploads reference audio
        |
        +--> controller stores audio + matching transcript
        |
Owner sends target text
        |
        +--> load active reference
        +--> prepend selected Fish performance tag, if any
        +--> encode official ServeTTSRequest as MessagePack
        +--> POST /v1/tts with Bearer token
        |
Temporary Fish S2 Pro
        |
        +--> generated audio bytes
        |
Telegram <--- controller sends audio
```

Reference audio is not copied permanently to the Vast instance. It travels with the request.

## Emotion / prosody controls

The bot exposes curated native S2 tags for convenient global selection. This does not prevent manual inline tags inside the user's text.

Example:

```text
[excited] النص المطلوب...
```

Do not add an LLM to infer emotions or rewrite text.

## Vast marketplace behavior

Every refresh performs a new Vast API request. VoxPilot asks Vast for a wider pool than the number displayed, normalizes results, then sorts deterministically.

The selected offer is checked again against the configured maximum hourly price immediately before rental.

A unique instance label is used for recovery if Vast's create response does not return a usable instance ID.

## Persistence

SQLite stores metadata only:
- current instance ID/phase/offer
- Fish endpoint/token for the current rental
- cached offer snapshot and refresh metadata
- billing timestamps and accumulated active seconds
- active voice ID
- TTS settings
- Cost Guard metadata
- operational events

Voice audio and its transcript live in the controller voice data directory, not SQLite.

Generated speech is transient and should not be retained after Telegram delivery unless a future explicit feature requires it.

## Security boundary

Controller-only secrets:
- Telegram bot token
- Vast API key

Temporary-instance secret:
- one randomly generated Fish API bearer token for the current rental

The Fish API must never be exposed without authentication.
