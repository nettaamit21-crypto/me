#!/usr/bin/env bash
# Contact sheet of single frames at given times (seek after -i so burned-in captions match).
# usage: stills.sh <video> <sheet.png> t1 t2 t3 ...   (5 per row, 300 px wide each)
set -euo pipefail
v="$1"; out="$2"; shift 2
d=$(mktemp -d); i=0
for t in "$@"; do ffmpeg -v error -y -i "$v" -ss "$t" -frames:v 1 -vf scale=300:-2 "$d/s$(printf %03d $i).png"; i=$((i+1)); done
cols=$(( i < 5 ? i : 5 ))
ffmpeg -v error -y -pattern_type glob -i "$d/s*.png" -vf "tile=${cols}x$(( (i+cols-1)/cols ))" -frames:v 1 "$out"
rm -rf "$d"; echo "$out"
