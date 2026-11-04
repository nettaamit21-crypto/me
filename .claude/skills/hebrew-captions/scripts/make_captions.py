"""Word timestamps -> Hebrew captions: an .ass file to burn in (RTL, active-word highlight) and a plain .srt.

usage: python3 make_captions.py words.json out.ass --W 1080 --H 1920 [--style reels|clean|youtube|extrude|white|soft]
       [--font Heebo|Rubik|NotoSansHebrew] [--accent FFD400] [--max-words 3] [--max-chars 22] [--y 0.72] [--srt out.srt]
       [--fix fixes.json]

words.json: [{"w": "שלום", "s": 1.00, "e": 1.40}, ...]  (times in the video the captions go on)
fixes.json: {"וויספר": "Whisper", "קלוד": "Claude"}  (spelling fixes applied word by word)
"""
import argparse, json, re, pathlib
import uharfbuzz as hb
from fontTools.ttLib import TTFont

FONTS = pathlib.Path(__file__).resolve().parent.parent / 'fonts'
FAMILY = {'NotoSansHebrew': 'Noto Sans Hebrew'}  # file prefix -> font family name, when they differ
HEB = re.compile('[\u0590-\u05FF\uFB1D-\uFB4F]'); LAT = re.compile('[A-Za-z]')

class Measure:
    """Shapes words with HarfBuzz and returns widths in pixels at a libass font size (VSFilter sizing: size = winAscent+winDescent)."""
    def __init__(self, path, size):
        data = open(path, 'rb').read(); self.font = hb.Font(hb.Face(data))
        os2 = TTFont(path)['OS/2']; self.k = size / (os2.usWinAscent + os2.usWinDescent)
    def __call__(self, text):
        buf = hb.Buffer(); buf.add_str(text); buf.guess_segment_properties(); hb.shape(self.font, buf)
        return sum(p.x_advance for p in buf.glyph_positions) * self.k

def direction(w):
    if HEB.search(w): return 'R'
    if LAT.search(w): return 'L'
    return 'N'

def layout_line(ws, widths, space, cx):
    """Visual x-centre for each word of an RTL line: logical order runs right to left, LTR runs (English) keep their inner order."""
    dirs = [direction(w) for w in ws]
    for i, d in enumerate(dirs):  # neutral words (numbers, symbols) join an LTR run only when both sides are LTR
        if d == 'N':
            prev = next((dirs[j] for j in range(i - 1, -1, -1) if dirs[j] != 'N'), 'R')
            nxt = next((dirs[j] for j in range(i + 1, len(dirs)) if dirs[j] != 'N'), 'R')
            dirs[i] = 'L' if prev == nxt == 'L' else 'R'
    runs = []
    for i, d in enumerate(dirs):
        if runs and d == 'L' and runs[-1][0] == 'L': runs[-1][1].append(i)
        else: runs.append((d, [i]))
    total = sum(widths) + space * (len(ws) - 1)
    xs = [0.0] * len(ws); right = cx + total / 2
    for d, idx in runs:
        rw = sum(widths[i] for i in idx) + space * (len(idx) - 1)
        if d == 'L':
            x = right - rw
            for i in idx: xs[i] = x + widths[i] / 2; x += widths[i] + space
        else:
            xs[idx[0]] = right - widths[idx[0]] / 2
        right -= rw + space
    return xs, total

def split_lines(n, widths, space, maxw):
    """One line if it fits, else the most balanced two-line split."""
    tot = sum(widths) + space * (n - 1)
    if tot <= maxw or n < 2: return [list(range(n))]
    best = min(range(1, n), key=lambda k: abs((sum(widths[:k]) + space * (k - 1)) - (sum(widths[k:]) + space * (n - k - 1))))
    return [list(range(best)), list(range(best, n))]

