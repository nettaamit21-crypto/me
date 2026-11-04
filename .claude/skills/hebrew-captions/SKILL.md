---
name: hebrew-captions
description: Burned-in Hebrew captions (RTL) with the spoken word highlighted, in Reels/Shorts or clean YouTube style, plus an .srt export. Use when a video needs subtitles or captions in Hebrew (or mixed Hebrew/English), or when the video-edit skill reaches its captions step.
---

# Hebrew captions

Turns word timestamps into captions that read correctly right to left, including English names and numbers inside Hebrew lines. The output is an `.ass` file that ffmpeg (libass) burns in, and a plain `.srt` for YouTube or the editor.

`$CAP` below means this skill's folder (`.claude/skills/hebrew-captions`).

## Why the script lays out every word itself

libass orders a plain Hebrew line correctly, but once override tags split the line (to colour the spoken word), it reorders the words wrongly. So in the highlight styles each word is its own event, placed by the script: it measures each word with HarfBuzz at the real font size, runs a small bidi layout (RTL paragraph, English runs keep their order, numbers follow their neighbours) and positions each word with `\pos`. The `youtube` style has no highlight, so it uses plain lines.

## Run

```bash
python3 $CAP/scripts/make_captions.py words_edited.json motion/work/captions.ass \
  --W 1080 --H 1920 --style reels --font Heebo --accent FFD400 --srt motion/out/captions.srt
```

- `words_edited.json`: word times **on the edited timeline** (from `video-edit/scripts/render_cut.py`). Captions for an unedited video can use `words.json` directly.
- `--style`
  - `reels` (default): Black weight, 2–4 words, the active word in the accent colour and 8% larger, a pop-in when each group starts. For Reels, Shorts and TikTok.
  - `clean`: Bold, up to 7 words, the active word coloured, no pop. For talking-head YouTube and courses.
  - `youtube`: Medium weight on a translucent box, no highlight, sentence-length lines.
  - `extrude`: Instagram-Edits look (from a reference the user liked). Noto Sans Hebrew Black, slightly oblique (`\fax-0.1`), white with a hard grey offset shadow that reads as 3D, 2 words at a time, centred at 60% height (on the chest). No highlight.
  - `soft`: **the user's preferred style, with `--below-face`.** White Heebo Bold, 2–3 words, over a soft blurred dark shadow that keeps it readable on light backgrounds; quick fade. Matched to an Instagram reference the user sent. Pairs with keyword callouts (`video-edit/scripts/make_callouts.py`).
  - `white`: the earlier default. The extrude font, size and placement, plain bright white, no slant, no shadow. Watch readability over light backgrounds (walls, white clothes); if a span is hard to read, move it with `--y` over a darker area and tell the user.
- `--font Heebo | Rubik | NotoSansHebrew` (all OFL, in `fonts/`). Each style has a default (extrude uses Noto Sans Hebrew Black). Heebo is neutral and modern; Rubik is rounder and friendlier.
- `--accent` and `--color` take hex RGB. Match the brand: the motion-broll default accent is `FF5A1F`.
- `--below-face VIDEO` (**use it by default**): each caption is placed under the face in that video's frame at its time, on the top line of the chest (`--chest 0.5` = half a face height below the face box), so captions never sit on the mouth or chin and follow zooms. Pass the video the captions go on (the rough cut).
- `--y 0.70`: vertical centre of the captions (0 = top). Default 0.70 for vertical video (clear of the platform UI at the bottom), 0.84 for horizontal.
- `--max-words`, `--max-chars`: group size. `--keep-punct` keeps commas and full stops (removed by default, the usual style for Hebrew captions).
- `--fix fixes.json`: spelling fixes applied word by word, e.g. `{"קלוד": "Claude", "וויספר": "Whisper"}`. Use it for brand names, English terms the transcript spelled in Hebrew, and misheard words.

Burn in (`finish.py` in video-edit does this through `"captions"`), or directly:

```bash
ffmpeg -i in.mp4 -vf "subtitles=motion/work/captions.ass:fontsdir=$CAP/fonts" -c:a copy out.mp4
```

## Rules

- **Check the transcript before captioning.** Read the words and fix misheard terms, names and numbers with `--fix`. Wrong captions do more harm than no captions.
- Groups break at sentence ends, commas and pauses, and never strand a preposition (`של`, `על`, `את`…), a one-letter prefix, a number, or half an English name (`Claude | Code`).
- Keep captions inside the safe area: vertical videos keep the bottom ~20% and the right edge clear for the platform buttons.
- Never place captions over on-screen text or a motion-graphic panel. Move them (`--y`) or hide them for that span (drop the words from the JSON) during a cutaway that has its own text.
- **Check stills:** grab frames at a few word times (`video-edit/scripts/sheet.py`, or `ffmpeg -i out.mp4 -ss T -frames:v 1`; seek after `-i` so the subtitle times match) and confirm the word order, spacing and highlight.

## Matching a reference

When the user sends a screenshot of captions they like: crop the caption, compare candidate OFL fonts from google/fonts rendered through libass at the same size (weight, width and letter shapes, especially מ ל ש ך), check for slant (`\fax`), shadow offset and colour, and measure size as the caption's width relative to the frame. Add the result as a named style in `STYLES` so it can be reused.
