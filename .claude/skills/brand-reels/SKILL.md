---
name: brand-reels
description: Branded, clean short-form edits (Reels/TikTok/Shorts, 1080x1920) of talking-head videos, especially AI-avatar characters with a brand kit. Pulls the video from an upload or Google Drive, cuts it tight, adds a few gentle emphasis zooms, a warm grade, one branded motion-graphic card that appears only on the meaningful lines (~30-40% of the runtime) and changes on the spoken words (hook, lists, numbered tips, quotes, comparisons, checklists, calendar stories, send/follow ending), soft white captions under the face, sparse sound design and -14 LUFS loudness. Use when someone asks to "edit this video branded / clean / creative / beautiful", to edit a character's video, to add a number and title for each tip, or to make "the same edit" for another video. Orchestrates video-edit, motion-broll and hebrew-captions.
---

# Brand reels

The house style for short vertical videos of a speaker (often an AI character): **the person stays the centre of the frame, the brand lives in one elegant card on the lap/table area, captions sit under the chin, and every visual change lands on a spoken word.** Nothing on screen is invented: every title, chip and quote is the speaker's own words, shortened.

This skill is the playbook on top of three tool skills in this repo. Read them when you need details:
- `video-edit` (`$VE=.claude/skills/video-edit`): transcription, analysis, `render_cut.py`, `align_script.py`, `finish.py`, `sheet.py`, sound effects.
- `motion-broll` (`$MB=.claude/skills/motion-broll`): the clip engine (one shape that morphs, springs, cursor). **Read its `SKILL.md` and `reference/engine-api.md` before writing a card.**
- `hebrew-captions` (`$CAP=.claude/skills/hebrew-captions`): captions (English or Hebrew), `soft` style, `--below-face`, `--strong-shadow`.

`$BR=.claude/skills/brand-reels`. Run everything from the repo root. Work per video in `motion/<v>/` (git-ignored; e.g. `motion/v11/`).

## The pipeline at a glance

| Step | Command | Output |
|---|---|---|
| 0. Source | `$BR/scripts/fetch_drive.sh <id> motion/<v>/source.mp4` or copy the upload | `source.mp4` |
| 1. Words | `python3 $VE/scripts/transcribe.py source.mp4 words.json --lang en` (`--lang he` for Hebrew) | word times |
| 2. Analyse | `python3 $VE/scripts/analyze.py source.mp4 words.json motion/<v>` | `transcript.md`, `video.json` (face), `contact.png` |
| 3. Cut | `python3 $BR/scripts/auto_cut.py words.json edit.json --source source.mp4 --video-json video.json --push … --snap … --print` | `edit.json` |
| 4. Render cut | `python3 $VE/scripts/render_cut.py edit.json motion/<v>/out` | `rough.mp4`, `words_edited.json` |
| 4b. Smooth joins | when takes are joined (real footage, retakes, showcase): `python3 $BR/scripts/smooth_cut.py cut.json motion/<v>/out` with a `morph` (between takes, at matched poses) or `ramp` (pause inside a take) per join; see `reference/lessons.md` | `rough.mp4` without jump cuts, `timeline.json` |
| 5. Card | write `motion/clips/<series>/01-<name>.html` (or `make_tips_card.py`), build, preview with `beats.js`, render `.mov` | `card_0m00s00.mov` |
| 6. Grade | `$BR/scripts/grade.sh rough.mp4 rough_graded.mp4 [hold]` | warm grade + vignette |
| 7. Captions | `align_script.py` → `make_captions.py --style soft --below-face rough.mp4 [--strong-shadow]` | `captions.ass`, `captions.srt` |
| 8b. Deliver | `$BR/scripts/deliver.sh final_master.mp4 final.mp4` | one two-pass encode that fits ~29 MB |
| 8. Finish | `python3 $BR/scripts/make_finish.py …` → `python3 $VE/scripts/finish.py finish.json` | `final.mp4` at -14 LUFS |
| 9. QA | `$BR/scripts/stills.sh final.mp4 sheet.png t1 t2 …` + `ebur128` | look at every still |
| 10. Deliver | send `final.mp4` + `captions.srt` to the user; save the card source locally | |

