#!/usr/bin/env python3
"""Build laser-ready files for the GVINAGE sign (cheese icon + lettering).

Every size is in millimetres. Examples:
    python3 make_sign.py                                  # default: 1800x280 board, 990 mm wide artwork
    python3 make_sign.py --board-width 1650 --board-height 300 --art-width 900
    python3 make_sign.py --cap-height 110                 # set the letter height instead of the width

Requires: pip install fonttools skia-pathops uharfbuzz shapely ezdxf cairosvg pillow numpy
"""
import argparse
import math
import os

import cairosvg
import ezdxf
import numpy as np
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import OverlapMode, instantiateVariableFont
from PIL import Image, ImageFilter
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
FONT = os.path.join(HERE, 'Cinzel-VariableFont.ttf')
TEXT = 'GVINAGE'
WEIGHT = 600          # Cinzel SemiBold, closest to the sign in the photo
ICON_GAP = 28         # space between the icon and the "G", in cap-height units (cap height = 100)
SW = 5.0              # icon line thickness, in cap-height units

# Everything is drawn in "cap units": cap height = 100, cap top at y=0, baseline at y=100, y pointing down.


# ---------------------------------------------------------------- lettering

class FlattenPen(BasePen):
    """Records glyph contours as polylines, splitting curves into short straight segments."""

    def __init__(self, glyph_set, step):
        super().__init__(glyph_set)
        self.step = step
        self.contours = []
        self.cur = None

    def _segments(self, *pts):
        length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        return max(2, math.ceil(length / self.step))

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        n = self._segments(p0, p1, p2, p3)
        for i in range(1, n + 1):
            t = i / n
            m = 1 - t
            self.cur.append(tuple(m**3 * a + 3 * m * m * t * b + 3 * m * t * t * c + t**3 * d
                                  for a, b, c, d in zip(p0, p1, p2, p3)))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        n = self._segments(p0, p1, p2)
        for i in range(1, n + 1):
            t = i / n
            m = 1 - t
            self.cur.append(tuple(m * m * a + 2 * m * t * b + t * t * c for a, b, c in zip(p0, p1, p2)))

    def _closePath(self):
        if self.cur and len(self.cur) > 2:
            self.contours.append(self.cur)
        self.cur = None

    _endPath = _closePath


def even_odd(contours):
    """Turns non-overlapping contours into one shape: nested contours become holes."""
    polys = sorted((Polygon(c).buffer(0) for c in contours), key=lambda p: -p.area)
    shape = Polygon()
    for p in polys:
        shape = shape.symmetric_difference(p)
    return shape


def lettering():
    font = TTFont(FONT)
    font = instantiateVariableFont(font, {'wght': WEIGHT}, overlap=OverlapMode.REMOVE)
    glyph_set = font.getGlyphSet()
    order = font.getGlyphOrder()
    cap = font['OS/2'].sCapHeight
    k = 100.0 / cap

    hb_font = hb.Font(hb.Face(hb.Blob.from_file_path(FONT)))
    hb_font.set_variations({'wght': WEIGHT})
    buf = hb.Buffer()
    buf.add_str(TEXT)
    buf.guess_segment_properties()
    hb.shape(hb_font, buf, {'kern': True})

    letters = []
    pen_x = 0
    for ch, info, pos in zip(TEXT, buf.glyph_infos, buf.glyph_positions):
        pen = FlattenPen(glyph_set, step=3)
        glyph_set[order[info.codepoint]].draw(pen)
        shape = even_odd(pen.contours)
        # font space (y up, baseline 0) -> cap units (y down, baseline 100)
        shape = affinity.affine_transform(shape, [k, 0, 0, -k, (pen_x + pos.x_offset) * k, 100])
        letters.append((ch, shape))
        pen_x += pos.x_advance
    return letters


# ---------------------------------------------------------------- cheese icon

def ellipse(cx, cy, rx, ry):
    return affinity.translate(affinity.scale(Point(0, 0).buffer(1, quad_segs=96), rx, ry, origin=(0, 0)), cx, cy)


def ring(cx, cy, rx, ry, w=SW):
    return ellipse(cx, cy, rx + w / 2, ry + w / 2).difference(ellipse(cx, cy, rx - w / 2, ry - w / 2))


def front_arc(cx, cy, rx, ry, w=SW):
    """Lower (front) half of an elliptical outline."""
    return ring(cx, cy, rx, ry, w).intersection(box(cx - rx - w, cy, cx + rx + w, cy + ry + w))


def stroke(points, w=SW):
    return LineString(points).buffer(w / 2, cap_style='flat', join_style='round')


