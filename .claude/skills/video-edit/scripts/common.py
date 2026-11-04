"""Shared helpers for the video-edit scripts."""
import json, subprocess, re, pathlib, fractions

def run(cmd, quiet=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(map(str, cmd))[:400]}\n{r.stderr[-3000:]}")
    return r

def probe(path):
    """Resolution (after rotation), fps as a string and float, duration, audio presence."""
    r = run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', str(path)])
    j = json.loads(r.stdout)
    v = next(s for s in j['streams'] if s['codec_type'] == 'video')
    W, H = int(v['width']), int(v['height'])
    rot = 0
    for sd in v.get('side_data_list', []) or []:
        if 'rotation' in sd: rot = int(float(sd['rotation']))
    if 'rotate' in v.get('tags', {}): rot = int(v['tags']['rotate'])
    if abs(rot) % 180 == 90: W, H = H, W
    fr = v.get('avg_frame_rate') or v.get('r_frame_rate') or '30/1'
    if fr in ('0/0', '0/1'): fr = v.get('r_frame_rate', '30/1')
    fps = float(fractions.Fraction(fr))
    # Snap near-standard rates (29.97 variable phone footage etc.) to their exact fraction.
    for std, s in [(23.976, '24000/1001'), (24, '24/1'), (25, '25/1'), (29.97, '30000/1001'), (30, '30/1'),
                   (50, '50/1'), (59.94, '60000/1001'), (60, '60/1')]:
        if abs(fps - std) < 0.05: fr, fps = s, float(fractions.Fraction(s)); break
    dur = float(j['format'].get('duration') or v.get('duration') or 0)
    has_audio = any(s['codec_type'] == 'audio' for s in j['streams'])
    return dict(W=W, H=H, fps=fps, fps_str=fr, duration=dur, has_audio=has_audio)

def load(p):
    return json.load(open(p, encoding='utf-8'))

def save(p, obj):
    pathlib.Path(p).parent.mkdir(parents=True, exist_ok=True)
    json.dump(obj, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def norm_word(w):
    """Lower-case, no punctuation, no niqqud: for comparing words and finding repeats."""
    w = re.sub('[֑-ׇ]', '', w)
    return re.sub(r'[^\w%₪$]', '', w.lower())

def fmt(t):
    m, s = divmod(max(0.0, t), 60); return f'{int(m):02d}:{s:05.2f}'
