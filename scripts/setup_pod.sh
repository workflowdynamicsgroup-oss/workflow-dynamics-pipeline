#!/usr/bin/env bash
# Pod-local setup. Code and checkpoints come from the global volume at pinned commits.
# Venvs are built on pod disk, installed from wheels on the volume where possible.
set -euo pipefail
source "$(dirname "$0")/common.sh"
header
DITTO_DIR=/workspace-global/code/ditto-talkinghead@c3e47ee
WAN_DIR=/workspace-global/code/wan2.2@1ea34ff
cd "$(dirname "$0")/.."
for d in "$DITTO_DIR" "$WAN_DIR"; do
  [ -d "$d/.git" ] || { log "MISSING_CODE $d (run scripts/publish_code_to_volume.sh first)"; exit 1; }
  log "CODE_OK $d $(git -C "$d" rev-parse HEAD)"
done
WHL=/workspace-global/wheels
pipi() { pip install -q --find-links "$WHL" "$@" || pip install -q "$@"; }
# Chatterbox venv (verified recipe 2026-11-16)
# Keep the system torch and numpy exactly as they are
python3 -c "import torch, numpy; print(torch.__version__, numpy.__version__)" | tee -a "$LOG"
pip freeze 2>/dev/null | grep -E "^(torch|torchaudio|torchvision)==" > /root/constraints.txt || true  # torch only; numpy is set per venv
if [ ! -x /root/venv_cb/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_cb
  /root/venv_cb/bin/pip install -q -c /root/constraints.txt --no-deps chatterbox-tts==0.1.7
  /root/venv_cb/bin/pip install -q -c /root/constraints.txt conformer==0.3.2 diffusers==0.29.0 librosa==0.11.0 omegaconf pykakasi==2.3.0 pyloudnorm resemble-perth s3tokenizer safetensors==0.5.3 spacy-pkuseg "transformers==5.2.0" "numpy<2"
fi
# faster-whisper for captions, on pod disk (pinned model: base). av pinned to 16.1.0:
# av 19 removed the metadata_errors argument that faster-whisper 1.2.1 passes to av.open.
if [ ! -x /root/venv_cap/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_cap
  /root/venv_cap/bin/pip install -q "faster-whisper==1.2.1" "av==16.1.0"
fi
/root/venv_cap/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root='/workspace-global/models/whisper'); print('FW_WHISPER_OK')" 2>&1 | tee -a "$LOG"
# System libraries MediaPipe loads at import (libEGL.so.1 is an apt package, not a pip one)
apt-get update -qq && apt-get install -y -qq libegl1 libgl1 libgles2 ffmpeg > /tmp/apt.log 2>&1 || { log APT_FAIL; tail -n 5 /tmp/apt.log | tee -a "$LOG"; exit 1; }
log APT_OK
# Ditto venv: packages from the 2026-11-16 install list, pinned where the notes pin them
if [ ! -x /root/venv_ditto/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_ditto
  /root/venv_ditto/bin/pip install -q -c /root/constraints.txt "numpy==2.0.1" "onnxruntime-gpu==1.20.2" tqdm librosa soundfile filetype cuda-python cython scikit-image colored tifffile einops imageio imageio-ffmpeg mediapipe
fi
# Wan venv: requirements without flash_attn, plus the three packages the README omits
# Pod-local copy of the pinned Wan code, patched for TI2V-5B without flash-attn (the volume copy stays unpatched)
rm -rf /root/wan2.2 && cp -r "$WAN_DIR" /root/wan2.2
python3 wan/patch_wan.py /root/wan2.2 | tee -a "$LOG" || { log WAN_PATCH_FAIL; exit 1; }
grep -v -i '^flash_attn' /root/wan2.2/requirements.txt > /root/wan_req.txt
if [ ! -x /root/venv_wan/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_wan
  /root/venv_wan/bin/pip install -q -c /root/constraints.txt -r /root/wan_req.txt einops regex scipy
fi
/root/venv_cb/bin/python -c "import chatterbox.tts; print('CB_IMPORT_OK')" 2>&1 | tee -a "$LOG"
/root/venv_ditto/bin/python -c "import imageio_ffmpeg, onnxruntime; print('DITTO_IMPORT_OK')" 2>&1 | tee -a "$LOG"
log SETUP_DONE
