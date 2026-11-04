#!/usr/bin/env bash
# Prepares a fresh container for the video skills (video-edit, motion-broll, hebrew-captions):
# ffmpeg (with prores_ks and libass), Python libs, Playwright in ./motion/node_modules using the
# pre-installed Chromium (no browser download), and the generated sound effects.
set -e
cd "$(dirname "$0")/.."
if ! command -v ffmpeg >/dev/null; then
  (apt-get install -y -qq ffmpeg || (apt-get update -qq && apt-get install -y -qq ffmpeg)) >/dev/null 2>&1 || echo "ffmpeg install failed"
fi
# Liberation Serif (OFL) is the serif italic used on brand-reels cards.
fc-list 2>/dev/null | grep -q "Liberation Serif" || (apt-get install -y -qq fonts-liberation >/dev/null 2>&1 || true)
# opencv<5: OpenCV 5 dropped the Haar face detector that analyze.py uses.
python3 -c "import numpy, cv2, uharfbuzz, fontTools, faster_whisper; assert cv2.__version__[0] == '4'" 2>/dev/null || \
  pip install -q numpy "opencv-python-headless<5" uharfbuzz fonttools faster-whisper 2>/dev/null || \
  pip install -q --break-system-packages numpy "opencv-python-headless<5" uharfbuzz fonttools faster-whisper
mkdir -p motion/{clips,dist,out,work,inputs}
if [ ! -d motion/node_modules/playwright ]; then
  [ -f motion/package.json ] || echo '{"private":true}' > motion/package.json
  # 1.56.1 matches the Chromium build pre-installed at /opt/pw-browsers (chromium-1194).
  (cd motion && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --silent playwright@1.56.1)
fi
[ -f motion/inputs/sfx/whoosh.wav ] || python3 .claude/skills/video-edit/scripts/make_sfx.py motion/inputs/sfx >/dev/null
echo "video skills environment ready"
