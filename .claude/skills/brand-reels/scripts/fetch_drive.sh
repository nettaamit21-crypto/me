#!/usr/bin/env bash
# Download a Google Drive video by file id (or share link) straight into the container.
# usage: fetch_drive.sh <file-id-or-link> <out.mp4>
# Needs drive.google.com + drive.usercontent.google.com in the environment's allowed domains, and the
# file shared as "Anyone with the link". The Drive connector itself can only download files under 10 MB,
# so use it only to *find* the file id (search by title), then fetch it here.
set -euo pipefail
id="$1"; out="$2"
[[ "$id" == *"/d/"* ]] && id="$(sed -E 's#.*/d/([^/?]+).*#\1#' <<<"$id")"
[[ "$id" == *"id="* ]] && id="$(sed -E 's#.*id=([^&]+).*#\1#' <<<"$id")"
mkdir -p "$(dirname "$out")"
code=$(curl -sSL --max-time 900 -o "$out" -w '%{http_code}' \
  "https://drive.usercontent.google.com/download?id=${id}&export=download&confirm=t") || {
  echo "BLOCKED: the network policy denies Drive. Add drive.google.com and drive.usercontent.google.com to Allowed domains." >&2; exit 2; }
if ! ffprobe -v error "$out" >/dev/null 2>&1; then
  if grep -q -i 'sign-in\|accounts.google' "$out" 2>/dev/null; then
    echo "PRIVATE: Drive returned a sign-in page. Ask the user to share the file as 'Anyone with the link' (viewer)." >&2
  else
    echo "FAILED: HTTP $code, not a video." >&2
  fi
  rm -f "$out"; exit 3
fi
ffprobe -v error -show_entries stream=codec_type,width,height,r_frame_rate:format=duration,size -of compact "$out"
