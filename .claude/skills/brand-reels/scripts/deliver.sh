#!/usr/bin/env bash
# Make the version that is sent in chat from the high-quality master, in ONE encode that fits the size limit.
# usage: deliver.sh <final_master.mp4> <final.mp4> [max_MB=29]
# If the master already fits, it is copied as is. Otherwise a two-pass x264 (preset slow, tune film) at the highest
# bitrate that fits: two-pass at a target bitrate keeps much more detail than a lower CRF for the same size.
set -euo pipefail
in="$1"; out="$2"; max="${3:-29}"
size=$(stat -c%s "$in"); limit=$(( max * 1024 * 1024 ))
if [ "$size" -le "$limit" ]; then cp "$in" "$out"; echo "fits ($((size/1048576)) MB), copied"; exit 0; fi
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$in")
vbr=$(python3 -c "print(int(($limit*8*0.97)/$dur - 192000))")
log=$(mktemp -d)/pass
ffmpeg -v error -y -i "$in" -c:v libx264 -b:v "$vbr" -preset slow -tune film -pix_fmt yuv420p -pass 1 -passlogfile "$log" -an -f null -
ffmpeg -v error -y -i "$in" -c:v libx264 -b:v "$vbr" -preset slow -tune film -pix_fmt yuv420p -pass 2 -passlogfile "$log" \
  -c:a aac -b:a 192k -movflags +faststart "$out"
echo "two-pass at $((vbr/1000)) kb/s -> $(( $(stat -c%s "$out")/1048576 )) MB"
