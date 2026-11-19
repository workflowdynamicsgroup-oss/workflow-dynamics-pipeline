#!/usr/bin/env bash
# Pod-local setup for the Wan 2.2 test only: no Chatterbox, Ditto or Whisper venvs.
# Code comes from the pinned volume copy; the pod-local copy is patched (the volume copy stays unpatched).
set -euo pipefail
source "$(dirname "$0")/../scripts/common.sh"
header
WAN_SHA=1ea34ff48f87168174e12956e200b1d908b1c5ff
WAN_DIR=/workspace-global/code/wan2.2@1ea34ff
[ -d "$WAN_DIR/.git" ] || { log "MISSING_CODE $WAN_DIR (run scripts/publish_code_to_volume.sh first)"; exit 1; }
[ "$(git -C "$WAN_DIR" rev-parse HEAD)" = "$WAN_SHA" ] || { log "MISMATCH $WAN_DIR"; exit 1; }
log "CODE_OK $WAN_DIR $WAN_SHA"
cd "$(dirname "$0")/.."
pip freeze 2>/dev/null | grep -E "^(torch|torchaudio|torchvision)==" > /root/constraints.txt || true
rm -rf /root/wan2.2 && cp -r "$WAN_DIR" /root/wan2.2
python3 wan/patch_wan.py /root/wan2.2 | tee -a "$LOG"
grep -v -i '^flash_attn' /root/wan2.2/requirements.txt > /root/wan_req.txt
if [ ! -x /root/venv_wan/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_wan
  /root/venv_wan/bin/pip install -q -c /root/constraints.txt -r /root/wan_req.txt einops regex scipy
fi
log SETUP_DONE
