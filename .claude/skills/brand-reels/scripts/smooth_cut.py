"""Render a cut with smooth joins: optical-flow morph between takes, speed ramps inside a take, audio crossfades.

usage: python3 smooth_cut.py cut.json <outdir> [--preview]

cut.json:
{
  "source": "motion/v15/raw.mov", "W": 1920, "H": 1080, "fps": 30,
  "segments": [{"in": 93.55, "out": 98.417, "name": "hook"}, {"in": 218.933, "out": 226.34}, ...],
  "joins": [                                   # one per pair of neighbouring segments
    {"type": "morph", "frames": 10},           # different takes: flow-warped dissolve centred on the cut
    {"type": "ramp", "pre": 0.35, "post": 0.48},  # same take, pause removed: the window [out-pre, in+post]
                                               # is played faster with an eased speed curve, no jump at all
    {"type": "cut"},                           # hard cut (hidden by a flash, a card flip... in the compositor)
    {"type": "morph", "frames": 8, "xa": 0, "xb": 0.05}   # audio: A may run xa s past its out, B starts xb s
  ],                                           # before its in (defaults xf/2 each, crossfade xf=0.06)
  "audio": {"xf": 0.06},
  "focus": [0.5, 0.42],                         # optional: zoom centre (normalised), per segment "focus" too
  "words": "motion/v16/words.json"              # optional: write words_edited.json (+ .txt) on the new timeline
}
Segments may zoom like render_cut.py: "zoom" 1.06, "zoom_end" 1.13, "zoom_dur" 0.3, "ease" "out" (push / punch / snap).
A morph across a zoom change turns it into a smooth push or pull.
Every join keeps the timeline of a plain cut: segment i lasts round((out-in)*fps) frames, so cut times are exact.
Joins happen in pauses: pick out/in in silence (see lessons.md) and, between takes, at the best-matching poses.
Writes <outdir>/rough.mp4 (x264 crf 10, near-lossless) and timeline.json (segments with start/end, joins) which
src2out() / out2src() below read to move word and effect times between the source and the new cut.
"""
import argparse, json, subprocess, pathlib, numpy as np, cv2

def smooth(u): u = min(max(u, 0.0), 1.0); return u * u * (3 - 2 * u)

def zoom_at(seg, tau):
    """zoom of a segment at local time tau (same curve as render_cut.py: smoothstep, or cubic out with ease 'out')."""
    z0 = float(seg.get('zoom', 1.0)); z1 = float(seg.get('zoom_end', z0))
    if abs(z1 - z0) < 1e-6: return z0
    D = seg['out'] - seg['in']; T = min(seg.get('zoom_dur') or D, D); p = min(max(tau / T, 0.0), 1.0)
    e = 1 - (1 - p) ** 3 if seg.get('ease') == 'out' else smooth(p)
    return z0 + (z1 - z0) * e

def apply_zoom(img, z, fx, fy):
    if abs(z - 1) < 1e-4: return img
    H, W = img.shape[:2]
    cx = min(max(fx * W, W / (2 * z)), W - W / (2 * z)); cy = min(max(fy * H, H / (2 * z)), H - H / (2 * z))
    M = np.float32([[z, 0, W / 2 - z * cx], [0, z, H / 2 - z * cy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)

class Reader:
    """sequential reader of one source range at the source frame rate, W x H rgb24; get(t) moves forward only."""
    def __init__(self, src, t0, t1, W, H, rate=60):
        self.t0, self.rate, self.W, self.H, self.k, self.cur = t0, rate, W, H, -1, None
        self.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-ss', f'{t0:.4f}', '-i', src, '-t', f'{t1 - t0:.4f}', '-an',
                                   '-vf', f'fps={rate},scale={W}:{H}:flags=lanczos,format=rgb24', '-f', 'rawvideo', '-'],
                                  stdout=subprocess.PIPE, bufsize=W * H * 3 * 4)
    def get(self, t):
        want = max(0, int(round((t - self.t0) * self.rate)))
        while self.k < want:
            buf = self.p.stdout.read(self.W * self.H * 3)
            if len(buf) < self.W * self.H * 3: break        # past the end: hold the last frame
            self.cur = np.frombuffer(buf, np.uint8).reshape(self.H, self.W, 3); self.k += 1
        return self.cur
    def close(self):
        self.p.stdout.close(); self.p.kill()

