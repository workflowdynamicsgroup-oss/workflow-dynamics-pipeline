#!/usr/bin/env bash
# Wan 2.2 TI2V-5B, pinned to Wan-Video/Wan2.2 commit 1ea34ff48f87168174e12956e200b1d908b1c5ff.
# Usage: RUN_NAME=... PROMPT=... FRAMES=121|241 OUT=... bash wan/run_wan.sh
# frame_num must be 4n+1 (121 = 5 s, 241 = 10 s). Steps 50, 1280*704, 24 fps.
source "$(dirname "$0")/../scripts/common.sh"
header
WAN_DIR=/root/wan-code
cd "$WAN_DIR"
log "WAN_COMMIT_ACTUAL $(git rev-parse HEAD)"
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python3 -u generate.py \
  --task ti2v-5B \
  --size 1280*704 \
  --ckpt_dir /workspace-global/models/wan2.2-ti2v-5b \
  --frame_num "$FRAMES" \
  --sample_steps 50 \
  --offload_model True \
  --prompt "$PROMPT" \
  --save_file "$OUT" 2>&1 | tee -a "$LOG"
test -s "$OUT" && log "WAN_DONE $OUT"
