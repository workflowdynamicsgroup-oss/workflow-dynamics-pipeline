#!/usr/bin/env bash
# Narration with the cloned voice. Uses the pod's Chatterbox venv.
# Usage: RUN_NAME=... bash chatterbox/run_chatterbox.sh SCRIPT.txt OUT.wav REFERENCE.wav
source "$(dirname "$0")/../scripts/common.sh"
header
/root/venv_cb/bin/python -u "$(dirname "$0")/run_chatterbox.py" "$1" "$2" "$3" 2>&1 | tee -a "$LOG"
test -s "$2" && log "CB_OUT $2"
