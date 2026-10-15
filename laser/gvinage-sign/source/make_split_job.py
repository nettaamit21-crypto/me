#!/usr/bin/env python3
"""GVINAGE sign with the lettering centred on the board and the icon to its left, split into parts
that each fit the laser's work area. Every size is in millimetres.

    python3 make_split_job.py --board-height 200 --cap-height 150 --max-part-width 740 --out ../board-20cm

Positions are given from the board's vertical centre line (= centre of the word) and its bottom edge,
so the board's length does not need to be known.
"""
import argparse
import os
from io import BytesIO

import cairosvg
from PIL import Image, ImageDraw, ImageFont
from shapely import affinity
from shapely.ops import unary_union

from make_sign import HERE, artwork, fill_time_minutes, wood_texture, write_dxf, write_plt, write_svg

FONT_UI = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def split(items, max_w):
    """Splits the shapes, in reading order, into the fewest runs no wider than max_w, as even as possible."""
    xs = [g.bounds for _, g in items]

    def width(i, j):
        return max(b[2] for b in xs[i:j]) - min(b[0] for b in xs[i:j])

    for n in range(1, len(items) + 1):
        best = None

        def search(start, left, cuts):
            nonlocal best
            if left == 1:
                if width(start, len(items)) <= max_w:
                    parts = cuts + [(start, len(items))]
                    widest = max(width(i, j) for i, j in parts)
                    if best is None or widest < best[0]:
                        best = (widest, parts)
                return
            for end in range(start + 1, len(items)):
                if width(start, end) <= max_w:
                    search(end, left - 1, cuts + [(start, end)])

        search(0, n, [])
        if best:
            return [items[i:j] for i, j in best[1]]
    raise SystemExit(f'one shape is wider than {max_w} mm')


