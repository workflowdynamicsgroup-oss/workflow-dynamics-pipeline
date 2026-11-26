#!/usr/bin/env bash
# Verify a model copy byte for byte: every file of 64 MB or more in SRC is compared with its copy in DST (cmp, 8 at a time).
# A file that differs is copied again with a single plain cp and compared once more. Exit 0 only when every file matches.
# Why: on 2026-11-26 the chunked copy of the Wan T5 file arrived with the right size but wrong bytes (differed at byte 7,878,881,281),
# so every clip failed to load it. A size check cannot see that. Usage: scripts/verify_copy.sh SRC DST
set -uo pipefail
SRC=${1:?SRC}; DST=${2:?DST}
t0=$(date +%s)
compare() { find "$SRC" -type f -size +64M -printf '%P\n' | xargs -r -P 8 -I{} sh -c 'cmp -s "$1/$3" "$2/$3" || echo "$3"' _ "$SRC" "$DST" {}; }
n=$(find "$SRC" -type f -size +64M | wc -l)
BAD=$(compare)
if [ -n "$BAD" ]; then
  echo "COPY_MISMATCH $(echo "$BAD" | tr '\n' ' ')"
  for rel in $BAD; do cp "$SRC/$rel" "$DST/$rel" || { echo "COPY_REPAIR_FAIL $rel"; exit 1; }; done
  BAD2=$(compare)
  [ -z "$BAD2" ] || { echo "COPY_STILL_BAD $(echo "$BAD2" | tr '\n' ' ')"; exit 1; }
  echo "COPY_REPAIRED $(echo "$BAD" | tr '\n' ' ')"
fi
echo "COPY_VERIFIED files=$n seconds=$(( $(date +%s) - t0 ))"
