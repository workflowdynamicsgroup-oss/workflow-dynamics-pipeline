# Changelog

Format: date | run or stage | symptom | cause | fix (commit)

- 2026-11-18 | setup | run scripts lost with earlier sandbox | scripts were never saved to git, R2 or the volume | repo created; wrappers to be rebuilt and committed
- 2026-11-18 | dryrun-a1 | pod failed instantly, DITTO_DIR suffix empty | variable undefined in that shell call | fixed in a21fff1 (pod deleted)
- 2026-11-18 | dryrun-a2 (ob0d7v766yb5dw) | git "dubious ownership" on volume code; chatterbox deps missing; setup stopped | volume files owned by another user; --no-deps install left deps out | safe.directory set in common.sh and fixed deps in 53001a8 (pod deleted)
- 2026-11-18 | dryrun-a3 (ngq86rzu4zj035) | setup stopped on numpy<2 conflict; venv_ditto never built; DITTO_COMMIT_MISMATCH on every run | constraints file pinned numpy; commit check compared to empty string | fixed in d4789c9 (pod deleted, ran about 1 minute)
- 2026-11-18 | process | pod launched for A3 without a price quote or explicit go; pod command had no self-delete | my error | rule restated in README; self-delete to be added before next launch
