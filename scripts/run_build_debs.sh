#!/usr/bin/env bash
# Pod wrapper for build_debs.sh: watchdog, self-delete check, build, summary on stdout, hold, self-delete.
# Env: RUN_NAME (required), WATCHDOG (default 900 s), HOLD (default 90 s), pod secret RUN_POD_API_KEY.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
( sleep "${WATCHDOG:-900}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
t0=$(date +%s)
bash scripts/build_debs.sh
RC=$?
echo "BUILD_DEBS rc=$RC seconds=$(( $(date +%s) - t0 ))"
echo "===== SUMMARY run=$RUN_NAME rc=$RC ====="
ls -l /workspace-global/debs 2>&1 | head -n 40
cat /workspace-global/debs/OS.txt 2>/dev/null
echo "===== END SUMMARY run=$RUN_NAME ====="
sleep "${HOLD:-90}"
bash scripts/self_delete.sh terminate
