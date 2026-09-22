"""Build the SetCode font: trace the letters of the Scarlet & Violet era set-code symbols from the sharpest
Bulbapedia originals, draw the missing letters/digits to the same geometry, and emit OTF + WOFF2."""
import json, math, os, sys
import numpy as np
from PIL import Image
import potrace
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
SYM = os.path.join(HERE, 'img', 'symbols')
OUT = os.path.join(HERE, 'font')
os.makedirs(OUT, exist_ok=True)
UPM = 1000
CAP = 700            # cap height in font units
SB = 38              # side bearing: letters sit ~0.11 cap apart, as on the Delta Reign / Stellar Crown originals

sets = json.load(open(os.path.join(HERE, 'sets_data.json'), encoding='utf-8'))
era = [s for s in sets if s['release'] >= '2023-03-31' and s['type'] != 'Other' and s.get('symbol_img')]

def box_of(path):
    im = Image.open(path).convert('RGBA'); a = np.array(im)
    ys, xs = np.where(a[:, :, 3] > 128)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

# ---------- candidate source images per letter, best first ----------
sources = []                                   # (box height, code, image path)
for st in era:
    sources.append((box_of(st['symbol_img']).shape[0], st['abbr'], st['symbol_img']))
ENH = os.path.join(HERE, 'enhanced')           # enhanced/<CODE>.png: upscaled images (e.g. Topaz) beat originals
if os.path.isdir(ENH):
    for fn in sorted(os.listdir(ENH)):
        if fn.lower().endswith('.png'):
            path = os.path.join(ENH, fn); code = os.path.splitext(fn)[0].upper()
            sources.append((box_of(path).shape[0], code, path)); print(f'  enhanced source {code}: box {box_of(path).shape[0]}px')
sources.sort(key=lambda t: -t[0])

# ---------- connected components ----------
def label(mask):
    H, W = mask.shape; lab = np.zeros((H, W), int); n = 0
    for y in range(H):
        for x in range(W):
            if mask[y, x] and not lab[y, x]:
                n += 1; stack = [(y, x)]; lab[y, x] = n
                while stack:
                    cy, cx = stack.pop()
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not lab[ny, nx]:
                                lab[ny, nx] = n; stack.append((ny, nx))
    return lab, n

FLAT = set('ABDEFHIJKLMNPRTVWXYZ')   # letters with a flat top or bottom: define the cap height / baseline

_extracted = {}
def extract(path, code):
    """Split a symbol image into per-letter strips. Returns {letter: (bitmap, scale, baseline)} or None."""
    if path in _extracted: return _extracted[path]
    a = box_of(path); H, W = a.shape[:2]
    m = int(round(0.12 * H))
    white = (a[:, :, 3] > 128) & (a[:, :, 0] > 190) & (a[:, :, 1] > 190) & (a[:, :, 2] > 190)
    white[:m, :] = False; white[-m:, :] = False; white[:, :m] = False; white[:, -m:] = False
    lab, n = label(white)
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(ys) < 0.004 * H * W: continue                       # ignore noise specks
        comps.append((xs.min(), xs.max(), ys.min(), ys.max(), i))
    comps.sort()
    if len(comps) != len(code):
        print(f'  ! {code} ({H}px): {len(comps)} components for {len(code)} letters, unusable'); _extracted[path] = None; return None
    tag = code.endswith('EN') and len(code) > 2       # e.g. DLREN: the last two are the small language tag
    main = list(zip(comps, code))[:-2] if tag else list(zip(comps, code))
    tags = list(zip(comps, code))[-2:] if tag else []
    flats = [c for c, ch in main if ch in FLAT] or [c for c, ch in main]
    top = min(c[2] for c in flats); bottom = max(c[3] for c in flats)
    scale = CAP / (bottom - top + 1)
    out = {}
    for c, ch in main:
        x0, x1, y0, y1, i = c
        if (y1 - y0 + 1) < 0.85 * (bottom - top + 1) and ch not in 'O0CGSQ': continue
        out[ch] = (lab[:, x0:x1 + 1] == i, scale, bottom, H)
    if tags:                                          # tag letters get their own cap height and baseline
        ttop = min(c[2] for c, _ in tags); tbottom = max(c[3] for c, _ in tags); tscale = CAP / (tbottom - ttop + 1)
        for c, ch in tags:
            x0, x1, y0, y1, i = c
            out[ch] = (lab[:, x0:x1 + 1] == i, tscale, tbottom, H)
    _extracted[path] = out; return out

