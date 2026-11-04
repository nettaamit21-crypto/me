"""Analyse raw footage + words.json and draft a rough cut.

usage: python3 analyze.py <video> <words.json> <outdir> [--max-gap 0.35] [--pad-in 0.06] [--pad-out 0.12]
                          [--punch 1.0] [--out-W 1080 --out-H 1920]

Writes to <outdir>:
  video.json       resolution, fps, duration, face focus point, silences
  transcript.md    numbered sentences with timestamps, pauses, [filler] marks and RETAKE? flags — read this
  edit_draft.json  a first cut in the edit.json schema: pauses and isolated fillers removed, steady framing (--punch >1 alternates a framing change on every cut; rarely wanted)
  contact.png      12 frames of the footage
"""
import argparse, re, sys, pathlib, statistics
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from common import run, probe, load, save, norm_word, fmt

FILLERS = {'אה', 'אהה', 'אההה', 'אמ', 'אממ', 'אםם', 'ממ', 'הממ', 'אמממ', 'אהם', 'uh', 'um', 'uhm', 'eh', 'hmm', 'erm'}
SOFT_FILLERS = {'כאילו', 'בעצם', 'יעני', 'סתם', 'נגיד', 'like'}

def silences(video, noise='-34dB', d=0.30):
    r = run(['ffmpeg', '-hide_banner', '-i', video, '-vn', '-af', f'silencedetect=noise={noise}:d={d}', '-f', 'null', '-'])
    out, s = [], None
    for line in r.stderr.splitlines():
        m = re.search(r'silence_start: ([\d.]+)', line)
        if m: s = float(m.group(1))
        m = re.search(r'silence_end: ([\d.]+)', line)
        if m and s is not None: out.append([round(s, 3), round(float(m.group(1)), 3)]); s = None
    return out

def face_focus(video, info, n=24):
    """Median face centre (normalised) from n sampled frames, with OpenCV's frontal-face Haar cascade."""
    try:
        import cv2
    except ImportError:
        return None, []
    if not hasattr(cv2, 'CascadeClassifier'):  # OpenCV 5 moved Haar cascades out; setup pins opencv-python-headless<5
        return None, []
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(video); pts = []
    for i in range(n):
        t = info['duration'] * (i + 0.5) / n
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read()
        if not ok: continue
        h, w = fr.shape[:2]
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        faces = cas.detectMultiScale(g, 1.1, 6, minSize=(int(min(w, h) * 0.08),) * 2)
        if len(faces):
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            pts.append({'t': round(t, 2), 'cx': round(float((x + fw / 2) / w), 3), 'cy': round(float((y + fh / 2) / h), 3), 'size': round(float(fh / h), 3)})
    cap.release()
    if not pts: return None, []
    return [round(float(statistics.median(p['cx'] for p in pts)), 3), round(float(statistics.median(p['cy'] for p in pts)), 3)], pts

def sentences(words, gap=0.6):
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and (w['s'] - words[i - 1]['e'] > gap or re.search(r'[.!?]$', words[i - 1]['w'])):
            out.append(cur); cur = []
        cur.append(i)
    if cur: out.append(cur)
    return out

