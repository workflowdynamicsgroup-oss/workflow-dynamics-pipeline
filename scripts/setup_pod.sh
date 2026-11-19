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
  timeout 900 /root/venv_cap/bin/pip install $PIP_NET "faster-whisper==1.2.1" "av==16.1.0" 2>&1 | tail -n 3 | tee -a "$LOG"  # av 19 breaks faster-whisper 1.2.1 (metadata_errors)
  log CAP_PIP_OK
fi
step CAP_WHISPER_LOAD
timeout 600 /root/venv_cap/bin/python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8', download_root='/workspace-global/models/whisper'); print('FW_WHISPER_OK')" 2>&1 | tee -a "$LOG" || { log WHISPER_FAIL_OR_TIMEOUT; exit 1; }
# System libraries MediaPipe loads at import (libEGL.so.1 is an apt package, not a pip one) and ffmpeg for Ditto.
# Preferred: offline .deb set on the global volume (no Ubuntu mirror involved). Fallback: apt, fully logged.
DEBS=/workspace-global/debs
apt_ok() { ldconfig -p | grep -q 'libEGL.so.1' && ldconfig -p | grep -q 'libGLESv2.so.2' && command -v ffmpeg >/dev/null 2>&1; }
step APT_OFFLINE
if ls "$DEBS"/*.deb >/dev/null 2>&1; then
  timeout 300 dpkg -i "$DEBS"/*.deb 2>&1 | tail -n 5 | tee -a "$LOG" || true
  ldconfig
fi
if apt_ok; then
  log APT_OFFLINE_OK
else
  log "APT_OFFLINE_MISSING falling back to apt (output timestamped below, connections sampled every 30 s)"
  step APT
  ( while sleep 30; do
      echo "$(date +%T) APT_NET conns=$(ss -tn state established 2>/dev/null | tail -n +2 | awk '{print $4"->"$5}' | tr '\n' ' ') procs=$(ps -eo etime,args | grep -E '[a]pt-get|[/]http' | awk '{print $1,$2,$3}' | tr '\n' ';')" | tee -a "$LOG"
    done ) &
  SAMPLER=$!
  set +e
  timeout 900 bash -c 'APT_NET="-o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 -o Acquire::Retries=3"; apt-get $APT_NET update && apt-get $APT_NET install -y libegl1 libgl1 libgles2 ffmpeg' 2>&1 | while IFS= read -r l; do echo "$(date +%T) APT $l" | tee -a "$LOG"; done
  APT_RC=${PIPESTATUS[0]}
  set -e
  kill "$SAMPLER" 2>/dev/null || true
  [ "$APT_RC" -eq 0 ] || { log "APT_FAIL_OR_TIMEOUT rc=$APT_RC"; exit 1; }
  log APT_OK
fi
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
