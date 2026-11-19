#!/usr/bin/env bash
# Pod wrapper for the B-roll fetch test (CPU pod is enough): checks first, then fetch, summary and R2 upload, hold, self-delete.
# Env: RUN_NAME (required), TERMS (default "laptop typing|city timelapse", separated by |), WATCHDOG (default 600 s), HOLD (default 60 s),
# pod secrets RUN_POD_API_KEY, PIXABAY_API_KEY, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT.
# Checks before any download: self-delete works, ffprobe present, boto3 importable (installed here: only run_dryrun.sh installs it
# otherwise), every secret non-empty, Pixabay answers (preflight in fetch_broll.py). If the R2 upload fails the clips are kept on the volume.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
LOG_DIR="${LOG_DIR:-/workspace-global/logs/$RUN_NAME}"; mkdir -p "$LOG_DIR"; export LOG_DIR
LOG="$LOG_DIR/run.log"
( sleep "${WATCHDOG:-600}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
die() { echo "$(date +%T) $*" | tee -a "$LOG"; echo "STAGE broll rc=1 seconds=0" | tee -a "$LOG"; python3 scripts/finish.py "$RUN_NAME" 1 2>&1 | tail -n 60; sleep "${HOLD:-60}"; bash scripts/self_delete.sh terminate; exit 1; }
for v in PIXABAY_API_KEY R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT; do [ -n "${!v:-}" ] || die "FAIL secret $v is empty"; done
command -v ffprobe >/dev/null || die "MISSING ffprobe"
python3 -c "import boto3" 2>/dev/null || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1 || pip install -q boto3 >/dev/null 2>&1
python3 -c "import boto3; print('BOTO3_OK', boto3.__version__)" 2>&1 | tee -a "$LOG" | grep -q BOTO3_OK || die "FAIL boto3 not importable"
t0=$(date +%s)
IFS='|' read -r -a TERMS_ARR <<< "${TERMS:-laptop typing|city timelapse}"
OUT=/root/broll_out
python3 broll/fetch_broll.py "$OUT" "${TERMS_ARR[@]}" 2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
echo "STAGE broll rc=$RC seconds=$(( $(date +%s) - t0 ))" | tee -a "$LOG"
FIN=$(python3 scripts/finish.py "$RUN_NAME" "$RC" "$OUT"/*.mp4 "$OUT"/broll_manifest.json 2>&1)
echo "$FIN"
if ! echo "$FIN" | grep -q '^UPLOAD_OK'; then
  mkdir -p "/workspace-global/outputs/$RUN_NAME" && cp "$OUT"/* "/workspace-global/outputs/$RUN_NAME/" 2>/dev/null
  echo "UPLOAD_FALLBACK clips kept in /workspace-global/outputs/$RUN_NAME"
fi
sleep "${HOLD:-60}"
bash scripts/self_delete.sh terminate
