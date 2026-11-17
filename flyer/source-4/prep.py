import sys, cv2, numpy as np
from PIL import Image
S = sys.argv[1]
def inpaint(img, mask, r=6):
    return cv2.inpaint(img, mask, r, cv2.INPAINT_TELEA)
def stroke_mask(gray, box, dark=True, thr=150, grow=5):
    x0, y0, x1, y1 = box
    m = np.zeros(gray.shape, np.uint8)
    sub = gray[y0:y1, x0:x1]
    m[y0:y1, x0:x1] = ((sub < thr) if dark else (sub > thr)).astype(np.uint8) * 255
    if grow: m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))
    return m
def shift_strokes(img, box, dy, dark=True, thr=150):
    """Move text strokes in box down by dy, keeping their exact look (delta transfer)."""
    x0, y0, x1, y1 = box
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    m = stroke_mask(gray, box, dark, thr, 7)
    bg = inpaint(img, m, 7)
    delta = img.astype(np.int16) - bg.astype(np.int16)
    out = bg.copy().astype(np.int16)
    sel = m[y0:y1, x0:x1] > 0
    tgt = out[y0+dy:y1+dy, x0:x1]
    tgt[sel] = tgt[sel] + delta[y0:y1, x0:x1][sel]
    return np.clip(out, 0, 255).astype(np.uint8)
def arch_mask(shape, x0, x1, top, bottom, ss=4):
    h, w = shape[:2]
    r = (x1 - x0 + 1) / 2.0; cx = (x0 + x1) / 2.0; cy = top + r
    ys, xs = np.mgrid[0:h*ss, 0:w*ss] / ss
    inside = (xs >= x0 - .5) & (xs <= x1 + .5) & (ys <= bottom + .5) & ((ys >= cy) | ((xs - cx)**2 + (ys - cy)**2 <= r*r))
    m = inside.reshape(h, ss, w, ss).mean(axis=(1, 3))
    return m
def cover(src, w, h, focus=(0.5, 0.5)):
    sh, sw = src.shape[:2]; s = max(w / sw, h / sh)
    r = cv2.resize(src, (int(round(sw * s)), int(round(sh * s))), interpolation=cv2.INTER_AREA)
    rh, rw = r.shape[:2]
    x = int(round((rw - w) * focus[0])); y = int(round((rh - h) * focus[1]))
    return r[y:y+h, x:x+w]
def place_in_arch(img, content, x0, x1, top, bottom):
    m = arch_mask(img.shape, x0, x1, top, bottom)
    w, h = x1 - x0 + 1, bottom - top + 1
    layer = img.copy(); layer[top:bottom+1, x0:x1+1] = content
    a = m[..., None]
    return (img * (1 - a) + layer * a).astype(np.uint8)

# ---------- green flyer ----------
g = cv2.imread(f'{S}/f2_in/19.webp')
# 1. arches: convoy (from center) -> left; workers -> center
CEN = (343, 775, 493, 1062); LEF = (49, 333, 579, 1028)
convoy = g[CEN[2]:CEN[3]+1, CEN[0]:CEN[1]+1].copy()
lw, lh = LEF[1]-LEF[0]+1, LEF[3]-LEF[2]+1
left_content = cover(convoy, lw, lh, (0.5, 0.75))
workers = cv2.imread(f'{S}/f2_in/21.webp')
workers = workers[330:1580, 0:950]
cw, ch = CEN[1]-CEN[0]+1, CEN[3]-CEN[2]+1
center_content = cover(workers, cw, ch, (0.5, 0.5))
g = place_in_arch(g, left_content, *LEF)
g = place_in_arch(g, center_content, *CEN)
gray = cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)
# 2. greeting line
g = inpaint(g, stroke_mask(gray, (150, 160, 990, 205), True, 175, 5))
# 3. serif line (keep the rules at ~1303-1310)
gray = cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)
m = stroke_mask(gray, (60, 1196, 1075, 1296), True, 175, 5); m[1298:, :] = 0
g = inpaint(g, m)
# 4. pill text (light on dark olive)
gray = cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)
g = inpaint(g, stroke_mask(gray, (260, 1352, 875, 1410), False, 120, 5), 5)
# 5. footer down 22px
g = shift_strokes(g, (180, 1522, 960, 1568), 22, True, 185)
cv2.imwrite(f'{S}/f2/green_base.png', g)

# ---------- wood flyer ----------
w = cv2.imread(f'{S}/wood_in/src.png')
gray = cv2.cvtColor(w, cv2.COLOR_BGR2GRAY)
w = inpaint(w, stroke_mask(gray, (150, 14, 990, 70), True, 150, 7), 7)
gray = cv2.cvtColor(w, cv2.COLOR_BGR2GRAY)
m = stroke_mask(gray, (30, 1198, 1102, 1280), True, 150, 7); m[1283:, :] = 0; m[:1196, :] = 0
w = inpaint(w, m, 7)
gray = cv2.cvtColor(w, cv2.COLOR_BGR2GRAY)
w = inpaint(w, stroke_mask(gray, (70, 1332, 1062, 1388), False, 98, 13), 11)
w = shift_strokes(w, (100, 1518, 1030, 1566), 20, True, 150)
cv2.imwrite(f'{S}/f2/wood_base.png', w)
print('ok')