STYLES = {
    # font weight, size as a fraction of frame height, outline, shadow, box, uppercase-ish pop, highlight mode
    'reels':   dict(weight='Black', size=0.052, outline=0.0045, shadow=0.0, box=False, pop=True,  hl='color'),
    'clean':   dict(weight='Bold',  size=0.040, outline=0.0030, shadow=0.0015, box=False, pop=False, hl='color'),
    'youtube': dict(weight='Medium', size=0.042, outline=0.0, shadow=0.0, box=True, pop=False, hl='none'),
    # Instagram-Edits look: heavy oblique letters with a hard grey extrusion shadow, 2 words, centred on the chest.
    'extrude': dict(weight='Black', size=0.053, outline=0.0, shadow=0.0, box=False, pop=False, hl='none', font='NotoSansHebrew',
                    max_words=2, max_chars=16, y=0.60, fax=-0.10, xshad=0.0032, yshad=0.0042, shadow_rgb='6E6E6E'),
    # the user's preferred look: the extrude font, size and placement, plain bright white, no slant, no shadow
    'white': dict(weight='Black', size=0.053, outline=0.0, shadow=0.0, box=False, pop=False, hl='none', font='NotoSansHebrew',
                  max_words=2, max_chars=16, y=0.60),
    # "soft": white Heebo Bold over a soft, blurred dark shadow (reads on light backgrounds), 2-3 words, quick fade.
    # Matched to an Instagram reference the user sent (dana_kalderon); pairs with the keyword callouts in video-edit.
    'soft': dict(weight='Bold', size=0.064, outline=0.0, shadow=0.0, box=False, pop=False, hl='none', font='Heebo',
                 max_words=3, max_chars=18, y=0.58, glow=dict(alpha='70', blur=7, dy=0.0028)),
}
PUNCT_END = re.compile(r'[.,!?;:…]+$')
BIDI = re.compile('[‎‏‪-‮⁦-⁩]')

