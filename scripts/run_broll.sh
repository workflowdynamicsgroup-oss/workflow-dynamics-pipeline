#!/usr/bin/env bash
# Pod wrapper for the B-roll fetch test (CPU pod is enough): watchdog, self-delete check, fetch, summary and R2 upload, hold, self-delete.
# Env: RUN_NAME (required), TERMS (default "laptop typing|city timelapse", separated by |), WATCHDOG (default 600 s), HOLD (default 60 s),
# pod secrets RUN_POD_API_KEY, PIXABAY_API_KEY, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
LOG_DIR="${LOG_DIR:-/workspace-global/logs/$RUN_NAME}"; mkdir -p "$LOG_DIR"; export LOG_DIR
( sleep "${WATCHDOG:-600}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
command -v ffprobe >/dev/null || { echo "MISSING ffprobe"; bash scripts/self_delete.sh terminate; exit 1; }
t0=$(date +%s)
IFS='|' read -r -a TERMS_ARR <<< "${TERMS:-laptop typing|city timelapse}"
OUT=/root/broll_out
python3 broll/fetch_broll.py "$OUT" "${TERMS_ARR[@]}" 2>&1 | tee -a "$LOG_DIR/run.log"
RC=${PIPESTATUS[0]}
echo "STAGE broll rc=$RC seconds=$(( $(date +%s) - t0 ))" | tee -a "$LOG_DIR/run.log"
python3 scripts/finish.py "$RUN_NAME" "$RC" "$OUT"/*.mp4 "$OUT"/broll_manifest.json
sleep "${HOLD:-60}"
bash scripts/self_delete.sh terminate
