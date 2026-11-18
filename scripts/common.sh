#!/usr/bin/env bash
# Shared helpers. Every run writes its commit and wrapper hashes as the first log lines.
set -euo pipefail
RUN_NAME="${RUN_NAME:?set RUN_NAME}"
git config --global --add safe.directory "*" 2>/dev/null || true
LOG_DIR="${LOG_DIR:-/workspace-global/logs/${RUN_NAME}}"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run.log"
log() { echo "$(date -u +%H:%M:%S) $*" | tee -a "$LOG"; }
header() {
  local repo_sha
  repo_sha=$(cd "$(dirname "$0")/.." && git rev-parse --short HEAD 2>/dev/null || echo "no-git")
  log "BOOT run=$RUN_NAME pipeline_commit=$repo_sha wrapper_sha256=$(sha256sum "$0" | cut -c1-16)"
}
