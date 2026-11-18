#!/usr/bin/env bash
# Dry run: setup, preflight, 10 s Chatterbox narration, 10 s Ditto render. Stops at the first failure.
# Always: summary + R2 upload, hold HOLD seconds so the live log can be read, then self-delete.
# Env: RUN_NAME (required), HOLD (default 240), plus pod secrets RUN_POD_API_KEY, R2_*.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
OUTDIR=/workspace-global/outputs/$RUN_NAME
OUT=$OUTDIR/ditto.mp4
# Watchdog: whatever hangs, the pod terminates itself after WATCHDOG seconds (default 25 min)
( sleep "${WATCHDOG:-1500}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
mkdir -p "$OUTDIR"
(
  set -e
  bash scripts/setup_pod.sh
  bash preflight/check_imports.sh
  cp "${TEXT_FILE:-test/narration10.txt}" /root/dry.txt
  bash chatterbox/run_chatterbox.sh /root/dry.txt /root/dry.wav /workspace-global/inputs/me.wav
  AUDIO=/root/dry.wav PHOTO=/workspace-global/inputs/IMG_3004.png OUT="$OUT" bash ditto/run_ditto.sh
)
RC=$?
/root/venv_cap/bin/pip install -q boto3 >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
PY=/root/venv_cap/bin/python; [ -x $PY ] || PY=python3
for f in /root/dry.wav "$OUT"; do [ -s "$f" ] && echo "DURATION $f $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null) s"; done
$PY scripts/finish.py "$RUN_NAME" "$RC" "$OUT" /root/dry.wav
sleep "${HOLD:-240}"
bash scripts/self_delete.sh terminate
