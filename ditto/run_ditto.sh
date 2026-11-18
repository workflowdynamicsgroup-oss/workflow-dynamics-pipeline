#!/usr/bin/env bash
# Ditto avatar, PyTorch path (TensorRT paths are the Ditto default and are not used).
# Upstream: antgroup/ditto-talkinghead @ c3e47eee2e626500017a0556b470d6d4182f85e8
# Usage: RUN_NAME=... AUDIO=... PHOTO=... OUT=... bash ditto/run_ditto.sh
source "$(dirname "$0")/../scripts/common.sh"
header
DITTO_DIR=/workspace-global/ditto/code/ditto-talkinghead
cd "$DITTO_DIR"
log "DITTO_COMMIT_EXPECTED c3e47eee2e626500017a0556b470d6d4182f85e8"
log "DITTO_COMMIT_ACTUAL $(git rev-parse HEAD 2>/dev/null || echo unknown)"
python3 -u inference.py \
  --data_root "./checkpoints/ditto_pytorch" \
  --cfg_pkl "./checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl" \
  --audio_path "$AUDIO" \
  --source_path "$PHOTO" \
  --output_path "$OUT" 2>&1 | tee -a "$LOG"
test -s "$OUT" && log "DITTO_DONE $OUT"
