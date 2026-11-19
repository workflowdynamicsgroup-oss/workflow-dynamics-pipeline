#!/usr/bin/env bash
# One-off, run on a pod: download the .deb files setup_pod.sh needs to the global volume,
# so later pods install them with dpkg and never touch the Ubuntu mirrors.
set -euo pipefail
source "$(dirname "$0")/common.sh"
header
OUT=/workspace-global/debs
mkdir -p "$OUT"
WORK=/root/debs_work
rm -rf "$WORK"; mkdir -p "$WORK/partial"
. /etc/os-release; log "OS $PRETTY_NAME"
step() { log "STEP_START $1"; }
NET="-o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 -o Acquire::Retries=3"
step APT_UPDATE
timeout 1500 apt-get $NET update 2>&1 | while IFS= read -r l; do echo "$(date +%T) APT $l" | tee -a "$LOG"; done
step APT_DOWNLOAD
timeout 1500 apt-get $NET install -y --download-only -o Dir::Cache::archives="$WORK" libegl1 libgl1 libgles2 ffmpeg 2>&1 | while IFS= read -r l; do echo "$(date +%T) APT $l" | tee -a "$LOG"; done
N=$(ls "$WORK"/*.deb 2>/dev/null | wc -l)
[ "$N" -gt 0 ] || { log "DEBS_NONE (every package already installed on the image?)"; exit 1; }
rm -f "$OUT"/*.deb
cp "$WORK"/*.deb "$OUT"/
echo "$PRETTY_NAME" > "$OUT/OS.txt"
log "DEBS_SAVED count=$N dir=$OUT"
ls -l "$OUT" | tee -a "$LOG"
