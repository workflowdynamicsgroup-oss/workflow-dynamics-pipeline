#!/usr/bin/env bash
# Pod wrapper for FLUX.1-schnell stills (A40 or RTX 4090): checks first, then setup, model copy, generation, summary, R2 upload, hold, self-delete.
# Env: RUN_NAME (required), PROMPTS (default flux/prompts_test.txt, one prompt per line), WATCHDOG (default 1500 s), HOLD (default 120 s),
# pod secrets RUN_POD_API_KEY, HF_TOKEN, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT.
# Checks before any install or copy: self-delete works, secrets non-empty, Hugging Face answers 200 for the gated repo with the token,
# usable RAM at least 45 GB (smaller of cgroup limit and MemAvailable), weights file size on the volume, free local disk.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
LOG_DIR="${LOG_DIR:-/workspace-global/logs/$RUN_NAME}"; mkdir -p "$LOG_DIR"; export LOG_DIR
LOG="$LOG_DIR/run.log"
log() { echo "$(date -u +%T) $*" | tee -a "$LOG"; }
( sleep "${WATCHDOG:-1500}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
git config --global --add safe.directory "*" 2>/dev/null || true
log "BOOT run=$RUN_NAME pipeline_commit=$(git rev-parse --short HEAD 2>/dev/null || echo no-git)"
OUT=/root/flux_out; mkdir -p "$OUT"
finish() {  # $1 = exit code of the job
  FIN=$(python3 scripts/finish.py "$RUN_NAME" "$1" "$OUT"/*.png 2>&1); echo "$FIN"
  if ! echo "$FIN" | grep -q '^UPLOAD_OK'; then
    mkdir -p "/workspace-global/outputs/$RUN_NAME" && cp "$OUT"/*.png "/workspace-global/outputs/$RUN_NAME/" 2>/dev/null
    echo "UPLOAD_FALLBACK images kept in /workspace-global/outputs/$RUN_NAME"
  fi
  sleep "${HOLD:-120}"; bash scripts/self_delete.sh terminate; exit "$1"
}
die() { log "FAIL $*"; echo "STAGE flux rc=1 seconds=0" | tee -a "$LOG"; finish 1; }
for v in HF_TOKEN R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT; do [ -n "${!v:-}" ] || die "secret $v is empty"; done
python3 -c "import boto3" 2>/dev/null || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
python3 -c "import boto3; print('BOTO3_OK', boto3.__version__)" 2>&1 | tee -a "$LOG" | grep -q BOTO3_OK || die "boto3 not importable"
# --- preflight (seconds, before any install or copy)
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 -H "Authorization: Bearer $HF_TOKEN" https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/transformer/config.json)
log "HF_PREFLIGHT http=$code"; [ "$code" = "200" ] || die "Hugging Face gated repo answered $code (need 200: token or licence)"
cg=$(cat /sys/fs/cgroup/memory.max 2>/dev/null || echo max); ma=$(awk '/MemAvailable/{print $2*1024}' /proc/meminfo)
ram=$(python3 -c "import sys; v=[int(x) for x in sys.argv[1:] if x.isdigit()]; print(min(v)//2**30)" "$cg" "$ma")
log "RAM_USABLE_GB=$ram"; [ "$ram" -ge 45 ] || die "usable RAM $ram GB is below 45 GB"
SRC=/workspace-global/models/flux1-schnell/flux1-schnell.safetensors; WANT=23782506688
have=$(stat -c %s "$SRC" 2>/dev/null || echo 0); log "WEIGHTS_SIZE have=$have want=$WANT"; [ "$have" = "$WANT" ] || die "weights file on the volume is $have bytes, want $WANT"
free=$(df --output=avail -B1G /root | tail -n1 | tr -d ' '); log "DISK_FREE_GB=$free"; [ "$free" -ge 45 ] || die "local disk free $free GB is below 45 GB"
PROMPTS="${PROMPTS:-flux/prompts_test.txt}"; [ -s "$PROMPTS" ] || die "prompts file $PROMPTS missing or empty"
log "PREFLIGHT_OK prompts=$(grep -c . "$PROMPTS")"
# --- setup: venv on local disk, torch pinned by the constraints file
t0=$(date +%s)
pip freeze 2>/dev/null | grep -E "^(torch|torchaudio|torchvision)==" > /root/constraints.txt
python3 -m venv --system-site-packages /root/venv_fx || die "venv failed"
timeout 900 /root/venv_fx/bin/pip install --timeout 60 --retries 5 -c /root/constraints.txt "diffusers==0.35.2" "transformers==4.57.1" accelerate sentencepiece protobuf "safetensors>=0.5" 2>&1 | tail -n 3 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" = "0" ] || die "pip install failed"
/root/venv_fx/bin/python -c "import torch, diffusers, transformers, sentencepiece; from diffusers import FluxPipeline; print('FLUX_IMPORT_OK torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'diffusers', diffusers.__version__, 'transformers', transformers.__version__)" 2>&1 | tee -a "$LOG" | grep -q FLUX_IMPORT_OK || die "import check failed"
grep -q 'cuda True' "$LOG" || die "CUDA not available"
log "SETUP_DONE seconds=$(( $(date +%s) - t0 ))"
# --- copy weights to local disk: parallel chunked dd (16 streams of 256 MiB pieces)
t1=$(date +%s); mkdir -p /root/models/flux; DST=/root/models/flux/flux1-schnell.safetensors
bash scripts/chunk_copy.sh "$SRC" "$DST" "$WANT" 16 2>>"$LOG" || die "chunk copy failed"
got=$(stat -c %s "$DST"); log "COPY_DONE bytes=$got seconds=$(( $(date +%s) - t1 ))"; [ "$got" = "$WANT" ] || die "copied size $got != $WANT"
# --- generate
t2=$(date +%s)
export FLUX_WEIGHTS="$DST" HF_HOME=/root/hf HF_TOKEN
/root/venv_fx/bin/python flux/run_flux.py "$PROMPTS" "$OUT" 2>&1 | grep -v -i "it/s\]\|s/it\]" | tee -a "$LOG"
RC=${PIPESTATUS[0]}
n=$(ls "$OUT"/*.png 2>/dev/null | wc -l); want=$(grep -c . "$PROMPTS")
[ "$RC" = "0" ] && [ "$n" = "$want" ] || { log "FAIL images=$n want=$want rc=$RC"; RC=1; }
echo "STAGE flux rc=$RC seconds=$(( $(date +%s) - t2 ))" | tee -a "$LOG"
finish "$RC"
