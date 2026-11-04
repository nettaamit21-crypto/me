# Showcase edits: "the editor that obeys my voice"

A different format from the character reels: the speaker *commands* the edit ("zoom on my hand", "split the scene into layers",
"hide me") and every command happens on screen, on its words. Output is vertical 1080x1920 with a banner, the **edited** 16:9
panel on top and the **original** (same cut, no effects) below, like the reference reels. First built for the AY Digital Marketing showcase video
(`examples/showcase/`); reuse that folder as the template.

## Pipeline
1. **Source**: often a 4K/60 HEVC phone file, sometimes rotated (ffmpeg auto-rotates). Download from Drive with `fetch_drive.sh`
   (4+ GB is fine, ~2-3 min). Free disk first if needed (old `motion/v*/out/segments`, `.mov`, `rough_graded.mp4`).
2. **Transcribe the whole session** (12 min ≈ 6 min on CPU), print lines grouped by pauses, and **pick takes**:
   the speaker repeats lines and says "לא טוב / עוד פעם / שוב"; take the last good one, after which he says "מצוין" or moves on.
   Check takes with contact sheets (`ffmpeg -ss T -i raw.mov -frames:v 1`) for gestures; a silent action (a throw) may not be in
   the transcript at all. When a word is unclear, re-transcribe that clip with a second model (`large-v3-turbo`) to confirm.
   Watch for false starts inside a take (silencedetect inside the range): "קלוד קוד הרג את כל… [restart] קלוד קוד הרג…".
3. **Cut** with `scripts/smooth_cut.py` (`cut.json`) straight from the 4K source to 1920x1080@30 (lanczos, near-lossless);
   keep action pauses (a held palm, a throw, a turn to the wall), trim dead air. **No raw jump cuts**: between takes pick the
   out/in pair with the best-matching pose inside the silences and join with a 10-frame `morph`; a pause removed inside one
   take is a `ramp`; a pose change too big to morph goes under a motivated move in the compositor (impact flash, card flip)
   as a hard `cut`. Audio: crossfades in silence, never a clipped word tail. Grab a **clean plate** from the empty-room
   seconds at the start.
4. **Re-transcribe the cut** for exact word times; every effect time is a word time from this list.
5. **Person matte**: `scripts/person_matte.py rough.mp4 matte.mkv` (MediaPipe selfie multiclass, 2-pass crop, guided filter,
   temporal smoothing; ~3 fps on 4 cores). Needs `pip install mediapipe`, `apt install libegl1 libgles2`, and the model in
   `motion/inputs/selfie.tflite`. **Hand tracking**: MediaPipe hand landmarker (`motion/inputs/hand.task`), palm = mean of
   landmarks 0,5,9,13,17, size = |0-9|; pick the hand held out; smooth over 5 frames.
6. **Sprites**: every text/label/card is HTML rendered once to a transparent PNG by `scripts/sprites.js` (Heebo, RTL-correct).
   3D objects (coin) and mini reels are rendered as short PNG sequences with Playwright.
7. **Compositor** (`compose.py`): per frame, float32 premultiplied RGBA, effects chosen by time window; `place()` (affine sprite with
   blur-in), `place_quad()` (perspective), `view()` (zoom), `project()` (3D planes). Render in **4 parallel chunks**
   (`--start/--end`, `cv2.setNumThreads(1)`, x264 veryfast crf 8) then concat: ~5 min for 90 s instead of 70.
8. **Layout** (`layout.sh`): captions burned at 1920x1080 first (`make_captions.py --W 1920 --H 1080`, reels style, accent colour, `--size 0.088`), then both panels
   scaled to 1080x608 on an ink canvas with the banner and an "original" tag. **Finish** with SFX and -14 LUFS (`finish.py`).
9. **Deliver**: `deliver.sh` (H.264 two-pass fitted to ~29 MB) is enough for 90 s: on the first showcase video it measured SSIM 0.9946 against
   the master, vs 0.9952 for an HEVC two-pass (`libx265`, `-tag:v hvc1`) of the same size. Send the H.264 (plays everywhere);
   make the HEVC only for a longer video, where H.264 at 29 MB starts to smear.

