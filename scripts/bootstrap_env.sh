#!/usr/bin/env bash
# Import only supported settings before defaults. Never print environment values.
voxpilot_load_environment() {
  local source="${1:-/proc/1/environ}" entry key
  [[ -r "$source" ]] || return 0
  while IFS= read -r -d '' entry; do
    key="${entry%%=*}"
    case "$key" in
      VOXPILOT_FISH_TOKEN|FISH_API_PORT|FISH_SPEECH_REPO_URL|FISH_SPEECH_REF|FISH_MODEL_REPO|FISH_MODEL_REVISION|FISH_UV_EXTRA|FISH_COMPILE|FISH_HALF|HF_HOME|HF_TOKEN|WORKSPACE|FISH_ROOT|LOG_FILE)
        # An explicitly inherited value (including empty) wins over PID 1.
        if [[ ! -v "$key" ]]; then export "$entry"; fi
        ;;
    esac
  done < "$source"
}