def leaf(origin, length, width, angle):
    """Almond-shaped leaf with a vein, growing from `origin` in direction `angle` (degrees, y down)."""
    half = length / 2
    w2 = width / 2
    r_plus_a = half * half / w2
    r = (r_plus_a + w2) / 2
    a = r_plus_a - r
    lens = Point(0, a).buffer(r, quad_segs=96).intersection(Point(0, -a).buffer(r, quad_segs=96))
    vein = stroke([(-half + 5, 0), (half - 8, 0)], w=1.8)
    shape = lens.difference(vein).union(stroke([(-half - 4, 0), (-half + 2, 0)], w=2.6))
    t = math.radians(angle)
    cx, cy = origin[0] + (half + 4) * math.cos(t), origin[1] + (half + 4) * math.sin(t)
    return affinity.translate(affinity.rotate(shape, angle, origin=(0, 0)), cx, cy)


def cheese_icon():
    cx = 70.0
    # round wooden serving board: top face + front thickness
    p_cy, p_rx, p_ry, p_t = 74.0, 68.0, 24.0, 7.0
    # cheese wheel standing on the board, sides bulging slightly
    w_rx, w_ry, w_h, bulge = 48.0, 21.0, 50.0, 3.0
    w_bot = p_cy - 5
    w_top = w_bot - w_h

    def side(sign):
        x = cx + sign * w_rx
        return [(x + sign * bulge * math.sin(math.pi * i / 20), w_top + w_h * i / 20) for i in range(21)]

    wheel_body = unary_union([ellipse(cx, w_top, w_rx, w_ry), ellipse(cx, w_bot, w_rx, w_ry),
                              Polygon(side(-1) + side(1)[::-1])])
    wheel_lines = unary_union([
        ring(cx, w_top, w_rx, w_ry),
        front_arc(cx, w_bot, w_rx, w_ry),
        stroke(side(-1)),
        stroke(side(1)),
        # rind line just under the top edge
        front_arc(cx, w_top + 8, w_rx, w_ry, w=SW * 0.55).intersection(box(cx - w_rx + 5, 0, cx + w_rx - 5, 200)),
    ])

    def side_hole(u, t, r):
        # u: -1..1 across the wheel, t: 0..1 down the side; holes near the edges look narrower
        squash = math.sqrt(1 - u * u)
        return ellipse(cx + u * w_rx, w_top + w_ry * squash + t * w_h, r * squash, r)

    holes_top = [(-0.45, -0.2, 3.8), (-0.12, -0.55, 3.1), (0.22, -0.32, 3.6), (0.55, 0.05, 3.0),
                 (0.05, 0.2, 4.0), (-0.42, 0.42, 2.9), (0.36, 0.5, 2.7)]
    holes = unary_union([ellipse(cx + u * w_rx, w_top + v * w_ry, r, r * 0.55) for u, v, r in holes_top] +
                        [side_hole(u, t, r) for u, t, r in
                         [(-0.62, 0.48, 4.2), (-0.18, 0.72, 3.3), (0.27, 0.42, 3.9), (0.62, 0.74, 3.0)]])

    board_lines = unary_union([
        ring(cx, p_cy, p_rx, p_ry),
        front_arc(cx, p_cy + p_t, p_rx, p_ry),
        stroke([(cx - p_rx, p_cy), (cx - p_rx, p_cy + p_t)]),
        stroke([(cx + p_rx, p_cy), (cx + p_rx, p_cy + p_t)]),
    ]).difference(wheel_body)

    # herb sprig lying on the front-left of the board, drawn back to front
    sprig = (56.0, p_cy + 22)
    leaves = Polygon()
    for length, width, angle in ((38, 14, 226), (46, 17, 196), (34, 13, 162)):
        new_leaf = leaf(sprig, length, width, angle)
        leaves = leaves.difference(new_leaf.buffer(2.2)).union(new_leaf)
    lines = unary_union([wheel_lines, holes, board_lines]).difference(leaves.buffer(2.2))
    return unary_union([lines, leaves])


# ---------------------------------------------------------------- output helpers

def polygons(geom):
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    return [g for part in geom.geoms for g in polygons(part)]


def rings(geom):
    for p in polygons(geom):
        yield list(p.exterior.coords)
        for i in p.interiors:
            yield list(i.coords)


def svg_path(geom):
    d = []
    for r in rings(geom):
        d.append('M' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in r[:-1]) + ' Z')
    return ' '.join(d)


