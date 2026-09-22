# VoxPilot

VoxPilot is a personal, owner-only Telegram controller for **Fish Audio S2 Pro** running on temporary **Vast.ai** GPU instances.

The project is intentionally focused: it converts text to speech, clones voices from a reference sample, exposes Fish-native emotion/prosody controls, and manages the GPU rental lifecycle. It is **not** a conversational AI assistant and contains no LLM prompt/persona/chat-history layer.

## What it does

- Save multiple reference voices on the durable controller.
- Select an active voice without re-uploading it after every Vast rental.
- Generate speech from text through Fish S2 Pro.
- Choose model-native performance presets such as excited, sad, angry, whisper, laughing, and singing.
- Adjust real Fish request controls: temperature, top-p, repetition penalty, chunk length, max new tokens, normalization, seed, and output format.
- Search Vast.ai live offers and show suitable 24GB+ GPUs.
- Rent, recover, stop, start, and destroy the current instance.
- Track estimated active rental cost by the second.
- Warn about an idle paid GPU or an actively billed rental that remains unready through Cost Guard.
- Use Telegram Rich Messages/styled buttons where supported with classic fallback.

## Runtime split

**Controller** (cheap permanent server / local machine): Telegram, voice files, SQLite state, Vast credentials, billing metadata, Fish HTTP client.

**Temporary Vast GPU**: pinned Fish Speech source + S2 Pro weights + official authenticated Fish API server.

Saved reference voices live on the controller, not on the temporary GPU.

## Requirements

- Python 3.11+ for the controller.
- Telegram bot token.
- Vast.ai API key.
- A public/reachable copy of this repository for Vast bootstrap, unless a Vast template is configured instead.
- A Vast GPU meeting the configured policy; default minimum is 24 GB VRAM.

Fish's official docs currently recommend at least 24 GB VRAM for S2 inference.

## Controller setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# fill TELEGRAM_BOT_TOKEN, OWNER_TELEGRAM_ID, VAST_API_KEY
voxpilot
```

## First-use flow

1. Start the bot and add a voice reference.
2. Send a 10–30 second voice/audio sample.
3. Send the exact text spoken in that sample.
4. Search Vast offers.
5. Rent and prepare one offer.
6. Choose emotion/settings if desired.
7. Send target text or tap Generate and send text.
8. VoxPilot sends back the synthesized audio.
9. Stop or destroy the GPU when finished.

Only clone voices you are authorized to use.

## Project state

Read these before making changes:

- `AGENTS.md`
- `docs/PROJECT_MEMORY.md`
- `docs/PROJECT_STATUS.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`
- `ROADMAP.md`
- active plan under `plans/`
- `docs/PROGRESS_LOG.md`
