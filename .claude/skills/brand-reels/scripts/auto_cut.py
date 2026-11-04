"""Tight talking-head cut from word timestamps, with steady framing and a few emphasis zooms chosen by phrase.

usage: python3 auto_cut.py <words.json> <edit.json> --source <video> [--video-json video.json]
         [--gap 0.45] [--pad-in 0.10] [--pad-out 0.24] [--base 1.08] [--focus 0.52,0.33]
         [--push "never teach a man"] [--punch "no man is too busy"] [--snap "is who he really is"] [--print]

Every pause longer than --gap becomes a cut. Each kept segment starts --pad-in before its first word and ends
--pad-out after its last (never past the next segment's start), so cuts land on the breath, not mid-word.
All segments sit on one base framing (--base, default 1.0 = the source framing: any zoom above 1.0 upscales
the picture and softens it, so the base stays at 1.0 and only the emphasis lines zoom). Emphasis is opt-in:
  --push  "phrase"  slow push-in across that segment (base -> base+0.07)            hook, key lesson, payoff
  --punch "phrase"  the whole segment one step tighter (base+0.06), back after it   punchline, CTA
  --snap  "phrase"  a fast punch-in on the segment's first word (+0.08 in 0.3 s)    once per video, the strongest line
Each option can repeat. A phrase matches the first segment whose text contains it (case-insensitive).
Rules of thumb: 2-4 emphasis segments per minute of video, at most one or two snaps, never two in a row.
The focus point (face) comes from analyze.py's video.json; pass --focus to override (x,y normalised; y a bit
below the face centre keeps the chest in frame for captions and cards).
"""
import argparse, json, pathlib, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('words'); ap.add_argument('edit'); ap.add_argument('--source', required=True)
    ap.add_argument('--video-json'); ap.add_argument('--gap', type=float, default=0.45)
    ap.add_argument('--pad-in', type=float, default=0.10); ap.add_argument('--pad-out', type=float, default=0.24)
    ap.add_argument('--base', type=float, default=1.0); ap.add_argument('--focus')
    ap.add_argument('--W', type=int, default=1080); ap.add_argument('--H', type=int, default=1920); ap.add_argument('--fps', default='25/1')
    for k in ('push', 'punch', 'snap'): ap.add_argument('--' + k, action='append', default=[])
    ap.add_argument('--print', action='store_true')
    a = ap.parse_args()

    words = json.load(open(a.words, encoding='utf-8'))
    groups, cur = [], None
    for w in words:
        if cur and w['s'] - cur['e'] <= a.gap:
            cur['e'] = w['e']; cur['t'].append(w['w'])
        else:
            if cur: groups.append(cur)
            cur = {'s': w['s'], 'e': w['e'], 't': [w['w']]}
    if cur: groups.append(cur)

    end = max(w['e'] for w in words) + 1.0
    if a.video_json and pathlib.Path(a.video_json).exists():
        vj = json.load(open(a.video_json)); end = vj.get('duration', end)
    segs = []
    for i, g in enumerate(groups):
        s_in = max(0.0, g['s'] - a.pad_in); s_out = g['e'] + a.pad_out
        if i + 1 < len(groups): s_out = min(s_out, groups[i + 1]['s'] - 0.08)
        if segs: s_in = max(s_in, segs[-1]['out'])
        segs.append({'in': round(s_in, 2), 'out': round(min(s_out, end - 0.02), 2), 'zoom': a.base, 'text': ' '.join(g['t'])})

    def find(p):
        p = p.lower()
        for i, s in enumerate(segs):
            if p in s['text'].lower(): return i
        sys.exit(f'phrase not found in any segment: "{p}"')
    for p in a.push: segs[find(p)]['zoom_end'] = round(a.base + 0.07, 3)
    for p in a.punch: segs[find(p)]['zoom'] = round(a.base + 0.06, 3)
    for p in a.snap: segs[find(p)].update(zoom_end=round(a.base + 0.08, 3), zoom_dur=0.3, ease='out')

    if a.focus: focus = [float(x) for x in a.focus.split(',')]
    elif a.video_json and pathlib.Path(a.video_json).exists():
        fx, fy = json.load(open(a.video_json)).get('focus', [0.5, 0.3]); focus = [fx, round(fy + 0.045, 3)]
    else: focus = [0.5, 0.33]
    edit = {'source': a.source, 'words': a.words, 'output': {'W': a.W, 'H': a.H, 'fps': a.fps}, 'focus': focus, 'segments': segs}
    json.dump(edit, open(a.edit, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    kept = sum(s['out'] - s['in'] for s in segs)
    if a.print:
        for i, s in enumerate(segs):
            z = f"{s['zoom']}" + (f"->{s['zoom_end']}" if 'zoom_end' in s else '') + (' snap' if 'zoom_dur' in s else '')
            print(f"{i:2d} {s['in']:6.2f}-{s['out']:6.2f} [{z}] {s['text']}")
    print(f'{len(segs)} segments, {kept:.1f}s kept of {end:.1f}s, focus {focus} -> {a.edit}')

if __name__ == '__main__':
    main()
