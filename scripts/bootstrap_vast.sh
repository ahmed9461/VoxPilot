#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE="${WORKSPACE:-/workspace}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
FISH_ROOT="${FISH_ROOT:-$WORKSPACE/fish-speech}"
FISH_VENV="${FISH_VENV:-$WORKSPACE/fish-venv}"
HF_HOME="${HF_HOME:-$WORKSPACE/hf-cache}"
LOG_FILE="${LOG_FILE:-$WORKSPACE/voxpilot-fish.log}"

FISH_SPEECH_REPO_URL="${FISH_SPEECH_REPO_URL:-https://github.com/fishaudio/fish-speech.git}"
FISH_SPEECH_REF="${FISH_SPEECH_REF:-214da3cd841bda85da2496b96cd3c4d7edb1337e}"
FISH_MODEL_REPO="${FISH_MODEL_REPO:-fishaudio/s2-pro}"
FISH_UV_EXTRA="${FISH_UV_EXTRA:-cu126}"
FISH_API_PORT="${FISH_API_PORT:-8080}"
FISH_COMPILE="${FISH_COMPILE:-0}"
FISH_HALF="${FISH_HALF:-0}"

mkdir -p "$WORKSPACE" "$HF_HOME"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[VoxPilot] bootstrap started: $(date -Is)"
echo "[VoxPilot] Fish ref=$FISH_SPEECH_REF model=$FISH_MODEL_REPO port=$FISH_API_PORT"

# Vast injects env vars into PID 1. Recover them when onstart runs in a child shell.
if [[ -r /proc/1/environ ]]; then
  while IFS= read -r -d '' entry; do
    key="${entry%%=*}"
    case "$key" in
      VOXPILOT_FISH_TOKEN|FISH_API_PORT|FISH_SPEECH_REPO_URL|FISH_SPEECH_REF|FISH_MODEL_REPO|FISH_UV_EXTRA|FISH_COMPILE|FISH_HALF|HF_HOME|HF_TOKEN)
        if [[ -z "${!key:-}" ]]; then export "$entry"; fi
        ;;
    esac
  done < /proc/1/environ
fi

if [[ -z "${VOXPILOT_FISH_TOKEN:-}" ]]; then
  echo "[VoxPilot] ERROR: VOXPILOT_FISH_TOKEN is missing" >&2
  exit 20
fi

if command -v apt-get >/dev/null 2>&1; then
  echo "[VoxPilot] installing system audio dependencies..."
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq     git curl ca-certificates ffmpeg portaudio19-dev libsox-dev build-essential cmake
fi

PYTHON_BIN=""
for candidate in /venv/main/bin/python /opt/conda/bin/python python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "[VoxPilot] ERROR: Python is unavailable" >&2
  exit 21
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "[VoxPilot] installing uv..."
  "$PYTHON_BIN" -m pip install -q --upgrade pip uv
fi

if [[ ! -d "$FISH_ROOT/.git" ]]; then
  git clone "$FISH_SPEECH_REPO_URL" "$FISH_ROOT"
fi
git -C "$FISH_ROOT" fetch --depth 1 origin "$FISH_SPEECH_REF"
git -C "$FISH_ROOT" reset --hard FETCH_HEAD
# The pinned Fish revision prints the full reference and target text via
# Conversation.visualize even when Loguru INFO is disabled.
git -C "$FISH_ROOT" apply "$SCRIPT_DIR/fish_prompt_privacy.patch"

cd "$FISH_ROOT"

echo "[VoxPilot] syncing Fish environment ($FISH_UV_EXTRA)..."
uv sync --python 3.12 --extra "$FISH_UV_EXTRA" --frozen

FISH_PY="$FISH_ROOT/.venv/bin/python"
if [[ ! -x "$FISH_PY" ]]; then
  echo "[VoxPilot] ERROR: Fish virtualenv was not created" >&2
  exit 22
fi

uv pip install --python "$FISH_PY" "huggingface_hub>=0.30,<2"

# Vast's CUDA image can put a forward-compatibility libcuda ahead of the host
# driver. That library fails with error 804 on a GeForce GPU even when the host
# driver can run this CUDA minor version. Use the mounted host driver directly.
HOST_LIBCUDA=/usr/lib/x86_64-linux-gnu/libcuda.so.1
if [[ -r "$HOST_LIBCUDA" ]]; then
  export LD_PRELOAD="$HOST_LIBCUDA${LD_PRELOAD:+:$LD_PRELOAD}"
fi

echo "[VoxPilot] checking CUDA before model download..."
"$FISH_PY" - <<'PY'
import torch

if not torch.cuda.is_available():
    raise RuntimeError("CUDA GPU is unavailable")
torch.ones(1, device="cuda").sum().item()
PY

CHECKPOINT_DIR="$FISH_ROOT/checkpoints/s2-pro"
mkdir -p "$CHECKPOINT_DIR"

echo "[VoxPilot] downloading/verifying S2 Pro weights..."
export FISH_MODEL_REPO HF_HOME
"$FISH_PY" - <<'PY'
import os
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id=os.environ.get("FISH_MODEL_REPO", "fishaudio/s2-pro"),
    local_dir="checkpoints/s2-pro",
    token=os.environ.get("HF_TOKEN") or None,
)
PY

ARGS=(
  tools/api_server.py
  --listen "0.0.0.0:$FISH_API_PORT"
  --llama-checkpoint-path "checkpoints/s2-pro"
  --decoder-checkpoint-path "checkpoints/s2-pro/codec.pth"
  --api-key "$VOXPILOT_FISH_TOKEN"
)

if [[ "$FISH_COMPILE" == "1" || "$FISH_COMPILE" == "true" ]]; then
  ARGS+=(--compile)
fi
if [[ "$FISH_HALF" == "1" || "$FISH_HALF" == "true" ]]; then
  ARGS+=(--half)
fi

FISH_PROCESS_PATTERN="tools/api_server.py.*$FISH_API_PORT"
pkill -TERM -f "$FISH_PROCESS_PATTERN" 2>/dev/null || true
for _ in 1 2 3 4 5; do
  if ! pgrep -f "$FISH_PROCESS_PATTERN" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
# A worker stuck during model initialization may ignore SIGTERM. Do not leave
# it beside a replacement server consuming RAM or holding the API port.
pkill -KILL -f "$FISH_PROCESS_PATTERN" 2>/dev/null || true

echo "[VoxPilot] launching official Fish API..."
# Fish logs prompt structure (including the owner's text) at INFO. Keep error
# output while avoiding routine speech content in the instance log.
export LOGURU_LEVEL="${LOGURU_LEVEL:-WARNING}"
exec "$FISH_PY" "${ARGS[@]}"
