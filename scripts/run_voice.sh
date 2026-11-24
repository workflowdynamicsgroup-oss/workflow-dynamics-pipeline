#!/usr/bin/env bash
# One-command narration run: fetch the narration from R2 (md5 checked), voice it with Chatterbox, run Whisper captions, upload, self-delete.
# Wraps run_dryrun.sh with SKIP_DITTO=1 and CAPTIONS=1 as defaults. Narration markers [BEAT] are turned into paragraph breaks by fetch_text.py.
# Env: RUN_NAME and NARRATION_KEY (required), NARRATION_MD5 (optional, checked), plus run_dryrun.sh settings (HOLD, WATCHDOG) and the pod secrets.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
: "${NARRATION_KEY:?set NARRATION_KEY, the R2 key of the narration file}"
python3 -c "import boto3" 2>/dev/null || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
if ! python3 scripts/fetch_text.py "$NARRATION_KEY" /root/narr.txt ${NARRATION_MD5:-}; then
  echo "FETCH_TEXT_FAIL: removing pod"; bash scripts/self_delete.sh terminate; exit 1
fi
export TEXT_FILE=/root/narr.txt CAPTIONS="${CAPTIONS:-1}" SKIP_DITTO="${SKIP_DITTO:-1}"
exec bash scripts/run_dryrun.sh
