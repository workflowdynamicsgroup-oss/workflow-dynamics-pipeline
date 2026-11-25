#!/usr/bin/env bash
# Merge a Ditto avatar mp4 with its cutout matte (alpha.mp4) into a VP9 webm with alpha.
# Usage: scripts/make_avatar_alpha.sh AVATAR.mp4 ALPHA.mp4 OUT.webm
# Output is 768x576 (2x the 16:9 avatar box); Remotion scales it for both formats.
set -euo pipefail
ffmpeg -v error -y -i "$1" -i "$2" \
  -filter_complex "[0:v]scale=768:576,format=yuva420p[v];[1:v]scale=768:576,format=gray[m];[v][m]alphamerge[o]" \
  -map "[o]" -an -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 33 -auto-alt-ref 0 -row-mt 1 "$3"