def write_svg(path, width, height, art, board=None, art_color='#000000', board_fill=None):
    parts = [f'<?xml version="1.0" encoding="UTF-8"?>',
             f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.2f}mm" height="{height:.2f}mm" '
             f'viewBox="0 0 {width:.2f} {height:.2f}">',
             '<title>GVINAGE sign</title>']
    if board is not None:
        fill = board_fill or 'none'
        parts.append(f'<g id="board-outline">'
                     f'<rect x="{board.bounds[0]:.2f}" y="{board.bounds[1]:.2f}" width="{board.bounds[2] - board.bounds[0]:.2f}" '
                     f'height="{board.bounds[3] - board.bounds[1]:.2f}" fill="{fill}" stroke="#FF0000" stroke-width="0.1"/></g>')
    parts.append(f'<g id="engrave" fill="{art_color}" fill-rule="evenodd" stroke="none">')
    for name, geom in art:
        parts.append(f'<path id="{name}" d="{svg_path(geom)}"/>')
    parts.append('</g></svg>')
    with open(path, 'w') as f:
        f.write('\n'.join(parts) + '\n')


def write_dxf(path, height, art, board=None, version='R2010'):
    """Closed polylines in mm. R12 uses old-style POLYLINE entities, which older laser software reads best."""
    doc = ezdxf.new(version) if version == 'R12' else ezdxf.new(version, units=ezdxf.units.MM)
    msp = doc.modelspace()

    def add(points, layer, color):
        # DXF is y-up: flip so the sign is not upside down
        points = [(x, height - y) for x, y in points]
        attribs = {'layer': layer, 'color': color}
        if version == 'R12':
            msp.add_polyline2d(points, close=True, dxfattribs=attribs)
        else:
            msp.add_lwpolyline(points, close=True, dxfattribs=attribs)

    doc.layers.add('ENGRAVE', color=7)
    if board is not None:
        doc.layers.add('BOARD', color=1)
        add(board.exterior.coords[:-1], 'BOARD', 1)
    for _, geom in art:
        for r in rings(geom):
            add(r[:-1], 'ENGRAVE', 7)
    doc.saveas(path)


def write_dxf_minimal(path, height, art):
    """Bare-bones DXF R12: only an ENTITIES section with closed POLYLINEs, CRLF line ends.
    The most widely readable variant, for old laser software."""
    out = ['0', 'SECTION', '2', 'ENTITIES']
    for _, geom in art:
        for r in rings(geom):
            out += ['0', 'POLYLINE', '8', '0', '66', '1', '70', '1', '10', '0.0', '20', '0.0', '30', '0.0']
            for x, y in r[:-1]:
                out += ['0', 'VERTEX', '8', '0', '10', f'{x:.3f}', '20', f'{height - y:.3f}', '30', '0.0']
            out += ['0', 'SEQEND', '8', '0']
    out += ['0', 'ENDSEC', '0', 'EOF']
    with open(path, 'w', newline='\r\n') as f:
        f.write('\n'.join(out) + '\n')


def write_plt(path, height, art):
    """HPGL, 40 units per mm, y up, one command per line (as CorelDRAW writes it)."""
    cmds = ['IN;', 'PA;', 'SP1;']
    for _, geom in art:
        for r in rings(geom):
            pts = [(round(x * 40), round((height - y) * 40)) for x, y in r]
            cmds.append(f'PU{pts[0][0]},{pts[0][1]};')
            cmds += [f'PD{x},{y};' for x, y in pts[1:]]
    cmds += ['PU;', 'SP0;']
    with open(path, 'w', newline='\r\n') as f:
        f.write('\n'.join(cmds) + '\n')


def write_bitmap(path, width, height, art, px_per_mm=10):
    """Black-on-white 1-bit bitmap with its resolution stored, so it imports at the right size."""
    tmp = os.path.join(HERE, '_tmp.svg')
    write_svg(tmp, width, height, art)
    from io import BytesIO
    png = cairosvg.svg2png(url=tmp, output_width=round(width * px_per_mm), output_height=round(height * px_per_mm),
                           background_color='white')
    os.remove(tmp)
    dpi = px_per_mm * 25.4
    Image.open(BytesIO(png)).convert('L').point(lambda v: 255 if v > 127 else 0, '1').save(path, dpi=(dpi, dpi))


def fill_time_minutes(art, speed, interval, overscan=5.0):
    """Rough raster-fill time when every shape is filled on its own (LightBurn 'Fill shapes individually')."""
    total = 0.0
    for _, geom in art:
        for p in polygons(geom):
            x0, y0, x1, y1 = p.bounds
            total += (y1 - y0) / interval * ((x1 - x0) + 2 * overscan) / speed
    return total / 60