glyph_bitmaps = {}
letters = sorted({ch for _, code, _ in sources for ch in code})
for ch in letters:
    for h, code, path in sources:
        if ch not in code: continue
        got = extract(path, code)
        if got and ch in got:
            glyph_bitmaps[ch] = got[ch][:3]; print(f'  {ch} <- {code} ({h}px box)'); break
    else:
        print(f'  ? no usable source for {ch}')

# ---------- trace ----------
def trace(bm, scale, baseline):
    """potrace a boolean bitmap -> list of contours, each a list of ('line', (x,y)) / ('curve', c1, c2, p)."""
    # upsample small sources so potrace has something to smooth
    up = 1
    up = 1   # trace at native resolution: potrace fits smooth curves to the pixel edge itself; any upscale
             # multiplies the outline segments (27 -> 160 for the M) and shows as a ragged edge
    if up > 1:   # upscale, blur away the pixel staircase, re-threshold: the tracer then sees real curves
        from PIL import ImageFilter
        big = Image.fromarray((bm * 255).astype(np.uint8)).resize((bm.shape[1] * up, bm.shape[0] * up), Image.BILINEAR)   # no ringing
        big = big.filter(ImageFilter.GaussianBlur(radius=max(0.8, up * 0.5)))
        bm = np.array(big) > 127
    bmp = potrace.Bitmap(~bm)                   # potracer: values <= blacklevel are foreground, so invert
    path = bmp.trace(turdsize=2, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY, alphamax=1.0, opticurve=True, opttolerance=0.3)
    contours = []
    def P(pt): return ((pt.x / up) * scale, (baseline + 1 - pt.y / up) * scale)   # rows count down; flip to y-up
    for curve in path:
        segs = [('move', P(curve.start_point))]
        for seg in curve:
            if seg.is_corner:
                segs.append(('line', P(seg.c))); segs.append(('line', P(seg.end_point)))
            else:
                segs.append(('curve', P(seg.c1), P(seg.c2), P(seg.end_point)))
        contours.append(segs)
    return contours

glyphs = {}   # ch -> contours (font units, y up, x starting anywhere)
for ch, (bm, scale, baseline) in glyph_bitmaps.items():
    glyphs[ch] = trace(bm, scale, baseline)

def bounds(contours):
    xs = []; ys = []
    for c in contours:
        for seg in c:
            for pt in seg[1:]: xs.append(pt[0]); ys.append(pt[1])
    return min(xs), min(ys), max(xs), max(ys)

def shift(contours, dx, dy):
    out = []
    for c in contours:
        out.append([(seg[0],) + tuple((p[0] + dx, p[1] + dy) for p in seg[1:]) for seg in c])
    return out

# normalise traced glyphs: left edge at SB, flat baseline at 0 (round letters keep their overshoot)
for ch in list(glyphs):
    x0, y0, x1, y1 = bounds(glyphs[ch])
    dy = 0 if ch not in FLAT else -y0
    glyphs[ch] = shift(glyphs[ch], SB - x0, dy)

# stroke measurements from traced letters
def width(ch): x0, _, x1, _ = bounds(glyphs[ch]); return x1 - x0
STEM = width('I')                       # vertical stem thickness
HW = width('H') if 'H' in glyphs else width('E') * 1.05
print(f'stem {STEM:.0f} units, H width {HW:.0f}, E width {width("E"):.0f}, O width {width("O"):.0f}')

# ---------- hand-built glyphs (polygons + arcs), same stem, same cap height ----------
def poly(points):
    area = sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points)))
    if area < 0: points = list(reversed(points))
    return [[('move', points[0])] + [('line', p) for p in points[1:]]]
def rect(x0, y0, x1, y1): return poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
def para(x0, x1, y0, y1, w, rising=True):
    """Diagonal bar of horizontal thickness w from (x0,y0) to (x1,y1)."""
    return poly([(x0, y0), (x0 + w, y0), (x1 + w, y1), (x1, y1)]) if rising else poly([(x0, y0), (x0 + w, y0), (x1 + w, y1), (x1, y1)])
