#!/usr/bin/env bash
# Pod-local setup. Code comes from GitHub at pinned commits; big model files stay on the global volume.
# Venvs and cloned code are built on the pod's local disk (the global volume drops symlinks and exec bits).
set -euo pipefail
source "$(dirname "$0")/common.sh"
header
# Ditto code at the pinned commit; checkpoints linked from the volume
if [ ! -d /root/ditto/.git ]; then git clone -q https://github.com/antgroup/ditto-talkinghead /root/ditto; fi
git -C /root/ditto fetch -q --depth 1 origin c3e47eee2e626500017a0556b470d6d4182f85e8 && git -C /root/ditto checkout -q c3e47eee2e626500017a0556b470d6d4182f85e8
log "DITTO_COMMIT $(git -C /root/ditto rev-parse HEAD)"
ln -sfn /workspace-global/ditto/checkpoints /root/ditto/checkpoints
# Wan code at the pinned commit
if [ ! -d /root/wan-code/.git ]; then git clone -q https://github.com/Wan-Video/Wan2.2 /root/wan-code; fi
git -C /root/wan-code fetch -q --depth 1 origin 1ea34ff48f87168174e12956e200b1d908b1c5ff && git -C /root/wan-code checkout -q 1ea34ff48f87168174e12956e200b1d908b1c5ff
log "WAN_COMMIT $(git -C /root/wan-code rev-parse HEAD)"
# Chatterbox venv on local disk, verified recipe 2026-11-16
if [ ! -x /root/venv_cb/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_cb
  /root/venv_cb/bin/pip install -q --no-deps chatterbox-tts==0.1.7
  /root/venv_cb/bin/pip install -q "numpy<2"
fi
/root/venv_cb/bin/python -c "import chatterbox.tts; print('CB_IMPORT_OK')" 2>&1 | tee -a "$LOG"
log SETUP_DONE
