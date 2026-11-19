#!/usr/bin/env bash
# Dry run: setup, preflight, 10 s Chatterbox narration, 10 s Ditto render. Stops at the first failure.
# Always: summary + R2 upload, hold HOLD seconds so the live log can be read, then self-delete.
# Env: RUN_NAME (required), HOLD (default 240), WATCHDOG (default 1500 s), TEXT_FILE (default test/narration10.txt),
#      CAPTIONS=1 (run the caption stage after narration), SKIP_DITTO=1 (narration and captions only), FAILTEST=hang|fail (inject a hang or a failing stage to test watchdog and self-delete),
#      PHOTO_SRC (default: volume IMG_3004.png), AVATAR_SIZE (e.g. 720x540, default: photo as is), DITTO_TIMEOUT (default 900 s), plus pod secrets RUN_POD_API_KEY, R2_*.
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
OUTDIR=/workspace-global/outputs/$RUN_NAME
OUT=$OUTDIR/ditto.mp4
# Watchdog: whatever hangs, the pod terminates itself after WATCHDOG seconds (default 25 min)
( sleep "${WATCHDOG:-1500}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
mkdir -p "$OUTDIR"
stage() { local n=$1 t0 rc=0; shift; t0=$(date +%s); "$@" || rc=$?; echo "STAGE $n rc=$rc seconds=$(( $(date +%s) - t0 ))"; return $rc; }
prep_photo() { # AVATAR_SIZE=WxH resizes the photo (cover, then crop) so Ditto renders at the real avatar size
  local src=${PHOTO_SRC:-/workspace-global/inputs/IMG_3004.png}  # PHOTO_SRC: a path inside the repo (for example inputs/avatar_portrait_S1.png) or on the volume
  echo "PHOTO_SRC $(ffprobe -v error -show_entries stream=width,height -of csv=s=x:p=0 "$src")"
  if [ -n "${AVATAR_SIZE:-}" ]; then
    local w=${AVATAR_SIZE%x*} h=${AVATAR_SIZE#*x}
    ffmpeg -loglevel error -y -i "$src" -vf "scale=${w}:${h}:force_original_aspect_ratio=increase,crop=${w}:${h}" /root/photo.png || return 1
    echo "PHOTO_USED /root/photo.png $(ffprobe -v error -show_entries stream=width,height -of csv=s=x:p=0 /root/photo.png)"
  else
    cp "$src" /root/photo.png
  fi
}
captions_stage() { # transcribe the narration; word count must be within 3% of the script
  /root/venv_cap/bin/python captions/make_captions.py /root/dry.wav /root/captions || return 1
  /root/venv_cap/bin/python - <<'PY'
import json, sys
n = len(json.load(open("/root/captions/captions.json")))
s = len(open("/root/dry.txt").read().split())
gaps = [b["startMs"] - a["endMs"] for a, b in zip(json.load(open("/root/captions/captions.json")), json.load(open("/root/captions/captions.json"))[1:])]
print(f"CAPTIONS_CHECK words={n} script_words={s} longest_gap_ms={max(gaps) if gaps else 0}")
sys.exit(0 if abs(n - s) <= max(2, 0.03 * s) else 1)
PY
}
(
  set -e
  case "${FAILTEST:-}" in
    hang) stage hang sleep 3600 ;;
    fail) stage fail false ;;
    *)
      stage setup bash scripts/setup_pod.sh
      stage preflight bash preflight/check_imports.sh
      cp "${TEXT_FILE:-test/narration10.txt}" /root/dry.txt
      echo "SCRIPT_WORDS $(wc -w < /root/dry.txt)"
      if [ -z "${SKIP_DITTO:-}" ]; then stage photo prep_photo; fi
      stage chatterbox bash chatterbox/run_chatterbox.sh /root/dry.txt /root/dry.wav /workspace-global/inputs/me.wav
      if [ -n "${CAPTIONS:-}" ]; then stage captions captions_stage; fi
      if [ -z "${SKIP_DITTO:-}" ]; then stage ditto env AUDIO=/root/dry.wav PHOTO=/root/photo.png OUT="$OUT" bash ditto/run_ditto.sh; fi
      ;;
  esac
)
RC=$?
/root/venv_cap/bin/pip install -q boto3 >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
PY=/root/venv_cap/bin/python; [ -x $PY ] || PY=python3
for f in /root/dry.wav "$OUT"; do [ -s "$f" ] && echo "DURATION $f $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null) s"; done
$PY scripts/finish.py "$RUN_NAME" "$RC" "$OUT" /root/dry.wav /root/captions/captions.json /root/captions/captions.srt
sleep "${HOLD:-240}"
bash scripts/self_delete.sh terminate
