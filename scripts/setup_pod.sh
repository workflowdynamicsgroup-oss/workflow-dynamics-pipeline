#!/usr/bin/env bash
# Pod-local setup. Code and checkpoints are read from the global volume; only the venv is built on the pod.
set -euo pipefail
source "$(dirname "$0")/common.sh"
header
DITTO_DIR=/workspace-global/code/ditto-talkinghead@c3e47ee
WAN_DIR=/workspace-global/code/wan2.2@1ea34ff
for d in "$DITTO_DIR" "$WAN_DIR"; do
  [ -d "$d/.git" ] || { log "MISSING_CODE $d (run scripts/publish_code_to_volume.sh first)"; exit 1; }
  log "CODE_OK $d $(git -C "$d" rev-parse HEAD)"
done
# Chatterbox venv on pod disk, installed from wheels on the volume
if [ ! -x /root/venv_cb/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_cb
  /root/venv_cb/bin/pip install -q --no-index --find-links /workspace-global/wheels --no-deps chatterbox-tts==0.1.7 || \
    /root/venv_cb/bin/pip install -q --no-deps chatterbox-tts==0.1.7
  /root/venv_cb/bin/pip install -q "numpy<2"
fi
/root/venv_cb/bin/python -c "import chatterbox.tts; print('CB_IMPORT_OK')" 2>&1 | tee -a "$LOG"
log SETUP_DONE
