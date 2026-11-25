#!/usr/bin/env bash
# Pod wrapper: remove the backdrop from a finished Ditto avatar video on the GPU (u2net_human_seg via onnxruntime-gpu).
# Env: RUN_NAME (required), INPUT (a file path), or INPUT_RUN (fetch R2 outputs/<INPUT_RUN>/ditto.mp4; wins over the volume default), else the old test file block135-a10, WATCHDOG (default 900 s), HOLD (default 120 s),
# secrets RUN_POD_API_KEY, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT.
# Outputs (uploaded to R2 outputs/<run>/): alpha.mp4 (gray mask, same frames as the input), cutout.webm (VP9 with alpha, audio kept), preview_charcoal.mp4 (first 12 s over #2A2D34).
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
LOG_DIR="${LOG_DIR:-/workspace-global/logs/$RUN_NAME}"; mkdir -p "$LOG_DIR"; export LOG_DIR
LOG="$LOG_DIR/run.log"
log() { echo "$(date -u +%T) $*" | tee -a "$LOG"; }
( sleep "${WATCHDOG:-900}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
git config --global --add safe.directory "*" 2>/dev/null || true
log "BOOT run=$RUN_NAME pipeline_commit=$(git rev-parse --short HEAD 2>/dev/null || echo no-git)"
OUT=/root/cutout_out; mkdir -p "$OUT"
finish() {
  FIN=$(python3 scripts/finish.py "$RUN_NAME" "$1" "$OUT"/alpha.mp4 "$OUT"/cutout.webm "$OUT"/preview_charcoal.mp4 2>&1); echo "$FIN"
  if ! echo "$FIN" | grep -q '^UPLOAD_OK'; then mkdir -p "/workspace-global/outputs/$RUN_NAME" && cp "$OUT"/* "/workspace-global/outputs/$RUN_NAME/" 2>/dev/null; echo "UPLOAD_FALLBACK kept in /workspace-global/outputs/$RUN_NAME"; fi
  sleep "${HOLD:-120}"; bash scripts/self_delete.sh terminate; exit "$1"
}
die() { log "FAIL $*"; echo "STAGE cutout rc=1 seconds=0" | tee -a "$LOG"; finish 1; }
for v in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT; do [ -n "${!v:-}" ] || die "secret $v is empty"; done
python3 -c "import boto3" 2>/dev/null || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
python3 -c "import boto3; print('BOTO3_OK', boto3.__version__)" 2>&1 | tee -a "$LOG" | grep -q BOTO3_OK || die "boto3 not importable"
# --- preflight, before any install
for t in ffmpeg ffprobe; do command -v $t >/dev/null || die "MISSING $t"; done
ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libvpx-vp9 && log "VP9_ENCODER_OK" || log "VP9_ENCODER_MISSING (cutout.webm will be skipped)"
# INPUT_RUN set (and INPUT not set): always fetch that run from R2, never the volume default (cutout-ghl-a1-block1 and cutout-ghl-a2-block2 cut the old test video by mistake)
if [ -n "${INPUT:-}" ]; then IN="$INPUT"; elif [ -n "${INPUT_RUN:-}" ]; then IN=/root/in.mp4; rm -f "$IN"; else IN=/workspace-global/outputs/block135-a10/ditto.mp4; fi
if [ ! -s "$IN" ]; then
  KEY="outputs/${INPUT_RUN:-block135-a10}/ditto.mp4"; IN=/root/in.mp4; log "INPUT_NOT_ON_VOLUME fetching R2 $KEY"
  python3 - "$KEY" "$IN" <<'PY' 2>&1 | tee -a "$LOG"
import boto3, os, sys
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
s3.download_file("workflowdynamic", sys.argv[1], sys.argv[2]); print("R2_FETCH_OK", os.path.getsize(sys.argv[2]))
PY
  [ -s "$IN" ] || die "input video not found on the volume or in R2"
fi
log "INPUT $IN $(ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,duration -of csv=p=0 "$IN")"
MODEL=/root/.u2net/u2net_human_seg.onnx; mkdir -p /root/.u2net
curl -sL --retry 3 --max-time 180 -o "$MODEL" https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx
msz=$(stat -c %s "$MODEL" 2>/dev/null || echo 0); log "MODEL_SIZE=$msz"; [ "$msz" -gt 150000000 ] || die "model download failed (size $msz)"
log "PREFLIGHT_OK"
# --- setup: venv on local disk, same onnxruntime-gpu pin as the Ditto venv
t0=$(date +%s)
pip freeze 2>/dev/null | grep -E "^(torch|torchaudio|torchvision)==" > /root/constraints.txt
python3 -m venv --system-site-packages /root/venv_cut || die "venv failed"
timeout 900 /root/venv_cut/bin/pip install --timeout 60 --retries 5 -c /root/constraints.txt "numpy==2.0.1" "onnxruntime-gpu==1.20.2" "opencv-python-headless<4.13" 2>&1 | tail -n 3 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" = "0" ] || die "pip install failed"
/root/venv_cut/bin/python -c "import onnxruntime as ort, cv2, numpy; print('CUT_IMPORT_OK ort', ort.__version__, ort.get_available_providers(), 'cv2', cv2.__version__, 'numpy', numpy.__version__)" 2>&1 | tee -a "$LOG" | grep -q CUT_IMPORT_OK || die "import check failed"
log "SETUP_DONE seconds=$(( $(date +%s) - t0 ))"
# --- cutout mask (fails at once if CUDA is not active)
t1=$(date +%s)
REQUIRE_CUDA=1 MODEL="$MODEL" BATCH=16 /root/venv_cut/bin/python cutout/make_cutout.py "$IN" "$OUT" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
echo "STAGE cutout rc=$RC seconds=$(( $(date +%s) - t1 ))" | tee -a "$LOG"
if [ "$RC" = "0" ]; then
  # preview over charcoal (first 12 s, with audio) and the transparent webm; neither is fatal
  t2=$(date +%s)
  ffmpeg -loglevel error -y -t 12 -i "$IN" -t 12 -i "$OUT/alpha.mp4" -f lavfi -i "color=c=0x2A2D34:s=720x540:r=25" -filter_complex "[1:v]format=gray[a];[0:v][a]alphamerge[fg];[2:v][fg]overlay=shortest=1,format=yuv420p[v]" -map "[v]" -map 0:a? -c:v libx264 -crf 20 -preset veryfast -c:a aac -t 12 "$OUT/preview_charcoal.mp4" 2>&1 | tee -a "$LOG"
  log "PREVIEW_DONE seconds=$(( $(date +%s) - t2 ))"
  if ffmpeg -hide_banner -encoders 2>/dev/null | grep -q libvpx-vp9; then
    t3=$(date +%s)
    timeout 600 ffmpeg -loglevel error -y -i "$IN" -i "$OUT/alpha.mp4" -filter_complex "[1:v]format=gray[a];[0:v][a]alphamerge[v]" -map "[v]" -map 0:a? -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 32 -deadline realtime -cpu-used 8 -row-mt 1 -c:a libopus "$OUT/cutout.webm" 2>&1 | tee -a "$LOG"
    log "WEBM_DONE rc=${PIPESTATUS[0]} seconds=$(( $(date +%s) - t3 )) bytes=$(stat -c %s "$OUT/cutout.webm" 2>/dev/null || echo 0)"
  fi
fi
finish "$RC"