def render_mask(art, w, h, scale):
    tmp = os.path.join(HERE, '_tmp.svg')
    write_svg(tmp, w, h, art)
    png = cairosvg.svg2png(url=tmp, output_width=round(w * scale), output_height=round(h * scale))
    os.remove(tmp)
    return Image.open(BytesIO(png)).split()[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--board-height', type=float, required=True)
    ap.add_argument('--cap-height', type=float, required=True, help='height of the capital letters')
    ap.add_argument('--max-part-width', type=float, required=True, help='widest strip the laser can engrave')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    other = os.path.join(args.out, 'other-formats')
    os.makedirs(other, exist_ok=True)

    bh, cap = args.board_height, args.cap_height
    s = cap / 100
    art = artwork()
    text = unary_union([g for n, g in art if n.startswith('letter')])
    tx = (text.bounds[0] + text.bounds[2]) / 2
    # board coordinates: x = 0 on the centre line of the word, y = 0 on the top edge, y down
    oy = (bh - cap) / 2
    art = [(n, affinity.affine_transform(g, [s, 0, 0, s, -tx * s, oy]).simplify(0.02)) for n, g in art]
    ax0, ay0, ax1, ay1 = unary_union([g for _, g in art]).bounds
    if ay0 < 0 or ay1 > bh:
        raise SystemExit('the artwork is taller than the board')

    parts = split(art, args.max_part_width)
    info = []
    for k, part in enumerate(parts, 1):
        x0, y0, x1, y1 = unary_union([g for _, g in part]).bounds
        local = [(n, affinity.translate(g, -x0, -y0)) for n, g in part]
        name = f'gvinage-part{k}' if len(parts) > 1 else 'gvinage'
        w, h = x1 - x0, y1 - y0
        # main file: DXF R12 (LaserCut 5.3, RDWorks); the rest for other software
        write_dxf(os.path.join(args.out, name + '.dxf'), h, local, version='R12')
        write_dxf(os.path.join(other, name + '-dxf2000.dxf'), h, local, version='R2000')
        write_plt(os.path.join(other, name + '.plt'), h, local)
        write_svg(os.path.join(other, name + '.svg'), w, h, local)
        info.append(dict(file=name, letters=''.join(n[-1] if n.startswith('letter') else '[icon]' for n, _ in part),
                         w=x1 - x0, h=y1 - y0, mark_x=x0, mark_y=bh - y1, bounds=(x0, y0, x1, y1),
                         t250=fill_time_minutes(local, 250, 0.1), t150=fill_time_minutes(local, 150, 0.15)))

    # the board drawn only as long as the artwork needs, with the same margin at both ends
    margin = 40
    half = max(-ax0, ax1) + margin
    bw = 2 * half
    on_board = [(n, affinity.translate(g, half, 0)) for n, g in art]

    pv = 1.0
    W, H = round(bw * pv), round(bh * pv)
    preview = wood_texture(W, H)
    preview.paste(Image.new('RGB', (W, H), (31, 72, 42)), (0, 0), render_mask(on_board, bw, bh, pv))
    preview.save(os.path.join(args.out, 'preview.png'))

    # placement guide: the board, the centre line, each part's frame and its start mark
    top, bottom, side = 70, 120, 30
    guide = Image.new('RGB', (W + 2 * side, H + top + bottom), 'white')
    guide.paste(preview, (side, top))
    d = ImageDraw.Draw(guide)
    f_big = ImageFont.truetype(FONT_UI, 40)
    f_small = ImageFont.truetype(FONT_UI, 22)
    cx = side + half * pv
    for y in range(top - 30, top + H + 30, 16):
        d.line([(cx, y), (cx, y + 8)], fill=(200, 0, 0), width=3)
    d.text((cx, top + H + 34), '0', fill=(200, 0, 0), font=f_big, anchor='mt')
    colors = [(230, 120, 0), (0, 110, 220), (150, 0, 170), (0, 150, 90)]
    for k, p in enumerate(info):
        c = colors[k % len(colors)]
        x0, y0, x1, y1 = p['bounds']
        r = [side + (x0 + half) * pv, top + y0 * pv, side + (x1 + half) * pv, top + y1 * pv]
        for i in range(0, round(r[2] - r[0]), 18):
            d.line([(r[0] + i, r[1]), (min(r[0] + i + 9, r[2]), r[1])], fill=c, width=3)
            d.line([(r[0] + i, r[3]), (min(r[0] + i + 9, r[2]), r[3])], fill=c, width=3)
        for i in range(0, round(r[3] - r[1]), 18):
            d.line([(r[0], r[1] + i), (r[0], min(r[1] + i + 9, r[3]))], fill=c, width=3)
            d.line([(r[2], r[1] + i), (r[2], min(r[1] + i + 9, r[3]))], fill=c, width=3)
        d.text(((r[0] + r[2]) / 2, top - 12), str(k + 1), fill=c, font=f_big, anchor='mb')
        mx, my = r[0], r[3]
        d.ellipse([mx - 11, my - 11, mx + 11, my + 11], outline=(200, 0, 0), width=4)
        d.line([(mx - 18, my), (mx + 18, my)], fill=(200, 0, 0), width=3)
        d.line([(mx, my - 18), (mx, my + 18)], fill=(200, 0, 0), width=3)
        label = f'{k + 1}:  {p["mark_x"] / 10:+.1f} / {p["mark_y"] / 10:.1f} cm'
        d.text((mx, top + H + 80), label, fill=c, font=f_small, anchor='lm')
    guide.save(os.path.join(args.out, 'placement-guide.png'))

    print(f'artwork {ax1 - ax0:.1f} x {ay1 - ay0:.1f} mm, from {ax0:.1f} to {ax1:.1f} mm around the centre line')
    print(f'minimum board length for equal end margins of {margin} mm: {bw:.0f} mm')
    print(f'margins: top {ay0:.1f} mm, bottom {bh - ay1:.1f} mm; baseline {bh - oy - cap:.1f} mm above the bottom edge')
    for p in info:
        print(f"{p['file']}: {p['letters']}  {p['w']:.1f} x {p['h']:.1f} mm  "
              f"start mark (bottom-left) x={p['mark_x']:+.1f} mm from centre, y={p['mark_y']:.1f} mm above bottom  "
              f"fill ~{p['t250']:.0f} min @250mm/s 0.1  ~{p['t150']:.0f} min @150mm/s 0.15")


if __name__ == '__main__':
    main()
