import sys, cv2, numpy as np
S = sys.argv[1]
sys.path.insert(0, '')  # no local imports
exec(open(f'{S}/f2_prep.py').read().split('# ---------- green flyer ----------')[0])  # reuse helpers only
orig = cv2.imread(f'{S}/f2_in/19.webp')
base = cv2.imread(f'{S}/f2/green_base_clean.png')
D = 50
ARCHES = {'L': (49, 333, 579, 1028), 'C': (343, 775, 493, 1062), 'R': (787, 1077, 579, 1028)}
# contents from the original sources
convoy = orig[493:1063, 343:776].copy()
view = orig[579:1029, 787:1078].copy()
workers = cv2.imread(f'{S}/f2_in/21.webp')[380:1560, 0:760]
out = base.copy()
for k, (x0, x1, top, bot) in ARCHES.items():
    nb = bot - D
    # shift the bottom border + paper band up by D (columns of the arch incl. its side borders)
    cx0, cx1 = x0 - 9, x1 + 10
    src = base[bot + 1: bot + 8 + D, cx0:cx1].copy()
    out[nb + 1: nb + 8 + D, cx0:cx1] = src
    w, h = x1 - x0 + 1, nb - top + 1
    if k == 'L':
        content = cover(convoy, w, h, (0.5, 0.75))
    elif k == 'C':
        s = w / view.shape[1]
        up = cv2.resize(view, (w, int(round(view.shape[0] * s))), interpolation=cv2.INTER_LANCZOS4)
        up = cv2.addWeighted(up, 1.35, cv2.GaussianBlur(up, (0, 0), 1.2), -0.35, 0)
        off = int(round((up.shape[0] - h) * 0.8)); content = up[off:off + h, :]
    else:
        content = cover(workers, w, h, (0.5, 0.5))
    out = place_in_arch(out, content, x0, x1, top, nb)
cv2.imwrite(f'{S}/f2/green_base_v3.png', out)
print('ok')
