---
name: video-edit
description: Full edit of raw talking-head footage in Hebrew or English. Transcribes it, analyses the topics and structure, cuts pauses, fillers and retakes, adds punch-in zooms and transitions, motion-graphic B-roll tied to what is being said (via motion-broll), Hebrew captions, sound effects, music with ducking and loudness normalisation. Use when the user uploads a raw video and asks to edit it, cut it, make it a Reel/Short/YouTube video, or "make it perfect".
---

# Video edit

You are the editor. The user gives raw footage; you give back a finished video plus the parts to fine-tune it. The pipeline is scripted, the **decisions are yours**: what to cut, where to zoom, which moments get B-roll and which transition fits. Make each one on purpose and be able to say why.

`$VE` = `.claude/skills/video-edit`, `$MB` = `.claude/skills/motion-broll`, `$CAP` = `.claude/skills/hebrew-captions`. Work in `motion/`. Run everything from the repo root.

## 0. Setup

`scripts/setup-env.sh` (runs at session start) installs ffmpeg, Playwright, numpy, OpenCV 4, HarfBuzz, fontTools and faster-whisper, and generates the sound effects into `motion/inputs/sfx/`. If anything is missing, run it again.

## 1. Interview (one round, AskUserQuestion)

Skip anything already answered.
- **Brand:** if the video is of a known character, read `motion/brands.json` and use its colours; a new character gets a new entry there.
- **Platform and format:** Reels/TikTok/Shorts (9:16, 1080×1920), YouTube (16:9), or both. This sets the reframe, pacing and caption style.
- **Target length and pacing:** tight (every pause gone, energetic), natural (short breaths kept), or a length target ("up to 60 seconds").
- **Captions:** reels / clean / youtube / none. Font (Heebo/Rubik) and accent colour.
- **B-roll density:** light / medium / heavy (see motion-broll), and the look (default palette or brand colours in `motion/inputs/`).
- **Music:** do they have a track (`motion/inputs/music.*`)? No music is better than generic music.
- **Must keep / must cut:** lines, names, numbers, a call to action.
- **Transcript:** an SRT if they have one (more accurate than automatic transcription).

## 2. Transcribe and analyse

```bash
cp <upload> motion/work/source.mp4
python3 $VE/scripts/transcribe.py motion/work/source.mp4 motion/work/words.json [--srt their.srt]
python3 $VE/scripts/analyze.py motion/work/source.mp4 motion/work/words.json motion/work [--out-W 1080 --out-H 1920]
```

**If the user has the script (AI avatars always do), save it as `motion/<video>/script.txt`** and, after the cut, run
`python3 $VE/scripts/align_script.py words_edited.json script.txt words_captions.json`: timings stay from the audio, the text (punctuation, capitals, spelling, quotes) comes from the script, so captions break on the real sentences. Use `words_captions.json` for the captions.

`transcribe.py` needs huggingface.co reachable for Whisper models (the Hebrew model `ivrit-ai/whisper-large-v3-turbo-ct2` first). If it is blocked, ask for an SRT and say which domain to allow.

`analyze.py` writes `video.json` (resolution, fps, face position, silences), `contact.png`, `transcript.md` (numbered sentences with pauses, `[fillers]`, `(~soft fillers~)`, low-confidence words marked `?`, and `⚠ RETAKE?` where a sentence restarts) and `edit_draft.json` (a first cut). **Read `transcript.md` and look at `contact.png` yourself.**

## 3. Understand the video, then plan

Before touching a segment, write down for yourself:
- **The one-sentence point** of the video and who it is for.
- **The structure:** hook (first 1–3 s), setup, the main beats (usually 2–5 topics), payoff, call to action. Give each topic a short title; these become chapter cards or section transitions.
- **The hook:** the strongest line. If the real hook comes later ("the result: 3 hours saved"), consider moving it to the front as a cold open (a segment can be reordered, since segments are listed in output order).
- **What to cut:** false starts and retakes (keep the *last* good take), fillers, repeated points, tangents that do not serve the point, dead air. Watch for a sentence that ends mid-thought after a cut.
- **Where the eye needs help:** every concrete noun, list, number, process, before/after or tool name is a B-roll candidate. Opinion, emotion and personal lines stay on the face.

