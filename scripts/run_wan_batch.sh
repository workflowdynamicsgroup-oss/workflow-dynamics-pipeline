#!/usr/bin/env bash
# Pod wrapper: all Wan 2.2 TI2V-5B clips of one video on ONE pod (A40 or RTX 4090).
# Order: checks, setup, preflight, model copy to local disk, one generate.py call per clip (each verified with ffprobe),
# summary, R2 upload, hold, self-delete. A clip that already verifies is skipped (resume). Failed clips are retried once.
# Env: RUN_NAME (required), PROMPTS (TSV: id<TAB>shot<TAB>seconds<TAB>prompt; default wan/prompts_ghl_vs_systeme.tsv),
#      FRAMES (default 121 = 5 s at 24 fps, must be 4n+1), WATCHDOG (default 9600 s), PER_CLIP_MAX (default 1800 s), HOLD (default 240 s),
#      DRY_RUN=1 (local test only: stub generator, no setup, no copy, no pod calls), pod secrets RUN_POD_API_KEY, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT.
# Settings follow wan/run_wan.sh: 1280*704, 50 steps, offload_model True, no flash-attn (patched pod-local copy in /root/wan2.2).
set -uo pipefail
cd "$(dirname "$0")/.."
: "${RUN_NAME:?set RUN_NAME}"
DRY_RUN="${DRY_RUN:-0}"
FRAMES="${FRAMES:-121}"; PER_CLIP_MAX="${PER_CLIP_MAX:-1800}"
PROMPTS="${PROMPTS:-wan/prompts_ghl_vs_systeme.tsv}"
LOG_DIR="${LOG_DIR:-/workspace-global/logs/$RUN_NAME}"; mkdir -p "$LOG_DIR"; export LOG_DIR
LOG="$LOG_DIR/run.log"
OUT="${OUT:-/root/wan_out}"; mkdir -p "$OUT"
MODEL_SRC="${MODEL_SRC:-/workspace-global/models/wan2.2-ti2v-5b}"; MODEL_DST="${MODEL_DST:-/root/models/wan2.2-ti2v-5b}"; MIN_MODEL_BYTES="${MIN_MODEL_BYTES:-30000000000}"
log() { echo "$(date -u +%T) $*" | tee -a "$LOG"; }
terminate() { if [ "$DRY_RUN" = 1 ]; then echo "DRY_RUN: would terminate pod"; else bash scripts/self_delete.sh terminate; fi; }
if [ "$DRY_RUN" != 1 ]; then
  ( sleep "${WATCHDOG:-9600}"; echo "WATCHDOG_FIRED: terminating pod"; bash scripts/self_delete.sh terminate ) &
  bash scripts/self_delete.sh check || { echo "SELF_CHECK_FAIL: aborting before any spend"; exit 1; }
  git config --global --add safe.directory "*" 2>/dev/null || true
