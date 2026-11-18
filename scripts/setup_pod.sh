#!/usr/bin/env bash
# Pod-local setup. Code and checkpoints come from the global volume at pinned commits.
# Venvs are built on pod disk, installed from wheels on the volume where possible.
set -euo pipefail
source "$(dirname "$0")/common.sh"
header
DITTO_DIR=/workspace-global/code/ditto-talkinghead@c3e47ee
WAN_DIR=/workspace-global/code/wan2.2@1ea34ff
for d in "$DITTO_DIR" "$WAN_DIR"; do
  [ -d "$d/.git" ] || { log "MISSING_CODE $d (run scripts/publish_code_to_volume.sh first)"; exit 1; }
  log "CODE_OK $d $(git -C "$d" rev-parse HEAD)"
done
WHL=/workspace-global/wheels
pipi() { pip install -q --find-links "$WHL" "$@" || pip install -q "$@"; }
# Chatterbox venv (verified recipe 2026-11-16)
if [ ! -x /root/venv_cb/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_cb
  /root/venv_cb/bin/pip install -q --no-deps chatterbox-tts==0.1.7
  /root/venv_cb/bin/pip install -q "numpy<2"
fi
# Whisper for captions, on pod disk (pinned model: base)
if [ ! -x /root/venv_cap/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_cap
  /root/venv_cap/bin/pip install -q openai-whisper
fi
/root/venv_cap/bin/python -c "import whisper; whisper.load_model('base', download_root='/workspace-global/models/whisper'); print('WHISPER_OK')" 2>&1 | tee -a "$LOG"
# Ditto venv: packages from the 2026-11-16 install list, pinned where the notes pin them
if [ ! -x /root/venv_ditto/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_ditto
  /root/venv_ditto/bin/pip install -q "numpy==2.0.1" "onnxruntime-gpu==1.20.2" tqdm librosa soundfile filetype cuda-python cython scikit-image colored tifffile einops imageio imageio-ffmpeg mediapipe
fi
# Wan venv: requirements plus the three packages the README omits
if [ ! -x /root/venv_wan/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_wan
  /root/venv_wan/bin/pip install -q -r "$WAN_DIR/requirements.txt" einops regex scipy
fi
/root/venv_cb/bin/python -c "import chatterbox.tts; print('CB_IMPORT_OK')" 2>&1 | tee -a "$LOG"
/root/venv_ditto/bin/python -c "import imageio_ffmpeg, onnxruntime; print('DITTO_IMPORT_OK')" 2>&1 | tee -a "$LOG"
log SETUP_DONE
