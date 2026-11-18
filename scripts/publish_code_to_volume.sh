#!/usr/bin/env bash
# Run once on a CPU pod with the global volume mounted, to place pinned code on the volume.
# The volume copy keeps its .git folder, so the commit can be checked on every run.
set -euo pipefail
clone_pin() { # repo url, commit, target dir on volume
  if [ ! -d "$3/.git" ]; then git clone -q "$1" "$3"; fi
  git -C "$3" fetch -q --depth 1 origin "$2"
  git -C "$3" checkout -q "$2"
  echo "PINNED $3 $(git -C "$3" rev-parse HEAD)"
}
mkdir -p /workspace-global/code
clone_pin https://github.com/antgroup/ditto-talkinghead c3e47eee2e626500017a0556b470d6d4182f85e8 /workspace-global/code/ditto-talkinghead@c3e47ee
clone_pin https://github.com/Wan-Video/Wan2.2 1ea34ff48f87168174e12956e200b1d908b1c5ff /workspace-global/code/wan2.2@1ea34ff