Then show the user **one plan table** and wait for approval:

| # | Time (source) | Line | Cut / keep | Framing (zoom) | B-roll (what the shape does, on which word) | Transition | Why |

plus a line on the total length before and after, the caption style, music and the chapter list. Keep it scannable.

## 4. Build the cut (edit.json)

Start from `edit_draft.json`, edit it by hand, save as `motion/work/edit.json`. Schema is in the header of `scripts/render_cut.py`. Then:

```bash
python3 $VE/scripts/render_cut.py motion/work/edit.json motion/out --fast   # quick review render
python3 $VE/scripts/sheet.py motion/out/rough.mp4 motion/work/cut.png --every 4
```

When it is right, render again without `--fast`. The script writes `rough.mp4`, `timeline.json` and `words_edited.json` (word times on the new timeline, used by motion-broll and captions).

### Cutting rules
- Cut on the **pause**, not mid-word: segments start ~0.06 s before the first word and end ~0.12 s after the last (the draft does this). Every segment gets 12 ms audio fades, so cuts do not click.
- Tight is not breathless: keep a beat (0.25–0.4 s) after a punchline, a question or a list item. `--max-gap` in analyze sets how much pause survives inside a segment.
- Never cut inside a word or leave a half-sentence. Read the text of each segment in `edit_draft.json`.
- If two takes exist, keep the one with the better delivery, usually the last one.

### Zoom rules (the framing): less is more
The user's rule: **don't overdo zooms.** Most of the video is plain, steady talking; zooms are a spice for the lines that deserve emphasis, and they are gentle.
- **Default: no zoom change.** Long stretches of normal speech stay on one steady framing (a base framing that sits the speaker well, e.g. 1.0–1.15 on a wide shot). Don't alternate the zoom on every cut, and don't give every segment its own zoom.
- **Zoom only on emphasis lines:** the hook, the key statement or lesson, a punchline, a number, a turn ("but…", "here's the thing"), the call to action. Read the transcript and pick them; a 60 s video usually has **2–4**, never one every few seconds.
- **Gentle amounts:** a punch-in of **+6–10%** (e.g. 1.0 → 1.08), a slow push of **+5–8%** across the line. A snap zoom (`zoom_dur` 0.25, `ease: "out"`) at most **once or twice per video**, on the single strongest line.
- **After an emphasis zoom, return to the base framing** at the next sentence, so the emphasis reads as emphasis.
- **Jump cuts:** avoid cutting inside a flowing sentence; trim pauses between sentences. When a cut in the middle of a thought can't be avoided, hide it with a small framing change (±4–6%), not a big punch.
- Keep the face in frame: `focus` comes from face detection (`video.json`). Check for a moving speaker in `faces`, and set `focus` per segment when needed. For 16:9 → 9:16, `focus` decides the crop; check the stills.
- Max zoom ~1.3 on 1080p sources (quality); 4K sources can go further.

### Transition rules
- The default between segments is a **hard cut**. Transitions are punctuation, not decoration.
- **Topic change / new chapter:** `dip` (0.4–0.5 s to black) or a motion-broll chapter card as a cutaway.
- **Time jump / "after a week":** `fade` 0.3–0.5 s.
- **Energetic moment / list item in a Reel:** `whip` (0.18 s) with the `swoosh-short` sound.
- **Reveal / before→after:** `zoom` or `flash`, with `riser` → `hit`.
- Never more than one styled transition every ~10 s, never two kinds in a row.

## 5. B-roll tied to the words (motion-broll)

