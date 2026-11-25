#!/usr/bin/env bash
# Pod wrapper: render the long-form video with Remotion on a CPU pod.
# Env: RUN_NAME (required), PKG_PREFIX (R2 folder holding props-16x9.json, narration.wav, avatar/*.webm, manifest.json; required),
#   FRAMES (optional, for example 0-499 for a 20 s test at 25 fps; empty = full video), COMP (default Long16x9),
#   WATCHDOG (default 2400 s), HOLD (default 60 s), secrets RUN_POD_API_KEY, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT.
# Local simulation: SIM_SRC=<dir mirroring R2 keys> SIM=1 skips the self-delete, the boto3 install and the browser download check.
# Output (uploaded to R2 outputs/<run>/): video.mp4.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"; : "${PKG_PREFIX:?set PKG_PREFIX}"
LOG_DIR="${LOG_DIR:-/root/logs/$RUN_NAME}"; mkdir -p "$LOG_DIR"; export LOG_DIR
LOG="$LOG_DIR/run.log"
log() { echo "$(date -u +%T) $*" | tee -a "$LOG"; }
SIM="${SIM:-0}"
if [ "$SIM" != 1 ]; then
  ( sleep "${WATCHDOG:-2400}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
  bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
fi
git config --global --add safe.directory "*" 2>/dev/null || true
log "BOOT run=$RUN_NAME pipeline_commit=$(git rev-parse --short HEAD 2>/dev/null || echo no-git) nproc=$(nproc) mem_gb=$(free -g | awk '/Mem:/{print $2}')"
OUT=/root/render_out; mkdir -p "$OUT"; PKG=/root/pkg; mkdir -p "$PKG"
finish() {
  if [ "$SIM" = 1 ]; then echo "SIM_FINISH rc=$1"; exit "$1"; fi
  FIN=$(python3 scripts/finish.py "$RUN_NAME" "$1" "$OUT"/video.mp4 2>&1); echo "$FIN"
  if ! echo "$FIN" | grep -q '^UPLOAD_OK'; then mkdir -p /root/keep && cp "$OUT"/* /root/keep/ 2>/dev/null; echo "UPLOAD_FALLBACK kept in /root/keep (pod will be deleted after HOLD)"; fi
  sleep "${HOLD:-60}"; bash scripts/self_delete.sh terminate; exit "$1"
}
die() { log "FAIL $*"; echo "STAGE render rc=1 seconds=0" | tee -a "$LOG"; finish 1; }
if [ "$SIM" != 1 ]; then
  for v in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY R2_ENDPOINT; do [ -n "${!v:-}" ] || die "secret $v is empty"; done
  python3 -c "import boto3" 2>/dev/null || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
  python3 -c "import boto3; print('BOTO3_OK', boto3.__version__)" 2>&1 | tee -a "$LOG" | grep -q BOTO3_OK || die "boto3 not importable"
fi
# --- preflight: node, ffmpeg, git, then the browser libraries (a missing one is installed, with a timeout)
t0=$(date +%s)
command -v ffmpeg >/dev/null || die "MISSING ffmpeg"
if ! command -v node >/dev/null; then
  python3 -m pip install -q --break-system-packages nodejs-wheel-binaries >/dev/null 2>&1
  export PATH="$(python3 -c 'import nodejs_wheel,os;print(os.path.join(os.path.dirname(nodejs_wheel.__file__),"bin"))' 2>/dev/null):$PATH"
fi
command -v node >/dev/null && command -v npm >/dev/null || die "MISSING node/npm"
log "NODE_OK $(node -v) npm $(npm -v)"
# --- fetch the package (props, narration, avatars, manifest and every clip) from R2
if [ "$SIM" = 1 ]; then
  SIM_SRC="${SIM_SRC:?}" python3 render/fetch_package.py "$SIM_SRC/$PKG_PREFIX/manifest.json" "$PKG" 2>&1 | tee -a "$LOG"
  FR=${PIPESTATUS[0]}
  for f in props-16x9.json narration.wav; do cp "$SIM_SRC/$PKG_PREFIX/$f" "$PKG/$f"; done
  mkdir -p "$PKG/avatar" "$PKG/narration"; cp "$SIM_SRC/$PKG_PREFIX"/avatar-block*.webm "$PKG/avatar/" 2>/dev/null; mv "$PKG/narration.wav" "$PKG/narration/narration.wav"
else
  python3 - <<PY 2>&1 | tee -a "$LOG"
import boto3, os
s3 = boto3.client("s3", endpoint_url=os.environ["R2_ENDPOINT"], aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
p = os.environ["PKG_PREFIX"].rstrip("/")
os.makedirs("/root/pkg/avatar", exist_ok=True); os.makedirs("/root/pkg/narration", exist_ok=True)
for key, dest in ((p + "/props-16x9.json", "/root/pkg/props-16x9.json"), (p + "/manifest.json", "/root/pkg/manifest.json"),
                  (p + "/narration.wav", "/root/pkg/narration/narration.wav"),
                  (p + "/avatar-block1.webm", "/root/pkg/avatar/avatar-block1.webm"), (p + "/avatar-block2.webm", "/root/pkg/avatar/avatar-block2.webm")):
    s3.download_file("workflowdynamic", key, dest); print("PKG_FILE_OK", key, os.path.getsize(dest))
PY
  FR=${PIPESTATUS[0]}
  [ "$FR" = 0 ] && { python3 render/fetch_package.py /root/pkg/manifest.json "$PKG" 2>&1 | tee -a "$LOG"; FR=${PIPESTATUS[0]}; }
fi
[ "$FR" = 0 ] || die "package fetch failed"
# shot 62a: both pricing pages side by side, GoHighLevel on the left
ffmpeg -loglevel error -y -i "$PKG/assets/_gohighlevel-pricing.png" -i "$PKG/assets/_systeme-pricing.png" \
  -filter_complex "[0:v]scale=-2:540[a];[1:v]scale=-2:540[b];[a][b]hstack=inputs=2,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xF4F7FB[o]" -map "[o]" "$PKG/assets/62a.png" || die "62a compose failed"
log "FETCH_DONE seconds=$(( $(date +%s) - t0 ))"
# --- install and browser
t1=$(date +%s)
cd remotion
timeout 900 npm install --no-audit --no-fund --loglevel=error 2>&1 | tail -n 3 | tee -a "$LOG"
[ "${PIPESTATUS[0]}" = 0 ] || { cd ..; die "npm install failed"; }
if [ "$SIM" != 1 ]; then
  BL=$(ldd node_modules/.remotion/chrome-headless-shell/*/*/chrome-headless-shell 2>/dev/null | grep -c 'not found' || true)
  timeout 300 npx remotion browser ensure 2>&1 | tail -n 3 | tee -a "$LOG"
  MISS=$(ldd node_modules/.remotion/chrome-headless-shell/*/*/chrome-headless-shell 2>/dev/null | grep 'not found' | awk '{print $1}' | tr '\n' ' ')
  if [ -n "$MISS" ]; then
    log "BROWSER_LIBS_MISSING $MISS; installing with apt (timeout 600 s)"
    ( timeout 600 apt-get update -qq && timeout 600 apt-get install -y -qq libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2t64 libpango-1.0-0 libcairo2 ) 2>&1 | tail -n 5 | tee -a "$LOG"
    MISS=$(ldd node_modules/.remotion/chrome-headless-shell/*/*/chrome-headless-shell 2>/dev/null | grep 'not found' | awk '{print $1}' | tr '\n' ' ')
    [ -z "$MISS" ] || { cd ..; die "browser libs still missing: $MISS"; }
  fi
  log "BROWSER_OK"
fi
log "SETUP_DONE seconds=$(( $(date +%s) - t1 ))"
# --- render
t2=$(date +%s)
FARGS=(); [ -n "${FRAMES:-}" ] && FARGS=(--frames="$FRAMES")
npx remotion render src/index.ts "${COMP:-Long16x9}" "$OUT/video.mp4" --props="$PKG/props-16x9.json" --public-dir="$PKG" --concurrency="$(nproc)" "${FARGS[@]}" 2>&1 | tr '\r' '\n' | awk 'NR%40==0 || /rror/' | tail -n 60 | tee -a "$LOG"
RC=${PIPESTATUS[0]}
cd ..
echo "STAGE render rc=$RC seconds=$(( $(date +%s) - t2 ))" | tee -a "$LOG"
if [ "$RC" = 0 ]; then
  log "RENDER_DONE $(ffprobe -v error -show_entries stream=width,height,r_frame_rate,duration -of csv=p=0 "$OUT/video.mp4" | head -1) bytes=$(stat -c %s "$OUT/video.mp4")"
fi
finish "$RC"