def arc_pts(cx, cy, rx, ry, a0, a1, n=20):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
def ring(cx, cy, rx, ry, a0, a1, t):
    """Filled arc band between radius r and r-t. A full ring is outer ccw + inner cw (a hole)."""
    if abs((a1 - a0) % 360) < 1e-6:
        outer = arc_pts(cx, cy, rx, ry, 0, 360, 40)[:-1]; inner = arc_pts(cx, cy, rx - t, ry - t, 360, 0, 40)[:-1]
        return [[('move', outer[0])] + [('line', q) for q in outer[1:]], [('move', inner[0])] + [('line', q) for q in inner[1:]]]
    outer = arc_pts(cx, cy, rx, ry, a0, a1); inner = arc_pts(cx, cy, rx - t, ry - t, a1, a0)
    return poly(outer + inner)

hand = {}
W = HW; S = STEM; D = S * 1.08    # diagonal thickness a touch heavier than stems, as in the originals
X0 = SB
# N
hand['N'] = rect(X0, 0, X0 + S, CAP) + rect(X0 + W - S, 0, X0 + W, CAP) + poly([(X0, CAP), (X0 + D, CAP), (X0 + W, 0), (X0 + W - D, 0)])
# U : stems + half-ring bottom
r = W / 2
hand['U'] = rect(X0, r, X0 + S, CAP) + rect(X0 + W - S, r, X0 + W, CAP) + ring(X0 + r, r, r, r * 0.95, 180, 360, S)
# Z
hand['Z'] = rect(X0, CAP - S * 0.95, X0 + W, CAP) + rect(X0, 0, X0 + W, S * 0.95) + poly([(X0 + W - D, CAP - S * 0.95), (X0 + W, CAP - S * 0.95), (X0 + D, S * 0.95), (X0, S * 0.95)])
# X
hand['X'] = poly([(X0, 0), (X0 + D, 0), (X0 + W, CAP), (X0 + W - D, CAP)]) + poly([(X0 + W - D, 0), (X0 + W, 0), (X0 + D, CAP), (X0, CAP)])
# Y
ym = CAP * 0.42
hand['Y'] = rect(X0 + W / 2 - S / 2, 0, X0 + W / 2 + S / 2, ym + 1) + poly([(X0, CAP), (X0 + D, CAP), (X0 + W / 2 + S / 2, ym), (X0 + W / 2 - S / 2, ym)]) + poly([(X0 + W - D, CAP), (X0 + W, CAP), (X0 + W / 2 + S / 2, ym), (X0 + W / 2 - S / 2, ym)])
# Q : O plus a tail
if 'O' in glyphs:
    ox0, oy0, ox1, oy1 = bounds(glyphs['O'])
    hand['Q'] = glyphs['O'] + poly([(ox0 + (ox1 - ox0) * 0.52, oy0 + (oy1 - oy0) * 0.22), (ox0 + (ox1 - ox0) * 0.52 + D, oy0 + (oy1 - oy0) * 0.22), (ox1 + S * 0.35, oy0 - S * 0.25), (ox1 + S * 0.35 - D, oy0 - S * 0.25)])
