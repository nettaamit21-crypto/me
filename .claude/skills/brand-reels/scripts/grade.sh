#!/usr/bin/env bash
# Subtle warm grade (a touch of contrast, saturation and warm highlights) on the rough cut. No vignette: on these
# framings it darkened the face ~20% and read as lower quality. Near-lossless (crf 10) so it costs no detail; with an optional frozen hold at the end
# (so a final Follow/Send click has time to read). Audio is padded with silence to match.
# usage: grade.sh <rough.mp4> <rough_graded.mp4> [hold_seconds=0]
set -euo pipefail
in="$1"; out="$2"; hold="${3:-0}"
vf="eq=contrast=1.04:saturation=1.06,colorbalance=rh=0.03:gh=0.01:bh=-0.03:rs=0.01:bs=-0.01"
af="anull"
if [ "$hold" != "0" ]; then vf="$vf,tpad=stop_mode=clone:stop_duration=$hold"; af="apad=pad_dur=$hold"; fi
ffmpeg -v error -y -i "$in" -vf "$vf" -af "$af" -c:v libx264 -crf 10 -preset medium -pix_fmt yuv420p -c:a aac -b:a 256k "$out"
ffprobe -v error -show_entries format=duration -of csv=p=0 "$out"