def wood_texture(w, h, seed=3):
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(0, 1, w)[None, :]
    rows = rng.normal(0, 1, (h // 3 + 2, 1))
    rows = np.repeat(rows, 3, axis=0)[:h]
    grain = np.sin((y * 38 + 0.6 * np.sin(x * 7 + y * 3)) * math.pi) * 0.5 + rows * 0.35
    grain += rng.normal(0, 0.15, (h, w))
    base = np.array([186, 132, 82], dtype=float)
    img = base[None, None, :] * (1 + 0.06 * grain[..., None])
    return Image.fromarray(np.clip(img, 0, 255).astype('uint8')).filter(ImageFilter.GaussianBlur(0.8))


def artwork():
    """Icon followed by the lettering, as [(name, shape)] in cap units, in reading order."""
    letters = lettering()
    icon = cheese_icon()
    text_left = min(g.bounds[0] for _, g in letters)
    shift = icon.bounds[2] + ICON_GAP - text_left
    letters = [(ch, affinity.translate(g, shift, 0)) for ch, g in letters]
    names = [f'letter-{i + 1}-{ch}' for i, (ch, _) in enumerate(letters)]
    return [('cheese-icon', icon)] + [(n, g) for n, (_, g) in zip(names, letters)]


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--board-width', type=float, default=1800)
    ap.add_argument('--board-height', type=float, default=280)
    size = ap.add_mutually_exclusive_group()
    size.add_argument('--art-width', type=float, default=990, help='width of icon + lettering, mm')
    size.add_argument('--cap-height', type=float, help='height of the capital letters, mm')
    args = ap.parse_args()

    art = artwork()
    x0, y0, x1, y1 = unary_union([g for _, g in art]).bounds
    cap_mm = args.cap_height or args.art_width / (x1 - x0) * 100
    s = cap_mm / 100

    # artwork-only file: tight around the ink
    art_tight = [(n, affinity.affine_transform(g, [s, 0, 0, s, -x0 * s, -y0 * s]).simplify(0.02)) for n, g in art]
    aw, ah = (x1 - x0) * s, (y1 - y0) * s

    # board layout: artwork centred horizontally, cap-height band centred vertically
    bw, bh = args.board_width, args.board_height
    ox = (bw - aw) / 2
    oy = (bh - cap_mm) / 2 - (0 - y0) * s
    art_board = [(n, affinity.translate(g, ox, oy)) for n, g in art_tight]
    board = box(0, 0, bw, bh)

    write_svg(os.path.join(OUT, 'gvinage-artwork.svg'), aw, ah, art_tight)
    write_svg(os.path.join(OUT, 'gvinage-board-layout.svg'), bw, bh, art_board, board)
    write_dxf(os.path.join(OUT, 'gvinage-artwork.dxf'), ah, art_tight)
    write_dxf(os.path.join(OUT, 'gvinage-board-layout.dxf'), bh, art_board, board)

    # 1-bit bitmap at 254 dpi (10 px per mm) for software that only takes images
    tmp = os.path.join(HERE, '_tmp.svg')
    write_svg(tmp, aw, ah, art_tight)
    px = 10
    png = cairosvg.svg2png(url=tmp, output_width=round(aw * px), output_height=round(ah * px), background_color='white')
    os.remove(tmp)
    from io import BytesIO
    Image.open(BytesIO(png)).convert('L').point(lambda v: 255 if v > 127 else 0, '1').save(
        os.path.join(OUT, 'gvinage-artwork-254dpi.png'), dpi=(254, 254))

    # client preview: green lettering on a wood board
    pv = 1.2
    W, H = round(bw * pv), round(bh * pv)
    write_svg(tmp, bw, bh, art_board)
    mask_png = cairosvg.svg2png(url=tmp, output_width=W, output_height=H)
    os.remove(tmp)
    mask = Image.open(BytesIO(mask_png)).split()[-1]
    preview = wood_texture(W, H)
    green = Image.new('RGB', (W, H), (31, 72, 42))
    preview.paste(green, (0, 0), mask)
    preview.save(os.path.join(OUT, 'preview.png'))

    print(f'artwork: {aw:.1f} x {ah:.1f} mm, capital letters {cap_mm:.1f} mm high')
    print(f'board:   {bw:.0f} x {bh:.0f} mm, artwork starts {ox:.1f} mm from the left edge')
    for label, speed in (('CO2 300 mm/s', 300), ('CO2 150 mm/s', 150), ('diode 80 mm/s', 80)):
        print(f'fill time, interval 0.1 mm, {label}: ~{fill_time_minutes(art_tight, speed, 0.1):.0f} min per pass')


if __name__ == '__main__':
    main()