## Effects (all on the spoken word)
| Command | Effect | How |
|---|---|---|
| hook line | giant words **behind the head**, then a strike-through; background dimmed 30% | sprite over `F*(1-A)`, then the person `F*A` on top |
| "in real time" | words behind head + blinking REC chip | same + front sprite |
| "zoom on my hand" | zoom 1→1.55 centred left of the palm | `view()` with tracked palm |
| "put my logo in 3D" | spinning metallic coin hovering on the palm, warm glow | 60-frame coin turn (CSS 3D) placed at palm − 1.55·size |
| (throw gesture) | coin flies to the lens with a trail, glass cracks, white flash, camera shake | `uu**2.2` path + scale ×10, procedural crack drawn at 2x |
| "split into layers" | wall (clean plate) / me (matte) / text planes separate in 3D, glass edges, numbered labels, layers panel | `project()` with ry −0.72, sep 560, planes back-to-front |
| "hide me" / "bring me back" | me plane fades, panel eye toggles, "מוסתר" chip; then planes fold flat | alpha + sprite swap, spring back |
| prices | hanging price tag swings in, grows to the bigger price, stamp, then **tears in two and falls** on "and today" | zig-zag split of the sprite, gravity + spin |
| "every person" | words behind head + two chips on their words | as the hook |
| "frame right / frame left" | the video shrinks into a rounded portrait card that goes where he points, then right | card crop + rounded mask + soft shadow |
| steps | right-aligned steps card on the free side, each step on its word, "done" pill | sprites |
| "back to full screen" | card expands back | spring |
| "run videos behind me" | 4 phone-shaped mini reels float in 3D **behind** him, playing | `place_quad` into the background layer |
| "documentary" | B&W cut-out on paper with an orange circle, grain, letterbox, tape stamps, title | matte + greyscale + sprites |
| CTA | cream card, him shifted left on an orange circle, "תגיבו ״מדריך״", DM chip | matte shift + sprites |

## Joins (second pass of the first one, after "the cuts aren't perfect")
- Audit every cut before rendering effects: a sheet of last-frame / first-frame / 50% overlay per cut, plus speech edges at
  10 ms. On the first showcase video we found a clipped word tail, a leaked syllable, pauses of 0.1 s and jumps at all 15 cuts.
- Same-take pauses (0.3-0.6 s removed): `ramp` with pre/post inside the silence, peak speed ≈ 1 + 1.5·gap/(pre+post) ≤ 2.
- Between takes: `morph` 10 frames (8 mid-sentence). The head and body morph cleanly; hands that moved a lot cross-dissolve.
- Under effects: the morph shows inside the 3D plane, the card or the B&W cut-out, so it needs nothing more; zooms, dims,
  labels and looks (B&W documentary) must ease across the join, not end on it.
- Throw → next take: hard cut on the impact frame, white from 2 frames before to 1 frame after, then a 0.28 s decay.
- Re-cutting means re-running the matte: run `person_matte.py` only on the ranges whose effects use the matte (text
  behind the head, 3D layers, floating reels, documentary, CTA), 4 ranges in parallel, black elsewhere (~8 min, not 50).
- Re-time effects from the new cut's words with onsets snapped to the audio (Whisper starts words up to 0.3-1 s early
  after a pause): an effect "on the word" is on the measured onset.
- Card on the side → next take with a different pose: the card flips (0.45 s, `project()` about Y), edge-on on the cut frame.

## Lessons from the first one
- `pkill -f "<pattern>"` also matches the shell running it (exit 144). Anchor the pattern: `pkill -f "^python3 motion/clips/…"`.
- A full-frame Gaussian blur per frame (glow, shadows) is the slowest thing: use a prebuilt glow sprite and blur at 1/4 size.
- Hide captions while an on-screen card spells out the same words (the steps), so the panel doesn't carry the same text twice.
- No logo provided → a monogram coin from the business name as a placeholder; say so and offer to swap in the real logo.