def ass_time(t):
    t = max(0.0, t); cs = int(round(t * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); s, cs = divmod(cs, 100)
    return f'{h}:{m:02d}:{s:02d}.{cs:02d}'

def srt_time(t):
    ms = int(round(max(0.0, t) * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def bgr(hexrgb):
    h = hexrgb.lstrip('#'); return f'&H00{h[4:6]}{h[2:4]}{h[0:2]}&'.upper()

STICKY = {'של', 'על', 'את', 'עם', 'אל', 'כל', 'לא', 'גם', 'רק', 'זה', 'זו', 'כי', 'אם', 'או', 'מה', 'איך', 'יותר', 'הכי', 'the', 'a', 'to', 'of'}

def sticky(prev, nxt, english=False):
    """True when a caption break between these two words would read badly."""
    p, n = prev['w'], nxt['w']
    if english: return p.lower() in {'a', 'an', 'the', 'to', 'of', 'i'} or bool(re.fullmatch(r'[\d.,%$]+', p))
    if LAT.search(p) and LAT.search(n): return True           # "Claude Code" inside a Hebrew line
    if re.fullmatch(r'[\d.,%₪$]+', p): return True           # "3 כלים", "50% הנחה"
    if p in STICKY or len(p) == 1: return True                # "של הסרטון", "ו", "ה"
    return False

def face_below(video, times, H_out, chest=0.5, lo=0.45, hi=0.80):
    """Caption centre (0..1) under the face at each time: face-box bottom + chest x face height (the top of the chest).
    Uses OpenCV's Haar face detector on the frame of `video` (the video the captions go on). Missing detections are
    filled from neighbours, then lightly smoothed so captions don't jump between groups."""
    import cv2
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(video); ys = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read(); y = None
        if ok:
            h, w = fr.shape[:2]
            f = cas.detectMultiScale(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY), 1.1, 6, minSize=(int(min(w, h) * 0.06),) * 2)
            if len(f):
                x0, y0, fw, fh = max(f, key=lambda r: r[2] * r[3])
                y = min(hi, max(lo, (y0 + fh + chest * fh) / h))
        ys.append(y)
    cap.release()
    known = [y for y in ys if y is not None]
    if not known: return None
    for i, y in enumerate(ys):  # fill gaps from the nearest detection
        if y is None:
            ys[i] = min(((abs(j - i), ys[j]) for j in range(len(ys)) if ys[j] is not None))[1]
    sm = [sorted(ys[max(0, i - 1):i + 2])[len(ys[max(0, i - 1):i + 2]) // 2] for i in range(len(ys))]  # median of 3
    return [round(v, 4) for v in sm]

def group(words, max_words, max_chars, gap=0.45):
    english = sum(bool(LAT.search(w['w'])) for w in words) > len(words) / 2  # an English video: no name rule
    """Split into caption groups: break on sentence ends and pauses, respect word/char limits,
    and avoid breaks that strand a preposition, a number or half of an English name (one word of slack)."""
    groups, cur = [], []
    for w in words:
        if cur:
            chars = sum(len(x['w']) + 1 for x in cur) + len(w['w'])
            pause = w['s'] - cur[-1]['e'] > gap
            full = len(cur) >= max_words or chars > max_chars
            latin_pair = not english and bool(LAT.search(cur[-1]['w']) and LAT.search(w['w']))
            slack = 2 if latin_pair else 1
            soft = len(cur) < max_words + slack and chars <= max_chars + 6 * slack and sticky(cur[-1], w, english)
            if pause or (full and not soft):
                groups.append(cur); cur = []
        cur.append(w)
        if re.search(r'[.!?…,]$', w['raw']):
            # a lone word ending a sentence joins the previous group ("השיווק שלי בדיוק כאן", not "כאן" alone)
            if len(cur) == 1 and groups and len(groups[-1]) <= max_words + 1 and cur[0]['s'] - groups[-1][-1]['e'] <= gap \
                    and not re.search(r'[.!?…]$', groups[-1][-1]['raw']) \
                    and sum(len(x['w']) + 1 for x in groups[-1]) + len(cur[0]['w']) <= max_chars + 12:
                groups[-1].extend(cur)
            else:
                groups.append(cur)
            cur = []
    if cur: groups.append(cur)
    return groups

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('words'); ap.add_argument('out')
    ap.add_argument('--W', type=int, default=1080); ap.add_argument('--H', type=int, default=1920)  # vertical by default (Reels/TikTok/Shorts); pass --W 1920 --H 1080 for 16:9
    ap.add_argument('--style', default='reels', choices=STYLES)
    ap.add_argument('--font', help='Heebo | Rubik | NotoSansHebrew (default: the style\'s font, else Heebo)'); ap.add_argument('--accent', default='FFD400')
    ap.add_argument('--color', default='FFFFFF'); ap.add_argument('--max-words', type=int)
    ap.add_argument('--max-chars', type=int); ap.add_argument('--y', type=float, help='vertical centre of the captions, 0..1')
    ap.add_argument('--below-face', metavar='VIDEO', help='place each caption under the face in VIDEO (top of the chest), per caption')
    ap.add_argument('--chest', type=float, default=0.5, help='with --below-face: gap below the face box, in face heights')
    ap.add_argument('--size', type=float, help="font size as a fraction of the frame height (overrides the style's)")
    ap.add_argument('--strong-shadow', action='store_true', help='soft style: a wider, darker halo for light backgrounds (white shirt, bright wall)')
    ap.add_argument('--keep-punct', action='store_true', help='keep commas and full stops (removed by default)')
    ap.add_argument('--srt'); ap.add_argument('--fix')
    a = ap.parse_args()
    st = STYLES[a.style]
    vertical = a.H > a.W
    a.font = a.font or st.get('font', 'Heebo')
    max_words = a.max_words or st.get('max_words') or (3 if a.style == 'reels' else 7)
    max_chars = a.max_chars or st.get('max_chars') or (18 if a.style == 'reels' else (32 if not vertical else 24))
    y = a.y if a.y is not None else st.get('y', 0.70 if vertical else 0.84)
    fixes = json.load(open(a.fix, encoding='utf-8')) if a.fix else {}

    words = []
    for w in json.load(open(a.words, encoding='utf-8')):
        raw = BIDI.sub('', w['w']).strip()
        if not raw: continue
        core = PUNCT_END.sub('', raw)
        core = fixes.get(core, core)
        shown = raw if a.keep_punct else core
        shown = re.sub(r'^[,.;:]+', '', shown)
        if not shown: continue
        words.append({'w': shown, 'raw': raw, 's': float(w['s']), 'e': float(w['e'])})
    groups = group(words, max_words, max_chars)
    ys = face_below(a.below_face, [(g[0]['s'] + g[-1]['e']) / 2 for g in groups], a.H, a.chest) if a.below_face else None
    if a.below_face: print('below-face placement:', 'face not found, using --y' if ys is None else f'y {min(ys):.2f}..{max(ys):.2f}')

    size = round(a.H * st['size']) if vertical else round(a.H * st['size'] * 1.15)
    if a.size: size = round(a.H * a.size)
    outline = max(0, round(a.H * st['outline'])); shadow = round(a.H * st['shadow'])
    bold = -1 if st['weight'] == 'Bold' else 0
    family = FAMILY.get(a.font, a.font)
    fontname = family if st['weight'] == 'Bold' else f"{family} {st['weight']}"
    border_style = 3 if st['box'] else 1
    back = '&H80000000&' if st['box'] else (bgr(st['shadow_rgb']) if 'shadow_rgb' in st else '&H64000000&')
    # per-event look tags: oblique shear and a hard offset shadow (libass \\xshad/\\yshad)
    look = (f"\\fax{st['fax']}" if 'fax' in st else '') + (f"\\xshad{a.H * st['xshad']:.1f}\\yshad{a.H * st['yshad']:.1f}" if 'xshad' in st else '')
    margin_v = round(a.H * (1 - y) - size / 2)
    margin_lr = round(a.W * 0.08)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {a.W}
PlayResY: {a.H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{fontname},{size},{bgr(a.color)},{bgr(a.accent)},&H00000000&,{back},{bold},0,0,0,100,100,0,0,{border_style},{outline if not st['box'] else round(size*0.18)},{shadow},2,{margin_lr},{margin_lr},{margin_v},177

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    font_file = FONTS / f"{a.font}-{st['weight']}.ttf"
    meas = Measure(str(font_file), size)
    space = (meas(' ') or size * 0.25) * 0.6  # side bearings already leave some air between words
    maxw = a.W - 2 * margin_lr; cx = a.W / 2; cy = a.H * y; lh = size * 1.12
    active = 1.08 if st['pop'] else 1.0
    ev, srt = [], []
    for gi, g in enumerate(groups):
        y = ys[gi] if ys else y; cy = a.H * y
        here = f"\\an5\\pos({a.W / 2:.1f},{cy:.1f})" if ys else ''
        g_start = g[0]['s']
        nxt = groups[gi + 1][0]['s'] if gi + 1 < len(groups) else g[-1]['e'] + 0.6
        g_end = min(max(g[-1]['e'] + 0.25, g_start + 0.5), nxt)
        text_plain = ' '.join(w['w'] for w in g)
        srt.append(f"{len(srt) + 1}\n{srt_time(g_start)} --> {srt_time(g_end)}\n{text_plain}\n")
        if st['hl'] == 'none':
            # Plain text: libass orders a single Hebrew run correctly by itself.
            if 'glow' in st:  # soft shadow = a blurred dark copy under the crisp text; both placed at the same centre
                gl = dict(st['glow'], **({'alpha': '30', 'blur': 12, 'bord': 7} if a.strong_shadow else {})); px = f"\\an5\\pos({a.W / 2:.1f},{a.H * y:.1f})"; fad = "\\fad(70,40)"
                ev.append(f"Dialogue: 0,{ass_time(g_start)},{ass_time(g_end)},Cap,,0,0,0,,{{\\an5\\pos({a.W / 2:.1f},{a.H * y + a.H * gl['dy']:.1f})"
                          f"\\1c&H000000&\\1a&H{gl['alpha']}&" + (f"\\bord{gl['bord']}\\3c&H000000&\\3a&H{gl['alpha']}&" if gl.get('bord') else '') + f"\\blur{gl['blur']}{fad}}}{text_plain}")
                ev.append(f"Dialogue: 1,{ass_time(g_start)},{ass_time(g_end)},Cap,,0,0,0,,{{{px}{fad}}}{text_plain}")
                continue
            ev.append(f"Dialogue: 0,{ass_time(g_start)},{ass_time(g_end)},Cap,,0,0,0,,{{{here}{look}}}{text_plain}" if (look or here) else
                      f"Dialogue: 0,{ass_time(g_start)},{ass_time(g_end)},Cap,,0,0,0,,{text_plain}")
            continue
        # Active-word highlight. libass reorders words wrongly when override tags split an RTL line,
        # so every word is its own event, placed by our own bidi layout.
        # layout widths include the outline on both sides; the active word's 8% growth fits inside the space
        ws = [w['w'] for w in g]; widths = [meas(w) + 2 * outline for w in ws]
        lines = split_lines(len(ws), widths, space, maxw)
        pos = [None] * len(ws)
        for li, idx in enumerate(lines):
            ly = cy + (li - (len(lines) - 1) / 2) * lh
            xs, _ = layout_line([ws[i] for i in idx], [widths[i] for i in idx], space, cx)
            for i, x in zip(idx, xs): pos[i] = (x, ly)
        for wi, w in enumerate(g):
            s0 = g_start if wi == 0 else w['s']
            e0 = g[wi + 1]['s'] if wi + 1 < len(g) else g_end
            if e0 <= s0: continue
            for wj, x in enumerate(g):
                tags = f"\\an5\\pos({pos[wj][0]:.1f},{pos[wj][1]:.1f})" + look
                if wj == wi:
                    tags += f"\\1c{bgr(a.accent)}"
                    if active != 1.0: tags += f"\\t(0,70,\\fscx{active*100:.0f}\\fscy{active*100:.0f})"
                elif wi == 0 and st['pop']:
                    tags += "\\fscx88\\fscy88\\t(0,90,\\fscx100\\fscy100)"
                ev.append(f"Dialogue: {1 if wj == wi else 0},{ass_time(s0)},{ass_time(e0)},Cap,,0,0,0,,{{{tags}}}{x['w']}")
    pathlib.Path(a.out).write_text(head + '\n'.join(ev) + '\n', encoding='utf-8')
    if a.srt: pathlib.Path(a.srt).write_text('\n'.join(srt), encoding='utf-8')
    print(f'{len(groups)} captions, {len(words)} words -> {a.out}' + (f' + {a.srt}' if a.srt else ''))

if __name__ == '__main__':
    main()