# digits
DW = CAP / 2          # round digits: two bowls of radius CAP/4 stack to exactly the cap height
S = S * 0.9           # digit bands a touch lighter so the counters stay open at this radius
hand['0'] = glyphs['O'] if 'O' in glyphs else ring(X0 + DW / 2, CAP / 2, DW / 2, CAP / 2, 0, 360, S)
hand['1'] = rect(X0 + DW * 0.45, 0, X0 + DW * 0.45 + S, CAP) + poly([(X0 + DW * 0.45, CAP), (X0 + DW * 0.45 + S, CAP), (X0 + DW * 0.45 + S, CAP - S * 1.6), (X0 + DW * 0.1, CAP - S * 2.3), (X0 + DW * 0.1, CAP - S * 1.3)])
rr = CAP / 4
hand['2'] = ring(X0 + rr, CAP - rr, rr, rr, 0, 180, S) + poly([(X0 + DW, CAP - rr), (X0 + DW - D, CAP - rr), (X0, S), (X0 + D, S)]) + rect(X0, 0, X0 + DW, S)
hand['3'] = ring(X0 + rr, CAP - rr, rr, rr, -80, 100, S) + ring(X0 + rr, rr, rr, rr, -100, 80, S) + rect(X0 + rr * 0.55, CAP - rr - S / 2, X0 + rr, CAP - rr + S / 2)
hand['4'] = rect(X0 + DW * 0.62, 0, X0 + DW * 0.62 + S, CAP) + rect(X0, S * 1.2, X0 + DW, S * 2.2) + poly([(X0, S * 1.2), (X0 + D, S * 1.2), (X0 + DW * 0.62 + D, CAP), (X0 + DW * 0.62, CAP)])
hand['5'] = rect(X0, CAP - S, X0 + DW, CAP) + rect(X0, CAP * 0.5, X0 + S, CAP) + rect(X0, CAP * 0.5, X0 + DW * 0.62, CAP * 0.5 + S) + ring(X0 + rr * 0.95, rr * 1.02, rr * 1.02, rr * 1.02, -125, 95, S)
hand['6'] = ring(X0 + rr, rr, rr, rr, 0, 360, S) + ring(X0 + rr, CAP - rr, rr, rr, 60, 180, S) + rect(X0, rr, X0 + S, CAP - rr)
hand['9'] = ring(X0 + rr, CAP - rr, rr, rr, 0, 360, S) + ring(X0 + rr, rr, rr, rr, 240, 360, S) + rect(X0 + DW - S, rr, X0 + DW, CAP - rr)
hand['7'] = rect(X0, CAP - S, X0 + DW, CAP) + poly([(X0 + DW - D, CAP - S), (X0 + DW, CAP - S), (X0 + DW * 0.42 + D, 0), (X0 + DW * 0.42, 0)])
hand['8'] = ring(X0 + rr * 0.95, CAP - rr * 0.98, rr * 0.98, rr * 0.98, 0, 360, S) + ring(X0 + rr * 0.95, rr * 1.02, rr * 1.02, rr * 1.02, 0, 360, S)

def signed_area(contour):
    pts = [seg[-1] for seg in contour]
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
def reverse(contour):
    pts = [seg[-1] for seg in contour][::-1]
    return [('move', pts[0])] + [('line', q) for q in pts[1:]]
# Nonzero winding: every solid part must share ONE direction, holes the opposite. poly() already makes each
# hand polygon counter-clockwise; a full ring's inner contour was built clockwise. Match the traced glyphs' outer
# direction so mixed glyphs (Q = traced O + drawn tail) union correctly.
ref_sign = signed_area(max(glyphs['I'], key=lambda c: abs(signed_area(c))))
def match(contours):
    out = []
    for c in contours:
        want_outer = signed_area(c) > 0          # poly()/outer arcs are ccw (+); ring holes are cw (-)
        sign_now = signed_area(c) > 0
        target = (ref_sign > 0) if want_outer else (ref_sign < 0)
        out.append(c if sign_now == target else reverse(c))
    return out
for ch in list(hand):
    if ch == 'Q': hand['Q'] = glyphs['O'] + match(hand['Q'][len(glyphs['O']):])
    elif ch == '0': hand['0'] = glyphs['O']
    else: hand[ch] = match(hand[ch])
for ch in ('0', '3'):            # drop 40 px traces of these; keep them when an enhanced source provided them
    if ch in glyph_bitmaps and glyph_bitmaps[ch][0].shape[0] < 100: glyphs.pop(ch, None); glyph_bitmaps.pop(ch, None)
# 3 = the traced B with its stem removed (the bowls keep their true Futura shape)
if 'B' in glyph_bitmaps:
    bmB, scB, baseB = glyph_bitmaps['B']
    bm3 = bmB.copy(); cols = np.where(bm3.any(axis=0))[0]; stem_px = int(round(STEM / scB * 1.12))
    bm3[:, :cols.min() + stem_px] = False
    hand['3'] = shift(trace(bm3, scB, baseB), 0, 0); x0, y0, x1, y1 = bounds(hand['3']); hand['3'] = shift(hand['3'], SB - x0, -y0)
