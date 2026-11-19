#!/usr/bin/env bash
# Wan 2.2 TI2V-5B test pod: watchdog, Wan-only setup, preflight, model copy to pod disk,
# one generation, summary and R2 upload, then self-delete. Stops at the first failed stage.
# Env: RUN_NAME (required), PROMPT (default: a short test prompt), FRAMES (121 = 5 s; 241 = 10 s),
#      HOLD (default 240 s), WATCHDOG (default 3600 s), plus pod secrets RUN_POD_API_KEY, R2_*.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
PROMPT=${PROMPT:-"A calm ocean at sunset, gentle waves, warm light on the water."}
FRAMES=${FRAMES:-121}
OUTDIR=/workspace-global/outputs/$RUN_NAME
OUT=$OUTDIR/wan.mp4
# Watchdog: whatever hangs, the pod terminates itself after WATCHDOG seconds
( sleep "${WATCHDOG:-3600}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
mkdir -p "$OUTDIR"
stage() { local n=$1 t0 rc=0; shift; t0=$(date +%s); "$@" || rc=$?; echo "STAGE $n rc=$rc seconds=$(( $(date +%s) - t0 ))"; return $rc; }
copy_model() { # copy the checkpoint to pod disk in parallel; loading straight from the volume stalled before
  local src=/workspace-global/models/wan2.2-ti2v-5b dst=/root/models/wan2.2-ti2v-5b
  mkdir -p "$dst" && cd "$src" && find . -type f -print0 | xargs -0 -P 8 -I{} sh -c 'mkdir -p "$(dirname "$2/$1")" && cp "$1" "$2/$1"' _ {} "$dst"
  local rc=$?; cd - >/dev/null || true
  echo "MODEL_LOCAL $(du -sh "$dst" | cut -f1)"; return $rc
}
(
  set -e
  stage setup bash wan/setup_wan_only.sh
  stage preflight bash wan/preflight_wan.sh
  stage copy_model copy_model
  stage generate env CKPT_DIR=/root/models/wan2.2-ti2v-5b PROMPT="$PROMPT" FRAMES="$FRAMES" OUT="$OUT" bash wan/run_wan.sh
)
RC=$?
/root/venv_cap/bin/pip install -q boto3 >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
PY=/root/venv_cap/bin/python; [ -x $PY ] || PY=python3
[ -s "$OUT" ] && echo "DURATION $OUT $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT" 2>/dev/null) s"
$PY scripts/finish.py "$RUN_NAME" "$RC" "$OUT"
sleep "${HOLD:-240}"
bash scripts/self_delete.sh terminate