Card steps 5 and 6-7 are independent: start the `.mov` render in the background (`render.js` takes ~1 min per 25 s) and grade/caption meanwhile.

## 0. Getting the video

- **Upload in chat:** the chat upload limit is ~30 MB; long source files are bigger. Prefer Drive.
- **Google Drive:** find the file with a Google Drive connector if one is connected (e.g. its file search, e.g. `title = 'סרטון 3'` or `title contains 'Untitled_Video'`); take its `id`. The connector's own download stops at 10 MB, so download with `fetch_drive.sh`, which needs:
  1. the environment's network policy to allow `drive.google.com` and `drive.usercontent.google.com` (environment settings → Network access → Custom → Allowed domains; keep the existing entries);
  2. the file shared as **"Anyone with the link"** (viewer). A private file returns a sign-in page; the script says `PRIVATE`. Sharing the whole folder by link avoids asking every time. `get_file_permissions` shows whether a file is shared.
- Check: `ffprobe` resolution and fps (AI avatars here are 1080x1920 @ 25). Match them in every output.

## 1-2. Words, transcript, character

- `transcribe.py` defaults to Hebrew (`--lang he`, ivrit-ai model). **For English speech always pass `--lang en`** (large-v3-turbo): the Hebrew model translates English into Hebrew, sometimes only from the middle of the video on, so a transcript that starts in English can turn into Hebrew halfway. Needs the Hugging Face domains (see CLAUDE.md).
- `analyze.py` snaps Whisper's early word starts to silence ends, finds the face (`video.json → focus`) and writes `transcript.md`. **Read the transcript and look at `contact.png`.** It also flags `⚠ RETAKE?`: for scripted AI avatars these are usually anaphora ("Never ask him… Never ask him…"), not retakes. Don't cut them.
- **Who is it?** Compare a frame with earlier characters (`motion/brands.json`, earlier `motion/v*/source.mp4`). Use that character's colours. Unknown character in the same niche: keep the closest kit, put no name on the Follow card, and ask the user for the name afterwards (then add a `brands.json` entry).
- **The script:** AI avatars always have one. Write `script.txt` from the transcript with real punctuation (capitals, commas where the speaker pauses, apostrophes, quotes). It drives caption line breaks.

## 3-4. The cut

`auto_cut.py` turns every pause longer than 0.45 s into a cut, pads 0.10 s before / 0.24 s after the words (a breath, not a gasp), and keeps the spoken list numbers ("1.", "2.") in. They are where the card changes. Typical result: 60-72 s raw → 50-56 s.

**Framing:** the base framing is the source framing, `1.0`. **Every zoom above 1.0 upscales the picture and costs detail** (a constant 1.08 base cut face sharpness by ~30%), so only the emphasis lines zoom. `focus` a bit below the face centre. Emphasis is opt-in by phrase:
- `--push "phrase"`: slow push-in across that segment (+0.07): the hook, the key lesson, the payoff line.
- `--punch "phrase"`: the segment one step tighter (+0.06), back to base after: a punchline, the CTA.
- `--snap "phrase"`: fast punch-in (+0.08 in 0.3 s): **once per video**, the strongest line.
- 2-4 emphasis segments per video in total. Most of the video is steady. Never two in a row.

Then `render_cut.py edit.json motion/<v>/out`. Check `words_edited.json`. A word Whisper stretched across a cut pause can land on the wrong side (`s` too early, or `e < s`). Fix such a word by hand (set `s` to the segment start where it is really heard, `e` > `s`) before captions and card timing.

## 5. The branded card: one shape, changes on words

Read `reference/card-patterns.md` for the pattern library and `templates/` for working sources. The essentials:

