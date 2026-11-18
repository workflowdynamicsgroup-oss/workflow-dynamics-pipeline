#!/usr/bin/env bash
# Ditto avatar, PyTorch path (TensorRT paths are Ditto's default and are not used).
# Code: /workspace-global/code/ditto-talkinghead@c3e47ee (pinned commit c3e47eee2e626500017a0556b470d6d4182f85e8)
# Usage: RUN_NAME=... AUDIO=... PHOTO=... OUT=... bash ditto/run_ditto.sh
REPO="$(cd "$(dirname "$0")/.." && pwd)"
source "$REPO/scripts/common.sh"
header
DITTO_DIR=/workspace-global/code/ditto-talkinghead@c3e47ee
cd "$DITTO_DIR"
PINNED=c3e47eee2e626500017a0556b470d6d4182f85e8
[ "$(git rev-parse HEAD)" = "$PINNED" ] || { log "DITTO_COMMIT_MISMATCH $(git rev-parse HEAD)"; exit 1; }
log "DITTO_COMMIT $PINNED"
mkdir -p "$(dirname "$OUT")"
DATA_ROOT=/workspace-global/ditto/checkpoints/ditto_pytorch
CFG=/workspace-global/ditto/checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl
python3 "$REPO/preflight/check_ditto_files.py" "$DATA_ROOT" "$CFG" "$AUDIO" "$PHOTO" 2>&1 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" = 0 ] || { log DITTO_FILES_FAIL; exit 1; }
/root/venv_ditto/bin/python "$REPO/preflight/check_ditto_models.py" "$DATA_ROOT" 2>&1 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" = 0 ] || { log DITTO_MODELS_FAIL; exit 1; }
export PYTHONFAULTHANDLER=1
set +e
timeout "${DITTO_TIMEOUT:-900}" /root/venv_ditto/bin/python -u inference.py \
  --data_root "/workspace-global/ditto/checkpoints/ditto_pytorch" \
  --cfg_pkl "/workspace-global/ditto/checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl" \
  --audio_path "$AUDIO" \
  --source_path "$PHOTO" \
  --output_path "$OUT" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
set -e
[ "$RC" = 124 ] && { log "DITTO_TIMEOUT after ${DITTO_TIMEOUT:-900}s (possible writer deadlock)"; exit 1; }
[ "$RC" = 0 ] || { log "DITTO_FAIL exit=$RC"; exit 1; }
test -s "$OUT" && log "DITTO_DONE $OUT"