# Flatten every constructed glyph into one non-overlapping outline (Chrome's DirectWrite path renders
# overlapping contours badly). Polygons only: exteriors follow the traced glyphs' direction, holes the opposite.
from shapely.geometry import Polygon
from shapely.ops import unary_union
def flatten(contours):
    polys = []
    for c in contours:
        pts = [seg[-1] for seg in c]
        if len(pts) >= 3: polys.append(Polygon(pts).buffer(0))
    # a contour lying entirely inside another is a hole (the inner ring of 0/6/8/9), everything else is solid
    holes = [q for q in polys if any(o is not q and o.contains(q) for o in polys)]
    solid = [q for q in polys if q not in holes]
    u = unary_union(solid)
    if holes: u = u.difference(unary_union(holes))
    u = u.buffer(0)
    if u.geom_type == 'MultiPolygon':                       # drop slivers
        big = max(g.area for g in u.geoms); u = unary_union([g for g in u.geoms if g.area > big * 0.01])
    geoms = list(u.geoms) if u.geom_type == 'MultiPolygon' else [u]
    out = []
    for g in geoms:
        ext = list(g.exterior.coords)[:-1]; ext_c = [('move', ext[0])] + [('line', q) for q in ext[1:]]
        out.append(ext_c if (signed_area(ext_c) > 0) == (ref_sign > 0) else reverse(ext_c))
        for hole in g.interiors:
            h = list(hole.coords)[:-1]; h_c = [('move', h[0])] + [('line', q) for q in h[1:]]
            out.append(h_c if (signed_area(h_c) > 0) == (ref_sign < 0) else reverse(h_c))
    return out
for ch in list(hand):
    if ch in ('0', '3', 'Q'): continue           # traced (curves) or traced + tail: leave as is
    if all(seg[0] != 'curve' for c in hand[ch] for seg in c): hand[ch] = flatten(hand[ch])
for ch, c in hand.items():
    if ch not in glyphs: glyphs[ch] = c

# ---------- build the font ----------
order = ['.notdef', 'space'] + [ch if ch.isalpha() else {'0':'zero','1':'one','2':'two','3':'three','4':'four','5':'five','6':'six','7':'seven','8':'eight','9':'nine'}[ch] for ch in sorted(glyphs)]
names = {ch: (ch if ch.isalpha() else {'0':'zero','1':'one','2':'two','3':'three','4':'four','5':'five','6':'six','7':'seven','8':'eight','9':'nine'}[ch]) for ch in glyphs}
fb = FontBuilder(UPM, isTTF=False)
fb.setupGlyphOrder(order)
fb.setupCharacterMap({ord(ch): names[ch] for ch in glyphs} | {32: 'space'})
charstrings = {}; metrics = {}
def draw(contours, width=0):
    pen = T2CharStringPen(width, None)
    for c in contours:
        for seg in c:
            if seg[0] == 'move': pen.moveTo(seg[1])
            elif seg[0] == 'line': pen.lineTo(seg[1])
            else: pen.curveTo(seg[1], seg[2], seg[3])
        pen.closePath()
    return pen.getCharString()
for ch, c in glyphs.items():
    x0, y0, x1, y1 = bounds(c)
    adv = int(round(x1 + SB)); charstrings[names[ch]] = draw(c, adv); metrics[names[ch]] = (adv, int(round(x0)))
charstrings['.notdef'] = draw(rect(SB, 0, SB + 300, CAP), 300 + 2 * SB); metrics['.notdef'] = (300 + 2 * SB, SB)
charstrings['space'] = T2CharStringPen(int(SB * 3), None).getCharString(); metrics['space'] = (int(SB * 3), 0)
fb.setupCFF('SetCode', {'FullName': 'SetCode', 'FamilyName': 'SetCode', 'Weight': 'Bold'}, charstrings, {})
fb.setupHorizontalMetrics(metrics)
fb.setupHorizontalHeader(ascent=CAP + 100, descent=-100)
fb.setupNameTable({'familyName': 'SetCode', 'styleName': 'Bold', 'fullName': 'SetCode Bold', 'psName': 'SetCode-Bold', 'uniqueFontIdentifier': 'SetCode;2026',
                   'description': 'Letters traced from the Scarlet & Violet era Pokemon TCG set-code symbols; missing letters and digits drawn to match. Personal fan project.'})
fb.setupOS2(sTypoAscender=CAP + 100, sTypoDescender=-100, usWinAscent=CAP + 100, usWinDescent=100, sCapHeight=CAP, sxHeight=CAP, fsSelection=0x20 | 0x40, usWeightClass=700)
fb.setupPost()
otf = os.path.join(OUT, 'SetCode.otf'); fb.save(otf)
f = TTFont(otf); f.flavor = 'woff2'; f.save(os.path.join(OUT, 'SetCode.woff2'))
print('built', otf, 'glyphs:', ''.join(sorted(glyphs)), 'traced:', ''.join(sorted(glyph_bitmaps)), 'drawn:', ''.join(sorted(set(glyphs) - set(glyph_bitmaps))))