- **Less is more: the card is on screen only 30-40% of the video.** The user's rule: 60-70% of the runtime is the speaker alone (face + captions); the card appears on the meaningful lines only. Pick 3-5 moments: the hook, the strongest list or contrast, the key quote/payoff, the CTA. Skip the rest even if a pattern would fit. Measure it: `sum(window lengths) / video length` must be 0.30-0.40.
- **One clip for the whole video, shown in windows**, transparent (`bg:null`), stage `1080 x 420-560`, overlaid at `y ≈ 1060-1120` on the 1920 frame: the lap/table area, under the captions, above the bottom UI zone. Clip time = rough-cut time (overlay `at: 0`), so card times are just word times from `words_edited.json`.
- **States** = sections of the video: hook → (list / quote / compare / checklist / calendar / numbered tips) → send → follow. All states hang from one top edge (`geom: g.cy = TOP + g.h/2`) so the card grows downward and never jumps.
- **Windows:** `const WIN=[[a,b],…]` (rough-cut times) and in `geom` multiply `g.op` and `g.sc` by an eased on/off value (see `reference/card-patterns.md`, "Windows"). Change the SEQ state **while the card is hidden** (0.6-0.8 s before the window opens) so it enters already in its new shape; keep the last item of a window on screen ≥ 1 s after it appears. Sound only inside windows: one whoosh as each window opens, pops on that window's items.
- **Every change sits on its word:** the state change on the word that opens the section (or the spoken number), each chip/row on the word it names. A strike-through on the word that rejects it.
- **Brand colours from `motion/brands.json`.** Ivory cards with ink text for content, ink (black) cards with ivory/gold text for hook, quotes and CTA. A **2 px gold hairline** around the shape (`html.alpha #shape{box-shadow:0 0 0 2px <gold>e6, 0 16px 46px rgba(0,0,0,.35)}`) keeps black cards visible on dark shirts and makes everything look finished.
- **Type:** Geist (the engine's sans) bold for titles and chips; `Liberation Serif` italic (`.sf`) for quotes, the big hook number and tip numbers: an editorial, premium accent. Gold (`gold_light`) for the one key word of a quote.
- **Text is the speaker's words**, shortened to 2-6 words. No new numbers, claims or names. Unknown character name → "Follow for more", no name.
- **Ending:** a "Send this" pill whose icon gets clicked by the cursor on "send", then (if they say "follow") a Follow button that flips to "✓ Following" on "follow". If "follow" is the last word, add a 0.6 s hold at the end (`grade.sh … 0.6`) so the flip is visible.
- **Numbered tips** ("10 things…", "5 signs…"): don't hand-write. Fill a spec and run `python3 $BR/scripts/make_tips_card.py spec.json motion/clips/<series>/01-tips.html` (see `templates/tips-spec.example.json`). Each tip gets the gold number and its title from the spoken number until the next one, plus a progress bar.

Build, preview, render:
```bash
python3 $MB/engine/build.py motion/dist motion/clips/<series>/01-<name>.html
NODE_PATH=./motion/node_modules node $MB/engine/beats.js motion/dist/01-<name>.html motion/<v>/beats.png <one time per state>
NODE_PATH=./motion/node_modules node $MB/engine/render.js motion/dist/01-<name>.html motion/<v>/out/card_0m00s00.mov 25/1
```
**Look at `beats.png` before rendering.** Typical fixes: text overflowing the card (widen the state or shorten the text), a quote mark on top of the text (position it with `left:`, since layers have no width and `right:` does not work), an element sliding past the card edge.

## Quality: keep every generation near-lossless
The user noticed quality loss. Measured on video 6 (face-area detail, source = 370): old pipeline 146, new pipeline 312. What changed:
- base zoom 1.0 (no constant upscale), lanczos scaling in `render_cut.py`;
- intermediates near-lossless: segments crf 8, rough crf 10, graded crf 10 (`yuv420p`);
- no vignette in the grade (it darkened the face ~20% and read as "lower quality");
- `finish.py` writes a master at crf 14 / preset slow (`make_finish.py` defaults), and `deliver.sh` makes the chat copy in **one** two-pass encode at the highest bitrate that fits ~29 MB (never re-encode a delivered file with a lower CRF).

## 6. Grade

`$BR/scripts/grade.sh rough.mp4 rough_graded.mp4 [hold]`: contrast +4%, saturation +6%, a little warmth in the highlights, no vignette, near-lossless. It makes AI-avatar footage feel filmed, not rendered. Keep it subtle, skin must stay natural. The captions' face detection still runs on `rough.mp4`.

## 7. Captions

```bash
python3 $VE/scripts/align_script.py motion/<v>/out/words_edited.json motion/<v>/script.txt motion/<v>/words_captions.json
python3 $CAP/scripts/make_captions.py motion/<v>/words_captions.json motion/<v>/captions.ass --W 1080 --H 1920 \
  --style soft --below-face motion/<v>/out/rough.mp4 --srt motion/<v>/out/captions.srt [--strong-shadow]
grep -v -- '-->' motion/<v>/out/captions.srt | grep -v '^[0-9]*$' | grep . | tr '\n' '|'   # read every line
```
- `soft`: white Heebo Bold, 2-3 words, soft shadow, under the face on the top line of the chest. The user's chosen look.
- **Light background behind the captions** (white shirt, bright wall): add `--strong-shadow` (a darker, wider halo). Check a still.
- Read the caption lines. Fix: a split word ("her self" → merge into "herself" in `words_captions.json`), an orphan last word, an awkward break. Add a comma in `script.txt` where the speaker pauses (`proud of, in a room`) and re-align.
- The spoken list numbers are dropped from captions automatically; the card shows them.

## 8. Finish

```bash
python3 $BR/scripts/make_finish.py motion/<v>/finish.json --video motion/<v>/out/rough_graded.mp4 --final motion/<v>/out/final.mp4 \
  --card motion/<v>/out/card_0m00s00.mov --card-y 1100 --captions motion/<v>/captions.ass \
  --whoosh 0.3 --swoosh <section changes…> --pop <chips/rows…> --click <cursor clicks…>
python3 $VE/scripts/finish.py motion/<v>/finish.json
```
Sound is sparse: one whoosh as the card enters, a short swoosh on section/tip changes, a soft pop on chips and rows, a click on each cursor click. No music unless the user supplies a track. `finish.py` normalises to -14 LUFS.

## 9. QA (always, before sending)

- `stills.sh final.mp4 sheet.png` at one time inside every card state, plus the hook and the end. **Look at it:** face clear, captions under the chin and not touching the card, card text fits, black cards visible, nothing over the mouth.
- `ffmpeg -i final.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "I:|Peak:" | tail -2` → I ≈ -14 LUFS, peak below -1 dBFS.
- Size: chat file delivery is often limited to ~30 MB. Use `deliver.sh final_master.mp4 final.mp4` (two-pass to fit); never a second CRF re-encode.

## 10. Deliver

Send `final.mp4` and `captions.srt` to the user (use the environment's file-sending tool if there is one; otherwise give the file paths). Keep the card source (`motion/clips/<series>/*.html`) in the local copy; never push it to the AY source repository (see "Local learning" in CLAUDE.md). Reply in the user's language (Hebrew for this user) with:
- length before → after;
- the card concept and its states, in order, with the words they land on;
- the emphasis zooms;
- anything shortened, and that all on-screen text is the speaker's own words;
- what's missing (e.g. the character's name for the Follow card) and the one question that unblocks it.

## Rules that came from the user (keep them)

- Brand-clean, the person is the centre. Graphics in the lower part of the frame, never over the face or mouth.
- **Pop-ups/cards on only 30-40% of the runtime**, on meaningful words and sentences; 60-70% of the video has no card at all.
- Captions: `soft` style under the face on the top line of the chest, not on the mouth or chin, only bottom captions (no extra callout pop-ups duplicating the captions).
- Zooms gentle and few. No slanted/grey 3D caption styles.
- Each character's brand colours are remembered in `motion/brands.json`. New character or colours → update it.
- "Same edit for this character" = reuse the card source, re-time every state to the new voice track (compare word times; the same script can drift ±0.5 s), swap name/colours.
- Never invent numbers, quotes, results or names.
- **Names on cards:** the Follow/CTA card shows the character's name (`handle` in `motion/brands.json`, e.g. "AY Digital Marketing") only when the video is that character's. Other characters' videos get their own name; the user's own business videos get his business brand, never a character's name. Unknown character → no name, and ask.

**Showcase videos** (the speaker commands the edit: "zoom on my hand", "split into layers", "hide me"; edited panel over the original): follow `reference/showcase-effects.md` and the template in `examples/showcase/` (person matte, hand tracking, sprites, compositor, layout).

More detail: `reference/card-patterns.md` (pattern library with code), `reference/lessons.md` (pitfalls and fixes we hit), `templates/` (working cards).
