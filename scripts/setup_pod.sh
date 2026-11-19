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
# Every network step is bounded and logged, so a stall shows up as a named step with a timeout code (124)
step() { log "STEP_START $1"; }
PIP_NET="--timeout 60 --retries 5"
# Chatterbox venv (verified recipe 2026-11-16)
# Keep the system torch and numpy exactly as they are
python3 -c "import torch, numpy; print(torch.__version__, numpy.__version__)" | tee -a "$LOG"
pip freeze 2>/dev/null | grep -E "^(torch|torchaudio|torchvision)==" > /root/constraints.txt || true  # torch only; numpy is set per venv
if [ ! -x /root/venv_cb/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_cb
  step CB_PIP_CHATTERBOX
  timeout 900 /root/venv_cb/bin/pip install $PIP_NET -c /root/constraints.txt --no-deps chatterbox-tts==0.1.7 2>&1 | tail -n 3 | tee -a "$LOG"
  step CB_PIP_DEPS
  timeout 900 /root/venv_cb/bin/pip install $PIP_NET -c /root/constraints.txt conformer==0.3.2 diffusers==0.29.0 librosa==0.11.0 omegaconf pykakasi==2.3.0 pyloudnorm resemble-perth s3tokenizer safetensors==0.5.3 spacy-pkuseg "transformers==5.2.0" "numpy<2" 2>&1 | tail -n 3 | tee -a "$LOG"
  log CB_PIP_OK
fi
# Whisper for captions, on pod disk (pinned model: base)
if [ ! -x /root/venv_cap/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_cap
  step CAP_PIP
  timeout 900 /root/venv_cap/bin/pip install $PIP_NET openai-whisper 2>&1 | tail -n 3 | tee -a "$LOG"
  log CAP_PIP_OK
fi
step CAP_WHISPER_LOAD
timeout 600 /root/venv_cap/bin/python -c "import whisper; whisper.load_model('base', download_root='/workspace-global/models/whisper'); print('WHISPER_OK')" 2>&1 | tee -a "$LOG" || { log WHISPER_FAIL_OR_TIMEOUT; exit 1; }
# System libraries MediaPipe loads at import (libEGL.so.1 is an apt package, not a pip one)
step APT
timeout 900 bash -c 'APT_NET="-o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 -o Acquire::Retries=3"; apt-get $APT_NET update -qq && apt-get $APT_NET install -y -qq libegl1 libgl1 libgles2 ffmpeg' > /tmp/apt.log 2>&1 || { log APT_FAIL_OR_TIMEOUT; tail -n 5 /tmp/apt.log | tee -a "$LOG"; exit 1; }
log APT_OK
# Ditto venv: packages from the 2026-11-16 install list, pinned where the notes pin them
if [ ! -x /root/venv_ditto/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_ditto
  step DITTO_PIP
  timeout 1200 /root/venv_ditto/bin/pip install $PIP_NET -c /root/constraints.txt "numpy==2.0.1" "onnxruntime-gpu==1.20.2" tqdm librosa soundfile filetype cuda-python cython scikit-image colored tifffile einops imageio imageio-ffmpeg mediapipe
fi
# Wan venv: requirements without flash_attn, plus the three packages the README omits
# Pod-local copy of the pinned Wan code, patched for TI2V-5B without flash-attn (the volume copy stays unpatched)
rm -rf /root/wan2.2 && cp -r "$WAN_DIR" /root/wan2.2
python3 wan/patch_wan.py /root/wan2.2 | tee -a "$LOG" || { log WAN_PATCH_FAIL; exit 1; }
grep -v -i '^flash_attn' /root/wan2.2/requirements.txt > /root/wan_req.txt
if [ ! -x /root/venv_wan/bin/python ]; then
  python3 -m venv --system-site-packages /root/venv_wan
  step WAN_PIP
  timeout 1200 /root/venv_wan/bin/pip install $PIP_NET -c /root/constraints.txt -r /root/wan_req.txt einops regex scipy
fi
/root/venv_cb/bin/python -c "import chatterbox.tts; print('CB_IMPORT_OK')" 2>&1 | tee -a "$LOG"
/root/venv_ditto/bin/python -c "import imageio_ffmpeg, onnxruntime; print('DITTO_IMPORT_OK')" 2>&1 | tee -a "$LOG"
log SETUP_DONE