fi
log "BOOT run=$RUN_NAME pipeline_commit=$(git rev-parse --short HEAD 2>/dev/null || echo no-git) wrapper_sha256=$(sha256sum "$0" | cut -c1-16)"
SUMMARY="$OUT/summary.tsv"; printf 'id\tshot\tseconds\tstatus\tgen_s\n' > "$SUMMARY"
finish() {  # $1 = exit code
  [ "$DRY_RUN" = 1 ] || /root/venv_cap/bin/pip install -q boto3 >/dev/null 2>&1 || python3 -m pip install -q --break-system-packages boto3 >/dev/null 2>&1
  for f in "$OUT"/*.mp4; do [ -s "$f" ] && echo "DURATION $f $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null) s"; done
  PY=/root/venv_cap/bin/python; [ -x "$PY" ] || PY=python3
  FIN=$($PY scripts/finish.py "$RUN_NAME" "$1" "$OUT"/*.mp4 "$SUMMARY" 2>&1); echo "$FIN"
  if ! echo "$FIN" | grep -q '^UPLOAD_OK'; then
    mkdir -p "/workspace-global/outputs/$RUN_NAME" 2>/dev/null && cp "$OUT"/*.mp4 "$SUMMARY" "/workspace-global/outputs/$RUN_NAME/" 2>/dev/null
    echo "UPLOAD_FALLBACK clips kept in /workspace-global/outputs/$RUN_NAME"
  fi
  [ "$DRY_RUN" = 1 ] || sleep "${HOLD:-240}"
  terminate; exit "$1"
}
die() { log "FAIL $*"; echo "STAGE wanbatch rc=1 seconds=0" | tee -a "$LOG"; finish 1; }
[ $(( (FRAMES - 1) % 4 )) -eq 0 ] || die "FRAMES $FRAMES is not 4n+1"
[ -s "$PROMPTS" ] || die "prompts file $PROMPTS missing or empty"
n_prompts=$(grep -c . "$PROMPTS"); log "PROMPTS $PROMPTS n=$n_prompts"
verify() {  # exact frame count, 1280x704, 24 fps
  local f=$1 w h r n
  [ -s "$f" ] || return 1
  IFS=, read -r w h r n < <(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=width,height,r_frame_rate,nb_read_frames -of csv=p=0 "$f" 2>/dev/null </dev/null)
  [ "${w:-0}" = 1280 ] && [ "${h:-0}" = 704 ] && [ "${r:-}" = "24/1" ] && [ "${n:-0}" = "$FRAMES" ]
}
gen() {  # $1 prompt, $2 output file
  if [ "$DRY_RUN" = 1 ]; then ffmpeg -nostdin -v error -y -f lavfi -i "testsrc=size=1280x704:rate=24" -frames:v "$FRAMES" -pix_fmt yuv420p "$2"; return; fi
  ( cd /root/wan2.2 || exit 97
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True timeout "$PER_CLIP_MAX" "${WAN_PY:-/root/venv_wan/bin/python}" -u generate.py \
      --task ti2v-5B --size 1280*704 --ckpt_dir "$MODEL_DST" --frame_num "$FRAMES" --sample_steps 50 --offload_model True \
      --prompt "$1" --save_file "$2" </dev/null 2>&1 | tr '\r' '\n' | { grep -v -i "it/s\]\|s/it\]" || true; } >> "$LOG"
    exit "${PIPESTATUS[0]}" )  # the generator's own exit code, not grep's
}
if [ "$DRY_RUN" != 1 ]; then
  t0=$(date +%s)
  step_rc=0; ( set -e; bash scripts/setup_pod.sh; bash preflight/check_imports.sh ) 2>&1 | tee -a "$LOG" | grep -E "PREFLIGHT_OK|SETUP_DONE|FAIL|MISSING" ; step_rc=${PIPESTATUS[0]}
  echo "STAGE setup rc=$step_rc seconds=$(( $(date +%s) - t0 ))" | tee -a "$LOG"; [ "$step_rc" = 0 ] || die "setup or preflight failed"
fi
if [ "$DRY_RUN" != 1 ] || [ "${TEST_COPY:-0}" = 1 ]; then  # TEST_COPY=1 lets a local test run the copy and size check
  t1=$(date +%s); mkdir -p "$MODEL_DST"
  WANT_BYTES=$(find "$MODEL_SRC" -type f -printf '%s\n' | awk '{s+=$1} END{print s+0}'); [ "$WANT_BYTES" -gt "$MIN_MODEL_BYTES" ] || die "model source on volume is only $WANT_BYTES bytes"
  while IFS= read -r -d '' f; do
    rel=${f#"$MODEL_SRC"/}; mkdir -p "$MODEL_DST/$(dirname "$rel")"; sz=$(stat -c %s "$f")
    if [ "$sz" -lt 67108864 ]; then cp "$f" "$MODEL_DST/$rel"; else bash scripts/chunk_copy.sh "$f" "$MODEL_DST/$rel" "$sz" 16 2>>"$LOG" || die "chunk copy failed for $rel"; fi
  done < <(find "$MODEL_SRC" -type f -print0)
  got=$(find "$MODEL_DST" -type f -printf '%s\n' | awk '{s+=$1} END{print s}'); log "COPY_DONE bytes=$got want=$WANT_BYTES seconds=$(( $(date +%s) - t1 ))"
  [ "$got" = "$WANT_BYTES" ] || die "model copy is $got bytes, want $WANT_BYTES"
  bash scripts/verify_copy.sh "$MODEL_SRC" "$MODEL_DST" 2>&1 | tee -a "$LOG"; [ "${PIPESTATUS[0]}" = 0 ] || die "model copy differs from the volume and could not be repaired"
fi
ok=0; bad=0; t2=$(date +%s)
while IFS=$'\t' read -r id shot secs prompt <&3; do
  [ -z "${id:-}" ] && continue
  f="$OUT/wan_${id}_${shot}.mp4"
  if verify "$f"; then log "WAN_SKIP $id $shot already verified"; printf '%s\t%s\t%s\tskipped\t0\n' "$id" "$shot" "$secs" >> "$SUMMARY"; ok=$((ok+1)); continue; fi
  status=failed; t3=$(date +%s)
  for attempt in 1 2; do
    rm -f "$f"; log "WAN_START $id $shot attempt $attempt"
    if gen "$prompt" "$f" && verify "$f"; then status=ok; break; fi
    log "WAN_ATTEMPT_FAIL $id $shot attempt $attempt"
  done
  [ "$status" = ok ] && { log "WAN_DONE $f"; ok=$((ok+1)); } || { bad=$((bad+1)); rm -f "$f"; }
  printf '%s\t%s\t%s\t%s\t%s\n' "$id" "$shot" "$secs" "$status" "$(( $(date +%s) - t3 ))" >> "$SUMMARY"
done 3< "$PROMPTS"
RC=0; [ "$bad" = 0 ] && [ "$ok" = "$n_prompts" ] || { log "FAIL ok=$ok bad=$bad want=$n_prompts"; RC=1; }
echo "STAGE wanbatch rc=$RC seconds=$(( $(date +%s) - t2 ))" | tee -a "$LOG"; cat "$SUMMARY" | tee -a "$LOG"
finish "$RC"
