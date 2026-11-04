"""Write finish.json for video-edit/scripts/finish.py from a few flags: graded cut, one card overlay, captions,
and a sparse sound map. Times are on the rough-cut timeline.

usage: python3 make_finish.py <out/finish.json> --video rough_graded.mp4 --final final.mp4 --card card.mov --card-y 1100
         --captions captions.ass [--whoosh 0.3] [--swoosh 9.0 25.8 ...] [--pop 12.9 14.3 ...] [--click 53.4 54.5]
         [--music motion/inputs/music.mp3] [--crf 21]
Levels (tested on voice-only AI-avatar reels): whoosh -18 dB on the card's entrance, swoosh-short -20 dB just
before a section change (pass the change time; it is shifted 0.06 s earlier), pop -22 dB on a chip/row appearing,
click -15 dB on a cursor click. Keep it sparse: one sound per visual change, never on every cut.
"""
import argparse, json
S = 'motion/inputs/sfx/'
ap = argparse.ArgumentParser(); ap.add_argument('out')
ap.add_argument('--video', required=True); ap.add_argument('--final', required=True)
ap.add_argument('--card'); ap.add_argument('--card-y', type=int, default=1100); ap.add_argument('--card-at', type=float, default=0)
ap.add_argument('--captions'); ap.add_argument('--fontsdir', default='.claude/skills/hebrew-captions/fonts')
for k in ('whoosh', 'swoosh', 'pop', 'click'): ap.add_argument('--' + k, type=float, nargs='*', default=[])
ap.add_argument('--music'); ap.add_argument('--crf', type=int, default=14)
a = ap.parse_args()
sfx = [{'file': S + 'whoosh.wav', 'at': t, 'gain_db': -18} for t in a.whoosh]
sfx += [{'file': S + 'swoosh-short.wav', 'at': round(max(0, t - 0.06), 2), 'gain_db': -20} for t in a.swoosh]
sfx += [{'file': S + 'pop.wav', 'at': t, 'gain_db': -22} for t in a.pop]
sfx += [{'file': S + 'click.wav', 'at': t, 'gain_db': -15} for t in a.click]
f = {'video': a.video, 'out': a.final, 'crf': a.crf, 'preset': 'slow', 'sfx': sfx, 'loudness': -14}
if a.card: f['broll'] = [{'file': a.card, 'at': a.card_at, 'mode': 'overlay', 'x': 0, 'y': a.card_y, 'fade': 0}]
if a.captions: f.update(captions=a.captions, fontsdir=a.fontsdir)
if a.music: f['music'] = {'file': a.music, 'gain_db': -21, 'duck': True, 'fade_in': 1.0, 'fade_out': 2.0}
json.dump(f, open(a.out, 'w'), indent=1); print(f'{len(sfx)} sfx -> {a.out}')