class Morph:
    """flow-warped dissolve. Hands and arms (MediaPipe hand landmarks + the 'body skin' class of the selfie multiclass
    segmenter) are kept out of the flow: their flow is filled in from the body around them, so they cross-dissolve
    instead of smearing into streaks across the shirt."""
    def __init__(self, W, H, hand_model='motion/inputs/hand.task', seg_model='motion/inputs/selfie.tflite'):
        self.W, self.H = W, H
        self.dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        self.gx, self.gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        self.hl = self.seg = None
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import vision, BaseOptions
            self.mp = mp
            if pathlib.Path(hand_model).exists():
                self.hl = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=hand_model), num_hands=2, min_hand_detection_confidence=0.3))
            if pathlib.Path(seg_model).exists():
                self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
                    base_options=BaseOptions(model_asset_path=seg_model), output_confidence_masks=True))
        except ImportError:
            print('mediapipe missing: hands are not protected in morphs')
    def hands(self, img):
        """mask (half size) of hands and arms: landmark hulls + the segmenter's body-skin class (not the face)."""
        w, h = self.W // 2, self.H // 2; small = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
        m = np.zeros((h, w), np.uint8)
        if self.hl is not None:
            r = self.hl.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(small)))
            for lm in r.hand_landmarks:
                P = np.array([[p.x * w, p.y * h] for p in lm], np.float32)
                fore = P[0] - (P[9] - P[0]) * 1.2                      # reach down the forearm
                cv2.fillConvexPoly(m, cv2.convexHull(np.vstack([P, fore[None]]).astype(np.int32)), 255)
        if self.seg is not None:
            S = max(w, h); pad = np.zeros((S, S, 3), np.uint8); oy, ox = (S - h) // 2, (S - w) // 2
            pad[oy:oy + h, ox:ox + w] = small                                              # landscape or portrait
            r = self.seg.segment(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=pad))
            skin = cv2.resize(r.confidence_masks[2].numpy_view(), (S, S))[oy:oy + h, ox:ox + w]   # 2 = body skin
            face = cv2.resize(r.confidence_masks[3].numpy_view(), (S, S))[oy:oy + h, ox:ox + w]   # 3 = face skin
            fy = np.where((face > 0.5).any(1))[0]
            if len(fy): skin[:min(h, fy.max() + int(h * 0.12))] = 0                      # keep neck and chin morphing
            m = np.maximum(m, (skin > 0.35).astype(np.uint8) * 255)
        return cv2.dilate(m, np.ones((31, 31), np.uint8))
    def flow(self, a, b, M):
        s = (self.W // 2, self.H // 2)
        g = lambda x: cv2.cvtColor(cv2.resize(x, s, interpolation=cv2.INTER_AREA), cv2.COLOR_RGB2GRAY)
        f = self.dis.calc(g(a), g(b), None)
        k = (1 - M)[..., None]                                           # normalised convolution fills the hands
        fill = cv2.GaussianBlur(f * k, (0, 0), 25) / np.maximum(cv2.GaussianBlur(k[..., 0], (0, 0), 25), 1e-3)[..., None]
        return cv2.resize(f * k + fill * (1 - k), (self.W, self.H)) * 2
    def warp(self, img, f):
        return cv2.remap(img, self.gx + f[..., 0], self.gy + f[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    def __call__(self, a, b, t):
        """frame between a (t=0) and b (t=1): both warped toward time t along the flow (Super-SloMo approximation)."""
        M = cv2.GaussianBlur(np.maximum(self.hands(a), self.hands(b)).astype(np.float32) / 255, (0, 0), 6)
        f01, f10 = self.flow(a, b, M), self.flow(b, a, M)
        ft0 = -(1 - t) * t * f01 + t * t * f10; ft1 = (1 - t) * (1 - t) * f01 - t * (1 - t) * f10
        o = (1 - t) * self.warp(a.astype(np.float32), ft0) + t * self.warp(b.astype(np.float32), ft1)
        return np.clip(o + 0.5, 0, 255).astype(np.uint8)

def plan(cut):
    """per output frame: what to show. Returns segments with start/end frames and a frame list."""
    fps = cut['fps']; segs = cut['segments']; joins = cut.get('joins', [{'type': 'cut'}] * (len(segs) - 1))
    n0 = 0
    for s in segs:
        s['N'] = int(round((s['out'] - s['in']) * fps)); s['n0'] = n0; n0 += s['N']
    total = n0
    frames = []                                          # (kind, seg, src_t[, seg2, src_t2, alpha])
    for i, s in enumerate(segs):
        for n in range(s['n0'], s['n0'] + s['N']):
            frames.append(['seg', i, s['in'] + (n - s['n0']) / fps])
    for j, J in enumerate(joins):
        A, B = segs[j], segs[j + 1]; C = B['n0']; tC = C / fps
        if J['type'] == 'morph':
            N = J.get('frames', 10)
            for k in range(N):
                n = C - N // 2 + k; dt = (n - C) / fps
                frames[n] = ['morph', j, A['out'] + dt, j + 1, B['in'] + dt, smooth((k + 0.5) / N)]
        elif J['type'] == 'ramp':
            pre, post = J['pre'], J['post']; g = B['in'] - A['out']; L = pre + post
            w0 = A['out'] - pre
            for n in range(int(round((tC - pre) * fps)), int(round((tC + post) * fps))):
                u = n / fps - (tC - pre)
                st = w0 + u + g * smooth(u / L)
                frames[n] = ['seg', j if st <= A['out'] + 0.5 else j + 1, st]
    return segs, joins, frames, total

def render_audio(cut, segs, joins, total, out_wav):
    fps = cut['fps']; SR = 48000; xf_def = cut.get('audio', {}).get('xf', 0.06)
    T = total / fps; buf = np.zeros((int(T * SR) + SR, 2), np.float32)
    for i, s in enumerate(segs):
        tS, tE = s['n0'] / fps, (s['n0'] + s['N']) / fps
        Jin = joins[i - 1] if i > 0 else None; Jout = joins[i] if i < len(joins) else None
        xfi = Jin.get('xf', xf_def) if Jin else 0.004; xfo = Jout.get('xf', xf_def) if Jout else 0.004
        xb = Jin.get('xb', xfi / 2) if Jin else 0.0       # B runs this far before its in
        xa = Jout.get('xa', xfo / 2) if Jout else 0.0     # A runs this far past its out
        a0, a1 = s['in'] - xb, s['out'] + xa
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{a0:.4f}', '-i', cut['source'], '-t', f'{a1 - a0:.4f}', '-vn',
                              '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
        x = np.frombuffer(raw, np.float32).reshape(-1, 2).copy()
        n = len(x); env = np.ones(n, np.float32); m_in = int(xfi * SR); m_out = int(xfo * SR)
        if m_in: env[:m_in] *= np.sin(np.linspace(0, np.pi / 2, m_in))
        if m_out: env[-m_out:] *= np.cos(np.linspace(0, np.pi / 2, m_out))
        p = int(round((tS - xb) * SR)); buf[max(0, p):p + n] += (x * env[:, None])[max(0, -p):]
    buf = buf[:int(T * SR)]
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-c:a', 'pcm_s16le', out_wav],
                   input=buf.tobytes(), check=True)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cut'); ap.add_argument('outdir'); ap.add_argument('--preview', action='store_true')
    a = ap.parse_args(); cut = json.load(open(a.cut)); out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    W, H, fps, src = cut.get('W', 1920), cut.get('H', 1080), cut['fps'], cut['source']
    segs, joins, frames, total = plan(cut)
    render_audio(cut, segs, joins, total, str(out / 'rough_audio.wav'))
    morph = Morph(W, H, cut.get('hand_model', 'motion/inputs/hand.task'), cut.get('seg_model', 'motion/inputs/selfie.tflite')); readers = {}
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', src],
                       capture_output=True, text=True).stdout.strip().split('/')
    rate = max(float(r[0]) / float(r[1] if len(r) > 1 else 1), fps)
    def reader(i):
        if i not in readers:
            s = segs[i]; readers[i] = Reader(src, s['in'] - 0.7, s['out'] + 1.0, W, H, rate)
        return readers[i]
    fdef = cut.get('focus', [0.5, 0.5])
    def framed(i, t):
        s = segs[i]; fx, fy = s.get('focus', fdef)
        return apply_zoom(reader(i).get(t), zoom_at(s, t - s['in']), fx, fy)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fps), '-i', '-',
                            '-i', str(out / 'rough_audio.wav'), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264',
                            '-preset', 'ultrafast' if a.preview else 'medium', '-crf', '20' if a.preview else '10',
                            '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', str(out / 'rough.mp4')], stdin=subprocess.PIPE)
    for n, f in enumerate(frames):
        if f[0] == 'seg':
            img = framed(f[1], f[2])
        else:
            _, i, ta, j, tb, al = f
            img = morph(framed(i, ta), framed(j, tb), al)
        for k in [k for k in readers if k < (f[1] - 1)]:      # close readers we are done with
            readers.pop(k).close()
        enc.stdin.write(np.ascontiguousarray(img).tobytes())
        if n % 300 == 0: print('frame', n, '/', total, flush=True)
    enc.stdin.close(); enc.wait()
    for r in readers.values(): r.close()
    import gc; morph.hl = morph.seg = None; gc.collect()   # release MediaPipe tasks now, not at interpreter exit (noisy)
    tl = {'source': src, 'W': W, 'H': H, 'fps': fps, 'duration': total / fps, 'joins': joins,
          'segments': [{'i': i, 'name': s.get('name', ''), 'in': s['in'], 'out': s['in'] + s['N'] / fps,
                        'start': s['n0'] / fps, 'end': (s['n0'] + s['N']) / fps} for i, s in enumerate(segs)]}
    json.dump(tl, open(out / 'timeline.json', 'w'), indent=1)
    if cut.get('words'): remap_words(cut['words'], tl, out)
    print('rough.mp4', total, 'frames', round(total / fps, 3), 's')

