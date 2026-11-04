"""Render the cut: segments of the source, reframed and zoomed, joined with cuts or transitions.

usage: python3 render_cut.py edit.json <outdir> [--fast] [--jobs 2]

edit.json:
{
  "source": "motion/work/source.mp4",
  "output": {"W": 1080, "H": 1920, "fps": "30/1"},     # optional; defaults to the source. Another aspect = reframe
  "focus": [0.5, 0.42],                                 # default point to keep in frame (normalised source coords)
  "segments": [
    {"in": 1.20, "out": 5.80, "zoom": 1.0},
    {"in": 6.10, "out": 9.00, "zoom": 1.12, "zoom_end": 1.18},            # slow push-in across the segment
    {"in": 9.40, "out": 12.0, "zoom": 1.0, "zoom_end": 1.25, "zoom_dur": 0.25, "ease": "out"},  # snap zoom on a word
    {"in": 14.0, "out": 20.0, "zoom": 1.0, "focus": [0.4, 0.4], "transition": {"type": "fade", "dur": 0.4}}
  ]
}
transition (into this segment): cut (default) | fade | dip (to black) | flash (white) | whip | zoom | slideleft |
  slideright | smoothleft | smoothright | circleopen | dissolve | any ffmpeg xfade name.

Writes <outdir>/rough.mp4, timeline.json (source -> output times) and, if words.json sits next to the
edit file or is given in edit["words"], words_edited.json (+ words_edited.txt for motion-broll) with times on the new timeline.
"""
import argparse, sys, pathlib, concurrent.futures as cf, fractions
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import run, probe, load, save

ALIAS = {'dip': ('fadeblack', 0.5), 'flash': ('fadewhite', 0.3), 'whip': ('smoothleft', 0.18),
         'zoom': ('zoomin', 0.35), 'fade': ('fade', 0.3)}

def zoom_expr(z0, z1, D, zdur, ease):
    if abs(z1 - z0) < 1e-4: return f'{z0:.5f}', False
    T = min(zdur or D, D)
    p = f'clip(t/{T:.4f},0,1)'
    e = f'(1-pow(1-{p},3))' if ease == 'out' else f'({p}*{p}*(3-2*{p}))'
    return f'({z0:.5f}+{z1 - z0:.5f}*{e})', True