Run the motion-broll workflow **on the rough cut**: source = `motion/out/rough.mp4`, words = `motion/out/words_edited.txt` (already in its `words.txt` format). Render the clips at the **output** resolution (1080×1920 for vertical), so they fill the frame.

How to tie B-roll to what is said:
- One clip = one idea, and the idea is literally on screen: the tool they name, the list they count, the number they say (relative bars if no real figure), the process they describe as steps.
- The clip **enters on the word that introduces the idea** and each state change lands on the word it shows. Leave on the face again for emotion, opinion and the call to action.
- Chapters from step 3 → chapter cards (`06-chapter` example) at topic changes.
- Other sources: screen recordings or product shots the user drops in `motion/inputs/` can be cut in as `cutaway` with `src_in`. AI-generated footage (the Higgsfield connector, if connected) costs credits, so only with the user's explicit OK.

### Keyword callouts (light B-roll without covering the speaker)
`scripts/make_callouts.py callouts.json <outdir>` renders short transparent overlays for a key word or 2–3 word phrase that was just said, and prints the `broll` entries for `finish.json`:
- `"kind": "box"`: a dark box with heavy white text inside a cream "selected text" frame with corner handles; pops in, blurs out.
- `"kind": "glass"`: a frosted pill with an icon (shield, check, zap, clock, lock, star, heart, …); rises in with a blur, blurs out.
Put `at` on the word, keep them in the empty area (usually the top third above the head), clear of the captions, and use them sparingly: a few per minute, never two at once. They pair with the `soft` caption style.

## 6. Captions

```bash
python3 $CAP/scripts/make_captions.py motion/out/words_edited.json motion/work/captions.ass \
  --W 1080 --H 1920 --style soft --below-face motion/out/rough.mp4 --srt motion/out/captions.srt [--fix motion/work/fixes.json]
```
Fix misheard names and terms first (`--fix`). During a full-frame cutaway that has its own text, drop those words or move the captions (`--y`).

## 7. Finish: B-roll, captions, sound, loudness

```bash
python3 $VE/scripts/finish.py motion/work/finish.json
```
Schema in the header of `scripts/finish.py`. Times are on the rough-cut timeline (motion-broll file names already say where each clip goes).
- **Sound effects** (`motion/inputs/sfx/`, generated by `make_sfx.py`): `whoosh` or `swoosh-short` ~0.1 s before a cutaway or whip; `pop` on a text pop; `click` on a motion-broll cursor click; `riser` → `hit` into a reveal. Keep them quiet (-8 to -14 dB) and sparse. SFX that repeat on every cut get annoying fast.
- **Music:** `gain_db` -18 to -22 under speech, `duck: true`, fade out at the end.
- **Loudness:** -14 LUFS (YouTube, Instagram, TikTok). The script normalises to it.

## 8. Check, then deliver

- Stills: `python3 $VE/scripts/sheet.py motion/out/final.mp4 motion/work/final.png --every 3` and at every B-roll in/out point. Look at them: face in frame, captions readable and not covering B-roll text, no black frames, transitions clean.
- Audio: `ffmpeg -i motion/out/final.mp4 -af ebur128 -f null -` → I ≈ -14 LUFS, no clipping.
- Sync: spot-check that a few captions land on their words.

Deliver `final.mp4` and `captions.srt` (with the environment's file-sending tool if there is one; otherwise give the paths), and a short summary: what was cut and why (length before → after), the chapter list, the B-roll list with times, and what is illustrative rather than real data. Mention that `rough.mp4`, the B-roll clips and `captions.srt` are there if they want to finish in their own editor, and offer a round of changes ("zoom less", "keep the joke at 0:42", "more B-roll in the middle").

## Honest limits

- You judge picture from stills and contact sheets, not by watching in real time, so check more stills around anything that moves.
- Speech-to-text in Hebrew makes mistakes with names and English terms; read the transcript before captions.
- Stock footage and licensed music are not built in: B-roll is motion graphics, the user's own material, or AI-generated with permission.