def remap_words(wpath, tl, out):
    """words.json (source times) -> words_edited.json / .txt on the cut, like render_cut.py (by largest overlap)."""
    new = []
    for w in json.load(open(wpath, encoding='utf-8')):
        ov = lambda x: min(w['e'], x['out']) - max(w['s'], x['in'])
        seg = max(tl['segments'], key=ov)
        if ov(seg) < min(0.06, (w['e'] - w['s']) / 2): continue
        f = lambda t: seg['start'] + min(max(t, seg['in']), seg['out']) - seg['in']
        new.append({**w, 's': round(f(w['s']), 3), 'e': round(f(w['e']), 3)})
    new.sort(key=lambda w: w['s'])
    json.dump(new, open(out / 'words_edited.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    lines, cur = [], []
    for k, w in enumerate(new):
        if cur and w['s'] - new[k - 1]['e'] > 0.5: lines.append(' '.join(cur)); cur = []
        cur.append(f"{w['s']:.2f}:{w['w']}")
    if cur: lines.append(' '.join(cur))
    (out / 'words_edited.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(len(new), 'words ->', out / 'words_edited.json')

def src2out(tl, s):
    """source time -> output time (nearest segment if s falls in a removed part)."""
    best = None
    for g in tl['segments']:
        if g['in'] - 1e-6 <= s <= g['out'] + 1e-6: return g['start'] + (s - g['in'])
        d = min(abs(s - g['in']), abs(s - g['out']))
        if best is None or d < best[0]: best = (d, g['start'] if abs(s - g['in']) < abs(s - g['out']) else g['end'])
    return best[1]

def out2src(tl, t):
    for g in tl['segments']:
        if g['start'] - 1e-6 <= t < g['end'] + 1e-6: return g['in'] + (t - g['start'])
    return tl['segments'][-1]['out']

if __name__ == '__main__':
    main()
