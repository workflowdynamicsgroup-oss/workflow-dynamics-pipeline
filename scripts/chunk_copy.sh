#!/usr/bin/env bash
# Parallel chunked copy: chunk_copy.sh SRC DST SIZE_BYTES [STREAMS=16]. 256 MiB pieces; DST is preallocated, pieces written in place.
set -euo pipefail
SRC="$1"; DST="$2"; WANT="$3"; N="${4:-16}"
truncate -s "$WANT" "$DST"
pieces=$(( (WANT + 268435455) / 268435456 ))
for i in $(seq 0 $((pieces-1))); do
  while [ "$(jobs -rp | wc -l)" -ge "$N" ]; do sleep 0.2; done
  dd if="$SRC" of="$DST" bs=1M skip=$((i*256)) seek=$((i*256)) count=256 conv=notrunc status=none &
done
wait