def seg_cmd(src, info, out, seg, i, dst, fast):
    fps = fractions.Fraction(out['fps']); SW, SH, W, H = info['W'], info['H'], out['W'], out['H']
    D_raw = seg['out'] - seg['in']; N = max(1, round(D_raw * fps)); D = float(N / fps)
    s0 = max(W / SW, H / SH)
    fx, fy = seg.get('focus', out['focus'])
    z0 = float(seg.get('zoom', 1.0)); z1 = float(seg.get('zoom_end', z0))
    Z, anim = zoom_expr(z0, z1, D, seg.get('zoom_dur'), seg.get('ease', 'inout'))
    sw, sh = f'({SW * s0:.4f}*{Z})', f'({SH * s0:.4f}*{Z})'
    vf = (f"setpts=PTS-STARTPTS,fps={out['fps']}:start_time=0,setpts=PTS-STARTPTS,scale=w='trunc({sw}/2)*2':h='trunc({sh}/2)*2':eval={'frame' if anim else 'init'}:flags=lanczos,"
          f"crop={W}:{H}:x='clip({fx}*{sw}-{W}/2,0,{sw}-{W}-2)':y='clip({fy}*{sh}-{H}/2,0,{sh}-{H}-2)',setsar=1,format=yuv420p")
    fade = 0.012
    af = f'asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d={fade},atrim=0:{D:.6f},apad=whole_dur={D:.6f},afade=t=out:st={D - fade:.6f}:d={fade}'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-ss', f"{seg['in']:.4f}", '-t', f'{D + 0.5:.4f}', '-i', src]
    if not info['has_audio']:
        cmd += ['-f', 'lavfi', '-t', f'{D:.4f}', '-i', 'anullsrc=r=48000:cl=stereo']
    cmd += ['-map', '0:v:0', '-map', '0:a:0' if info['has_audio'] else '1:a:0', '-vf', vf, '-af', af,
            '-frames:v', str(N), '-c:v', 'libx264', '-preset', 'ultrafast' if fast else 'veryfast', '-crf', '22' if fast else '8',
            '-c:a', 'pcm_s16le', '-ac', '2', str(dst)]
    return cmd, D

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('edit'); ap.add_argument('outdir')
    ap.add_argument('--fast', action='store_true'); ap.add_argument('--jobs', type=int, default=2)
    a = ap.parse_args()
    ed = load(a.edit); outdir = pathlib.Path(a.outdir); tmp = outdir / 'segments'; tmp.mkdir(parents=True, exist_ok=True)
    src = ed['source']; info = probe(src)
    out = {'W': info['W'], 'H': info['H'], 'fps': info['fps_str'], **ed.get('output', {})}
    out['W'] -= out['W'] % 2; out['H'] -= out['H'] % 2
    out['focus'] = ed.get('focus', [0.5, 0.42])
    segs = ed['segments']
    jobs = []
    for i, s in enumerate(segs):
        cmd, D = seg_cmd(src, info, out, s, i, tmp / f'{i:04d}.mkv', a.fast); s['_D'] = D; jobs.append(cmd)
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        list(ex.map(run, jobs))

    # join: runs of hard cuts are concatenated, runs are joined with xfade/acrossfade
    groups = [[0]]
    for i in range(1, len(segs)):
        t = segs[i].get('transition', {}).get('type', 'cut')
        (groups[-1].append(i) if t == 'cut' else groups.append([i]))
    fc, ins = [], []
    for i in range(len(segs)): ins += ['-i', str(tmp / f'{i:04d}.mkv')]
    for g, idx in enumerate(groups):
        pads = ''.join(f'[{i}:v][{i}:a]' for i in idx)
        fc.append(f'{pads}concat=n={len(idx)}:v=1:a=1[g{g}v0][g{g}a];[g{g}v0]settb=AVTB[g{g}v]')
    cur_v, cur_a = '[g0v]', '[g0a]'
    timeline = []; t_out = 0.0; gdur = 0.0
    for g, idx in enumerate(groups):
        ov = 0.0
        if g > 0:
            tr = segs[idx[0]]['transition']; name, dflt = ALIAS.get(tr['type'], (tr['type'], 0.3))
            d = float(tr.get('dur', dflt)); d = min(d, segs[idx[0]]['_D'] / 2, segs[groups[g - 1][-1]]['_D'] / 2)
            fc.append(f'{cur_v}[g{g}v]xfade=transition={name}:duration={d:.4f}:offset={gdur - d:.4f}[x{g}v];'
                      f'{cur_a}[g{g}a]acrossfade=d={d:.4f}:c1=tri:c2=tri[x{g}a]')
            cur_v, cur_a = f'[x{g}v]', f'[x{g}a]'; ov = d
            t_out = gdur - d
        for k, i in enumerate(idx):
            s = segs[i]
            timeline.append({'i': i, 'in': s['in'], 'out': round(s['in'] + s['_D'], 4), 'start': round(t_out, 4),
                             'end': round(t_out + s['_D'], 4), 'transition_in': ov if k == 0 else 0})
            t_out += s['_D']
        gdur = t_out
    rough = outdir / 'rough.mp4'
    run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', ';'.join(fc), '-map', cur_v, '-map', cur_a,
         '-c:v', 'libx264', '-preset', 'ultrafast' if a.fast else 'medium', '-crf', '23' if a.fast else '10', '-pix_fmt', 'yuv420p',
         '-r', out['fps'], '-c:a', 'aac', '-b:a', '256k', '-movflags', '+faststart', str(rough)])
    save(outdir / 'timeline.json', {'source': src, 'W': out['W'], 'H': out['H'], 'fps': out['fps'], 'duration': round(gdur, 4), 'segments': timeline})

    wpath = ed.get('words') or str(pathlib.Path(a.edit).with_name('words.json'))
    if pathlib.Path(wpath).exists():
        new = []
        for w in load(wpath):
            # the segment the word overlaps most: Whisper often stretches a word across a pause that was cut,
            # so its midpoint can fall in the gap even though the word is heard in the kept audio
            ov = lambda x: min(w['e'], x['out']) - max(w['s'], x['in'])
            seg = max(timeline, key=ov, default=None)
            if not seg or ov(seg) < min(0.06, (w['e'] - w['s']) / 2): continue
            f = lambda t: seg['start'] + min(max(t, seg['in']), seg['out']) - seg['in']
            new.append({**w, 's': round(f(w['s']), 3), 'e': round(f(w['e']), 3)})
        new.sort(key=lambda w: w['s'])  # segments may be reordered (cold open)
        save(outdir / 'words_edited.json', new)
        # motion-broll's words.txt format: one line per phrase, "time:word" pairs
        lines, cur = [], []
        for k, w in enumerate(new):
            if cur and w['s'] - new[k - 1]['e'] > 0.5: lines.append(' '.join(cur)); cur = []
            cur.append(f"{w['s']:.2f}:{w['w']}")
        if cur: lines.append(' '.join(cur))
        (outdir / 'words_edited.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'{len(new)} words remapped -> {outdir}/words_edited.json')
    print(f'rough cut: {len(segs)} segments, {len(groups) - 1} transitions, {gdur:.2f}s -> {rough}')

if __name__ == '__main__':
    main()
