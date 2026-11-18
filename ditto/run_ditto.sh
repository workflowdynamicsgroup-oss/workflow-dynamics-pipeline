#!/usr/bin/env bash
# Ditto avatar, PyTorch path (TensorRT paths are Ditto's default and are not used).
# Code: /workspace-global/code/ditto-talkinghead@ (pinned commit )
# Usage: RUN_NAME=... AUDIO=... PHOTO=... OUT=... bash ditto/run_ditto.sh
source "$(dirname "$0")/../scripts/common.sh"
header
DITTO_DIR=/workspace-global/code/ditto-talkinghead@
cd "$DITTO_DIR"
[ "$(git rev-parse HEAD)" = "" ] || { log "DITTO_COMMIT_MISMATCH"; exit 1; }
log "DITTO_COMMIT "
export PYTHONFAULTHANDLER=1
/root/venv_ditto/bin/python -u inference.py \
  --data_root "/workspace-global/ditto/checkpoints/ditto_pytorch" \
  --cfg_pkl "/workspace-global/ditto/checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl" \
  --audio_path "$AUDIO" \
  --source_path "$PHOTO" \
  --output_path "$OUT" 2>&1 | tee -a "$LOG"
test -s "$OUT" && log "DITTO_DONE $OUT"
