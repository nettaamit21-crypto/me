# Lessons: problems we hit and the fix

## Getting the file
| Symptom | Cause | Fix |
|---|---|---|
| Chat upload rejected | ~30 MB upload limit | Use Drive (`fetch_drive.sh`), or the user compresses (HandBrake / FreeConvert, 1080x1920) |
| Drive connector: "File too large for download, over limit of 10 MB" | connector limit | Use the connector only to find the `id`; download with `fetch_drive.sh` |
| `CONNECT tunnel failed, response 403` | network policy blocks Drive | User adds `drive.google.com` + `drive.usercontent.google.com` in Network access → Custom → Allowed domains |
| Downloaded "mp4" is ~900 KB of HTML, `moov atom not found` | file is private (sign-in page) | User shares "Anyone with the link"; check with `get_file_permissions` |
| Whisper metadata loads, weights 403 | Hugging Face file storage blocked | Allow the hf.co domains listed in CLAUDE.md |

## Words and cutting
| Symptom | Fix |
|---|---|
| Captions/cuts start before the voice after a pause | `analyze.py` snaps word starts to silence ends; always run it before cutting |
| A sentence's first word ("she", "they") hangs before the pause, stretched across it, so the cut drops or misplaces it | `analyze.py` now also moves such short words to the silence end (they are spoken after the pause) |
| A word disappears after the cut | `render_cut.py` maps words by overlap; check `words_edited.json` around cuts |
| A word lands before the pause it follows (e.g. "asked … is" with `is` at the old time), or `e < s` | set `s` to where it's heard (segment start) and `e` > `s` by hand |
| English video, transcript turns into Hebrew halfway | `transcribe.py` defaults to `--lang he`; rerun with `--lang en` |
| `half -naked` split into two caption words | merge words starting with `-` into the previous one in `words_captions.json` |
| `⚠ RETAKE?` on "Never ask him… Never ask him…" | anaphora in a script, not a retake: keep |
| Same script, another character: card times off | re-time each state from the new `words_edited.json` (we measured drifts of -0.04 to +0.47 s) |
| Jump cuts between takes look rough ("the cuts aren't perfect") | `smooth_cut.py`: pick out/in in silence at the best-matching poses (search pairs of frames, lowest grey difference, pause 0.35-0.55 s at a sentence end, ~0.25 s mid-sentence), then a 10-frame optical-flow **morph** centred on the cut |
| A pause removed inside one take still jumps | `smooth_cut.py` **ramp** join: play the window around the pause faster with an eased speed curve (peak ≤ 2x), so motion stays continuous; audio is cut in the silence with a crossfade |
| End of a word clipped ("מל-") or the next word leaking in ("המשחק-ז") | measure speech edges at 10 ms (energy + 3-8 kHz band for fricatives like /f/, /z/); keep a word's full tail (often 0.2-0.3 s of decay), and in connected speech cut in the dip with `xa: 0` so A's audio stops exactly there |
| Effect pops off at a cut (zoom 1.12→1.0, text, dim, a card not quite full) | every effect eases out across the join: zooms return with `eio` over ~0.4 s, branches end only once their weights reach 0 |
| Pose change too big for a morph (sideways → frontal) | hide the join in a motivated move: a white flash on an impact, a card flip that is edge-on on the cut frame |
| Jump cuts on an AI avatar after removing pauses | the same `smooth_cut.py` with an 8-frame `morph` per join (25 fps); gaps under 0.3 s are merged instead (a short pause reads better than a join). Segments keep their `zoom`/`zoom_end` (push/punch/snap), and a morph across a zoom change becomes a smooth push or pull |

## Card
| Symptom | Fix |
|---|---|
| Black card disappears on a dark shirt | 2 px gold hairline on `#shape` (alpha box-shadow) |
| Hook text overflows the card | widen the state (900+), drop the title to 38 px, or shorten |
| Quote mark sits on the text | position it with `left:` (layers have no width, so `right:` measures from the anchor) |
| Element animates past the card edge | smaller offset (≤ 40 px) or clip it |
| Cursor wanders over the card between clicks | rest keys off-stage (y beyond the stage height) |
| "Following" flashes for 0.2 s at the very end | hold the last frame 0.6 s (`grade.sh … 0.6`) and extend the clip's `T` |
| Waiting for a background `render.js` with `pgrep -f render.js` never ends | the wait loop's own command line contains "render.js": wait on the log line (`grep -q rendered render.log`) instead |
| Contact sheets of vertical clips are cropped | our `beats.js` reads the stage size (local change, keep it) |

## Captions
| Symptom | Fix |
|---|---|
| White captions unreadable on a white shirt | `--strong-shadow` |
| Lowercase first words, no sentence breaks | `align_script.py` with a punctuated `script.txt` |
| "her self", "every one" split by Whisper | merge the two words in `words_captions.json` (keep the first word's `s`, the last word's `e`) |
| Last word alone on screen ("it", "man", "address") | lone sentence-end words join a group of up to max+1 words / max_chars+12 (in `make_captions.py`); else add a comma earlier in `script.txt` |
| Awkward break ("you'd be proud / of in a room") | add a comma at the speaker's pause in `script.txt` and re-align |
| Captions over the mouth | `--below-face rough.mp4` (per-caption face detection), `--chest 0.5` |

## Quality
| Symptom | Cause | Fix |
|---|---|---|
| Final looks softer/duller than the source | constant 1.08 zoom (upscale), 4 encode generations at crf 14-23, vignette darkening the face | base zoom 1.0, lanczos, intermediates crf 8-10, no vignette, master crf 14 slow, `deliver.sh` two-pass to fit |

## Delivery
- Chat file delivery is often limited to ~30 MB: `deliver.sh` fits the master into ~29 MB with one two-pass encode. A 500 from the server: just retry.
- Keep only sources in git (`motion/clips/**.html`, scripts, docs), and only in the user's own copy. `motion/v*/`, `*.mp4`, `*.mov`, `*.wav` are git-ignored.
