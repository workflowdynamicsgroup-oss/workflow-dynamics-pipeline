#!/usr/bin/env bash
# Pod wrapper: the two avatar blocks of one video on ONE pod (A40 or RTX 4090).
# Per block: Chatterbox voices the block text, then Ditto renders the avatar at AVATAR_SIZE. Stops at the first failure.
# Order: self-check, setup, preflight, then block1 and block2 (voice, photo prep, Ditto), summary, R2 upload, hold, self-delete.
# The cutout is NOT run here: run scripts/run_cutout.sh afterwards on the uploaded Ditto blocks (INPUT or INPUT_RUN).
# Env: RUN_NAME (required), BLOCKS_DIR (default avatar/blocks_ghl_vs_systeme; holds block1.txt and block2.txt),
#      BLOCKS (default "block1 block2"; one name re-runs just that block), AVATAR_SIZE (default 720x540), PHOTO_SRC (default volume IMG_3004.png), DITTO_TIMEOUT (default 900 s per block),
#      WATCHDOG (default 4500 s), HOLD (default 240 s), secrets RUN_POD_API_KEY, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
BLOCKS_DIR="${BLOCKS_DIR:-avatar/blocks_ghl_vs_systeme}"
AVATAR_SIZE="${AVATAR_SIZE:-720x540}"
LOG_DIR="${LOG_DIR:-/workspace-global/logs/$RUN_NAME}"; mkdir -p "$LOG_DIR"; export LOG_DIR
LOG="$LOG_DIR/run.log"
OUT=/root/avatar_out; mkdir -p "$OUT"
log() { echo "$(date -u +%T) $*" | tee -a "$LOG"; }
stage() { local n=$1 t0 rc=0; shift; t0=$(date +%s); "$@" || rc=$?; echo "STAGE $n rc=$rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$LOG"; return $rc; }
( sleep "${WATCHDOG:-4500}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
git config --global --add safe.directory "*" 2>/dev/null || true
log "BOOT run=$RUN_NAME pipeline_commit=$(git rev-parse --short HEAD 2>/dev/null || echo no-git) blocks=$BLOCKS_DIR size=$AVATAR_SIZE"
BLOCKS="${BLOCKS:-block1 block2}"
for b in $BLOCKS; do [ -s "$BLOCKS_DIR/$b.txt" ] || { log "FAIL missing $BLOCKS_DIR/$b.txt"; exit 1; }; done
prep_photo() { # scale and crop the photo to AVATAR_SIZE so Ditto renders at the real avatar size
  local src=${PHOTO_SRC:-/workspace-global/inputs/IMG_3004.png}
  echo "PHOTO_SRC $(ffprobe -v error -show_entries stream=width,height -of csv=s=x:p=0 "$src")"
  local w=${AVATAR_SIZE%x*} h=${AVATAR_SIZE#*x}
  ffmpeg -loglevel error -y -i "$src" -vf "scale=${w}:${h}:force_original_aspect_ratio=increase,crop=${w}:${h}" /root/photo.png || return 1
  echo "PHOTO_USED /root/photo.png $(ffprobe -v error -show_entries stream=width,height -of csv=s=x:p=0 /root/photo.png)"
}
block() { # $1 = block name: voice the text, then render Ditto
  local b=$1
  cp "$BLOCKS_DIR/$b.txt" "/root/$b.txt"
  echo "SCRIPT_WORDS $b $(wc -w < "/root/$b.txt")"
  stage "chatterbox_$b" bash chatterbox/run_chatterbox.sh "/root/$b.txt" "/root/$b.wav" /workspace-global/inputs/me.wav || return 1
  stage "ditto_$b" env AUDIO="/root/$b.wav" PHOTO=/root/photo.png OUT="$OUT/$b.mp4" bash ditto/run_ditto.sh || return 1
  cp "/root/$b.wav" "$OUT/$b.wav" 2>/dev/null || true
  [ -s "$OUT/$b.mp4" ] && echo "DURATION $OUT/$b.mp4 $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$b.mp4") s"
}
RC=0
(
  set -e
  stage setup bash scripts/setup_pod.sh
  stage preflight bash preflight/check_imports.sh
  stage photo prep_photo
  for b in $BLOCKS; do block "$b"; done
) || RC=$?
/root/venv_cap/bin/pip install -q boto3 >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
PY=/root/venv_cap/bin/python; [ -x "$PY" ] || PY=python3
echo "DURATION_CHECK done rc=$RC"
FILES=(); for b in $BLOCKS; do FILES+=("$OUT/$b.mp4" "$OUT/$b.wav"); done
FIN=$($PY scripts/finish.py "$RUN_NAME" "$RC" "${FILES[@]}" 2>&1); echo "$FIN"
if ! echo "$FIN" | grep -q '^UPLOAD_OK'; then
  mkdir -p "/workspace-global/outputs/$RUN_NAME" && cp "$OUT"/* "/workspace-global/outputs/$RUN_NAME/" 2>/dev/null
  echo "UPLOAD_FALLBACK kept in /workspace-global/outputs/$RUN_NAME"
fi
sleep "${HOLD:-240}"
bash scripts/self_delete.sh terminate
exit "$RC"