def retakes(words, sents, window=30.0):
    """Sentence pairs that start with the same 3 words within `window` seconds: the earlier one is probably a false start."""
    flags = {}
    key = lambda s: ' '.join(norm_word(words[i]['w']) for i in s[:3])
    for a in range(len(sents)):
        ka = key(sents[a])
        if len(sents[a]) < 2 or not ka.strip(): continue
        for b in range(a + 1, len(sents)):
            if words[sents[b][0]]['s'] - words[sents[a][-1]]['e'] > window: break
            if key(sents[b]) == ka:
                flags[a] = b; break
    return flags

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('words'); ap.add_argument('outdir')
    ap.add_argument('--max-gap', type=float, default=0.35); ap.add_argument('--pad-in', type=float, default=0.06)
    ap.add_argument('--pad-out', type=float, default=0.12); ap.add_argument('--punch', type=float, default=1.0)
    ap.add_argument('--out-W', type=int); ap.add_argument('--out-H', type=int)
    a = ap.parse_args()
    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    info = probe(a.video)
    words = load(a.words)
    sil = silences(a.video) if info['has_audio'] else []
    # Whisper often starts a word that follows a pause too early (inside the silence). Snap such starts to the
    # measured end of the silence, and write the corrected times back so cuts and captions use them.
    snapped = 0
    for w in words:
        for s0, s1 in sil:
            if s0 + 0.05 < w['s'] < s1 - 0.03 and w['e'] > s1:
                w['s'] = round(s1, 3); snapped += 1; break
            # A short word that starts just before the pause and is stretched across it ("she … didn't") is
            # really spoken after the pause: Whisper hangs the next sentence's first word on the old one.
            if w['s'] <= s0 + 0.05 and s0 - w['s'] < 0.2 and w['e'] > s1 and (s1 - s0) > 0.5 * (w['e'] - w['s']):
                w['s'] = round(s1, 3); snapped += 1; break
    if snapped:
        save(a.words, words)
    focus, faces = face_focus(a.video, info)
    info.update(silences=sil, focus=focus or [0.5, 0.42], faces=faces, face_found=bool(focus))
    save(out / 'video.json', info)

    # contact sheet
    n = 12; step = max(info['duration'] / n, 0.1)
    run(['ffmpeg', '-v', 'error', '-y', '-i', a.video, '-vf', f"fps=1/{step:.3f},scale=480:-2,tile=4x3", '-frames:v', '1', str(out / 'contact.png')])

    # transcript for reading
    sents = sentences(words); rt = retakes(words, sents)
    filler_idx = {i for i, w in enumerate(words) if norm_word(w['w']) in FILLERS}
    lines = [f"# Transcript — {fmt(info['duration'])} total, {len(words)} words, {len(sents)} sentences\n",
             f"Video {info['W']}x{info['H']} @ {info['fps_str']} fps. Face focus: {info['focus']} ({'detected' if focus else 'not detected, centre assumed'}).",
             "Marks: [filler] removable filler · (~word~) soft filler, keep unless it drags · ⚠ RETAKE? the sentence restarts later · ⟂1.4s pause before\n"]
    for si, s in enumerate(sents):
        pre = words[s[0]]['s'] - words[s[0] - 1]['e'] if s[0] > 0 else words[s[0]]['s']
        toks = []
        for i in s:
            w = words[i]['w']; nw = norm_word(w)
            if i in filler_idx: toks.append(f'[{w}]')
            elif nw in SOFT_FILLERS: toks.append(f'(~{w}~)')
            elif words[i].get('p') is not None and words[i]['p'] < 0.5: toks.append(f'{w}?')
            else: toks.append(w)
        flag = f"  ⚠ RETAKE? restarts at S{rt[si] + 1}" if si in rt else ''
        gap = f' ⟂{pre:.1f}s' if pre > 0.8 else ''
        lines.append(f"S{si + 1} [{fmt(words[s[0]]['s'])}–{fmt(words[s[-1]]['e'])}]{gap} {' '.join(toks)}{flag}")
    (out / 'transcript.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    # draft cut: keep speech, cut pauses longer than max-gap, drop isolated fillers and flagged retakes
    drop = set(filler_idx)
    for si in rt:
        drop.update(sents[si])
    keep = [i for i in range(len(words)) if i not in drop]
    segs, cur = [], None
    for i in keep:
        w = words[i]
        if cur and w['s'] - cur['last_e'] <= a.max_gap and (i - cur['last_i'] == 1):
            cur['last_e'] = w['e']; cur['last_i'] = i
        else:
            if cur: segs.append(cur)
            cur = {'first_s': w['s'], 'last_e': w['e'], 'last_i': i, 'first_i': i}
    if cur: segs.append(cur)
    draft = []
    for k, c in enumerate(segs):
        s_in = max(0.0, c['first_s'] - a.pad_in); s_out = min(info['duration'], c['last_e'] + a.pad_out)
        if draft and s_in < draft[-1]['out']: s_in = draft[-1]['out']
        if s_out - s_in < 0.2: continue
        text = ' '.join(words[i]['w'] for i in range(c['first_i'], c['last_i'] + 1) if i not in drop)
        draft.append({'in': round(s_in, 3), 'out': round(s_out, 3), 'zoom': 1.0, 'text': text})
    # steady framing by default; emphasis zooms are chosen by hand on the key lines (see SKILL.md, zoom rules)
    for k, d in enumerate(draft):
        d['zoom'] = 1.0 if k % 2 == 0 else a.punch
    oW = a.out_W or info['W']; oH = a.out_H or info['H']
    edit = {'source': a.video, 'output': {'W': oW, 'H': oH, 'fps': info['fps_str']}, 'focus': info['focus'],
            'segments': draft}
    save(out / 'edit_draft.json', edit)
    kept = sum(d['out'] - d['in'] for d in draft)
    print(f"{snapped} word starts snapped to silence ends; " if snapped else '', end='')
    print(f"{len(sents)} sentences, {len(filler_idx)} fillers, {len(rt)} possible retakes, {len(sil)} silences; "
          f"face {'at ' + str(focus) if focus else 'not found'}\n"
          f"draft: {len(draft)} segments, {fmt(kept)} of {fmt(info['duration'])} kept -> {out}/edit_draft.json")

if __name__ == '__main__':
    main()
