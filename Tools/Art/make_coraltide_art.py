"""Builds Assets/coraltide_art.png from Michael's Coral Tide artwork (Tools/Art/coraltide_original.png, 1536 x 1024).

The artwork is a 3:2 pedal mock-up; the double-wide body is 464 x 372 px (186.8 x 149.8 mm, art printed 2.6 mm inside the
edge = 1.256 : 1). So the face is made taller without distorting anything that has a shape:
  - painted out: the four knobs, the ORDER toggle, both LEDs, both footswitches,
    the maker's mark (footprint + name: not ours to use), and - temporarily - every printed element of the control
    rows (dot scales, knob labels, ORDER / B > EQ / EQ > B, the BOOST / EQ footswitch labels);
  - the face is stretched vertically in bands: the now-plain cream control band most, the sea / beach / coral band less,
    the title band ("Coral Tide" + sun) only 5 %, the frame lines and the tagline not at all;
  - the printed elements go back UNSTRETCHED, each group anchored to its control (dot scale + label to its knob, toggle
    legends to the toggle, footswitch labels to their switch), extracted by unmixing against the inpainted background.
The real controls are placed where the painted ones end up (fractions printed at the end -> FaceLayout "ct" branch and
render_coraltide.py).

Only numpy, opencv-python (core) and pillow. Run from C:\\Dev\\pedalfactory-master (takes a few minutes):
    python Tools/Art/make_coraltide_art.py Tools/Art/coraltide_original.png Assets/coraltide_art.png
Source pixel coordinates below refer to the 1536 x 1024 original."""
import os, sys, numpy as np, cv2
from PIL import Image

CROP = (20, 26, 1516, 998)                         # flat top incl. the cream margin outside the printed frame line
KNOBS = [(223, 197), (528, 196), (1003, 196), (1309, 196)]   # BOOST, LEVEL, LOW, HIGH: centre of each dot scale (r 110)
PAINTED = [(222, 196), (529, 196), (1007, 196), (1314, 196)]  # centre of each painted knob skirt (r ~99)
KNOB_D = 197                                       # painted skirt diameter
DOT_R, DOT_ANGLES = 110.3, (-125.2, -93.6, -62.0, -31.6, 0.0, 31.6, 62.0, 93.6, 125.2)   # dot scale, deg clockwise from up
TOGGLE = (768, 184)
LEDS = [(565, 693), (968, 693)]                    # red (BOOST), blue (EQ)
FOOTS = [(563, 815), (967, 815)]                   # BOOST, EQ
FOOT_D = 165                                       # painted hex nut across
BRAND = [(660, 898, 876, 932), (746, 820, 797, 900)]          # "BAREFOOT FX" and the footprint: painted out
FOOT_LABELS = [(498, 903, 628, 944), (934, 903, 996, 944)]    # BOOST, EQ under the switches (painted out)
FOOT_INK = [(500, 911, 626, 941), (938, 911, 992, 942)]       # ... and the lettering put back
TOP_BAND = (62, 45, 1476, 354)                     # control rows (x0, y0, x1, y1), inside the frame line

# vertical stretch: (y0, y1, scale) bands in source px; everything else 1.0. Total height 972 -> 1191.
BANDS = [(50, 343, 1.54), (356, 624, 1.05), (668, 978, 1.15)]

BODY_W, BODY_H, INSET = 91.0 * (464 / 226), 91.0 * 372 / 226, 2.6     # mm (= render_coraltide.py)


def ymap_table(h):
    """Source row -> output row (float), cumulative over the bands."""
    s = np.ones(h, np.float64)
    for y0, y1, k in BANDS:
        s[y0:y1] = k
    return np.concatenate([[0.0], np.cumsum(s)])            # ymap[y] = output position of source row edge y


def mirror_fill(img, hole, after_only=False):
    """Fill each row-run of `hole` by mirroring the row in from both ends, cross-faded (after_only: from the far
    end only)."""
    out = img.astype(np.float32).copy()
    for y in np.nonzero(hole.any(1))[0]:
        row = hole[y]
        xs = np.nonzero(row)[0]
        spans = np.split(xs, np.nonzero(np.diff(xs) > 1)[0] + 1)
        for sp in spans:
            x0, x1 = int(sp[0]), int(sp[-1]) + 1
            n = x1 - x0
            for k, x in enumerate(range(x0, x1)):
                left = out[y, max(2 * x0 - 1 - x, 0)]
                d = x1 - 1 - x                                          # distance from the far end
                if after_only:
                    d = d % 56; d = d if d < 28 else 55 - d             # zig-zag within a 28 px strip beyond the hole
                right = out[y, min(x1 + d, img.shape[1] - 1)]
                w = 1.0 if after_only else (k + 0.5) / n
                w = w * w * (3 - 2 * w)
                out[y, x] = (1 - w) * left + w * right
    return np.clip(out, 0, 255).astype(np.uint8)


def synth_cream(field, hf_src, hf_ok, shape, rng, tile=28, ov=8):
    """Plain cream paint for an area of `shape` (h, w): `field` = smooth colour (h, w, 3) + speckle texture quilted at
    random from the clean cream areas of the original (hf_src = original minus its blur, hf_ok = usable source pixels)."""
    h, w = shape
    acc = np.zeros((h, w, 3), np.float32); wsum = np.zeros((h, w), np.float32)
    ramp = np.minimum(np.arange(tile + ov) + 1, np.arange(tile + ov)[::-1] + 1).astype(np.float32)
    win = np.minimum(np.outer(np.minimum(ramp, ov), np.minimum(ramp, ov)), ov * ov) / (ov * ov)
    ok = cv2.erode(hf_ok.astype(np.uint8), np.ones((tile + ov, tile + ov), np.uint8), anchor=(0, 0),
                   borderType=cv2.BORDER_CONSTANT, borderValue=0)
    ys, xs = np.nonzero(ok)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            j = rng.integers(len(ys))
            p = hf_src[ys[j]:ys[j] + tile + ov, xs[j]:xs[j] + tile + ov]
            hh, ww = min(tile + ov, h - y), min(tile + ov, w - x)
            acc[y:y + hh, x:x + ww] += p[:hh, :ww] * win[:hh, :ww, None]
            wsum[y:y + hh, x:x + ww] += win[:hh, :ww]
    return field + acc / np.maximum(wsum, 1e-6)[..., None]


def build(src, out):
    im = cv2.cvtColor(np.array(Image.open(src).convert("RGB")), cv2.COLOR_RGB2BGR)
    H, W = im.shape[:2]
    rng = np.random.default_rng(7)
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    cream = np.median(lab[60:75, 600:700].reshape(-1, 3), 0)
    dE = np.sqrt(((lab - cream) ** 2).sum(-1))
    tx0, ty0, tx1, ty1 = TOP_BAND

    # ---- bottom: LEDs, footswitches and the maker's mark painted out (the real controls cover most of it) ----------
    # LEDs and switches sit on horizontal wave bands: fill each row of the hole by mirroring the row in from both
    # sides and cross-fading (keeps the bands continuous at the edge; the middle is under the real control anyway)
    ctl = np.zeros((H, W), np.uint8)
    for c in LEDS:
        cv2.circle(ctl, c, 34, 255, -1)
    for cx, cy in FOOTS:
        cv2.circle(ctl, (cx, cy), 86, 255, -1)
        cv2.ellipse(ctl, (cx + 4, cy + 12), (90, 88), 0, 0, 360, 255, -1)
    filled = im.copy()
    vfill = lambda img, m, after_only=False: np.ascontiguousarray(
        mirror_fill(np.ascontiguousarray(img.transpose(1, 0, 2)), np.ascontiguousarray(m.T), after_only).transpose(1, 0, 2))
    fp = np.zeros((H, W), np.uint8)
    r = BRAND[1]                                                        # maker's mark: the footprint (row by row),
    cv2.rectangle(fp, (r[0], r[1]), (r[2], BRAND[0][1] - 1), 255, -1)
    filled = mirror_fill(filled, fp > 0)
    fp[:] = 0                                                           # then the lettering on the sand (column by column)
    cv2.rectangle(fp, BRAND[0][:2], BRAND[0][2:], 255, -1)
    filled = vfill(filled, fp > 0)
    cap = np.zeros((H, W), bool)                                        # bottom of each switch hole: on the sand,
    for cx, cy in FOOTS:                                                # filled column by column (no wave bands)
        cap[cy + 55:, cx - 94:cx + 98] = True
    cap &= ctl > 0
    filled = mirror_fill(filled, (ctl > 0) & ~cap)
    for r in FOOT_LABELS:                                               # + the BOOST / EQ lettering under them
        cap[r[1]:r[3] + 1, r[0]:r[2] + 1] = True
    cap = cv2.morphologyEx(cap.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 1), np.uint8)) > 0   # no gaps in a column
    filled = vfill(filled, cap, True)                                   # from the sand below only

    # ---- top band: smooth cream colour field (elements removed) for unmixing the printed elements --------------
    topel = np.zeros((H, W), np.uint8)
    topel[ty0:ty1, tx0:tx1] = (dE[ty0:ty1, tx0:tx1] > 16).astype(np.uint8) * 255
    for cx, cy in KNOBS:
        cv2.circle(topel, (cx, cy), 110, 255, -1)
        cv2.ellipse(topel, (cx + 2, cy + 16), (114, 112), 0, 0, 360, 255, -1)   # and its soft shadow
    cv2.rectangle(topel, (712, 88), (830, 314), 255, -1)
    topel = cv2.dilate(cv2.morphologyEx(topel, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)), np.ones((7, 7), np.uint8))
    wc = ((topel == 0) & (dE < 16)).astype(np.float32)               # clean cream only (no letters, coral, sun)
    wc[:ty0] = 0; wc[ty1:] = 0; wc[:, :tx0] = 0; wc[:, tx1:] = 0
    field = None                                                     # normalized convolution, coarser where sparse
    for sig in (160, 80):                                            # broad: keeps the left-right tint, not the knobs' shading
        num = cv2.GaussianBlur(im.astype(np.float32) * wc[..., None], (0, 0), sig)
        den = cv2.GaussianBlur(wc, (0, 0), sig)
        f = num / np.maximum(den, 1e-6)[..., None]
        if field is None:
            field = f
        else:
            k = np.clip(den / 0.25, 0, 1)[..., None]                    # trust the finer scale where well supported
            field = field * (1 - k) + f * k
    hf = im.astype(np.float32) - cv2.GaussianBlur(im.astype(np.float32), (0, 0), 4)
    hf_ok = np.zeros((H, W), bool)
    hf_ok[ty0:ty1, tx0:tx1] = True
    hf_ok &= topel == 0

    # printed elements of the control rows: alpha from the colour distance to cream, unmixed against the field
    def sprite(box, hole=None):
        bx0, by0, bx1, by1 = box
        L = lab[by0:by1, bx0:bx1]
        chroma = np.sqrt((L[..., 1] - cream[1]) ** 2 + (L[..., 2] - cream[2]) ** 2)
        dark = cream[0] - L[..., 0]                                     # ink is coloured or dark; the white knob
        a = np.clip(np.maximum((chroma - 20.0) / 15.0, (dark - 50.0) / 25.0), 0, 1)   # and its soft shadow are neither
        rows, cols = np.arange(by0, by1)[:, None], np.arange(bx0, bx1)[None, :]
        a[(rows >= 318) & (cols >= 1092) & (cols < 1262)] = 0             # not the sun's top
        if hole is not None:
            hm = np.zeros(a.shape, np.uint8)
            if hole[0] == "knob":
                _, cx, cy = hole
                cv2.circle(hm, (cx - bx0, cy - by0), 104, 1, -1)
                cv2.ellipse(hm, (cx - bx0 + 2, cy - by0 + 14), (106, 104), 0, 0, 360, 1, -1)
                a[(hm > 0) & (chroma < 25)] = 0          # knob, pointer, outline, shadow: neutral; the dot scale is coloured
                hm[:] = 0
            else:
                cv2.rectangle(hm, (hole[1] - bx0, hole[2] - by0), (hole[3] - bx0, hole[4] - by0), 1, -1)
            a[hm > 0] = 0
        o = im[by0:by1, bx0:bx1].astype(np.float32); b = field[by0:by1, bx0:bx1]
        col = np.clip(b + (o - b) / np.maximum(a, 0.35)[..., None], 0, 255)
        return col, a

    groups = []                                                        # (colour, alpha, box, anchor)
    for (cx, cy), (px, py) in zip(KNOBS, PAINTED):
        box = (cx - 135, 60, cx + 135, 342)                            # dot scale + label (not the title below)
        groups.append((*sprite(box, ("knob", px, py)), box, (cx, cy)))
    # dot scales: the painted knobs hid parts of some dots -> redraw all nine of each scale from one clean dot
    def dot_template(gi, ang):
        col, a, (bx0, by0, _, _), (cx, cy) = groups[gi]
        x = cx + DOT_R * np.sin(np.radians(ang)) - bx0; y = cy - DOT_R * np.cos(np.radians(ang)) - by0
        x0, y0 = int(round(x)) - 13, int(round(y)) - 13
        return col[y0:y0 + 27, x0:x0 + 27].copy(), a[y0:y0 + 27, x0:x0 + 27].copy()
    templates = [dot_template(1, 31.6), dot_template(2, 0.0)]              # red (LEVEL), teal (LOW)
    for gi, (col, a, (bx0, by0, bx1, by1), (cx, cy)) in enumerate(groups):
        yy, xx = np.mgrid[by0:by1, bx0:bx1]
        rr = np.hypot(xx - cx, yy - cy)
        a[(rr > 92) & (rr < 128) & (yy < cy + 100)] = 0
        tc, ta = templates[0 if gi < 2 else 1]
        for ang in DOT_ANGLES:
            x = cx + DOT_R * np.sin(np.radians(ang)) - bx0; y = cy - DOT_R * np.cos(np.radians(ang)) - by0
            x0, y0 = int(round(x)) - 13, int(round(y)) - 13
            m = ta > a[y0:y0 + 27, x0:x0 + 27]
            a[y0:y0 + 27, x0:x0 + 27][m] = ta[m]; col[y0:y0 + 27, x0:x0 + 27][m] = tc[m]
    box = (708, 86, 832, 316)
    groups.append((*sprite(box, ("rect", 720, 124, 828, 244)), box, TOGGLE))
    # footswitch labels: unmixed against the inpainted beach, re-placed at their own (stretched) centre
    for r in FOOT_INK:
        bx0, by0, bx1, by1 = r
        lo = lab[by0:by1, bx0:bx1]; lb = cv2.cvtColor(filled, cv2.COLOR_BGR2LAB).astype(np.float32)[by0:by1, bx0:bx1]
        chroma = np.sqrt(((lo[..., 1:] - lb[..., 1:]) ** 2).sum(-1)); dark = lb[..., 0] - lo[..., 0]
        dv = lo[..., 1:] - lb[..., 1:]
        ink = np.median(dv[chroma > np.percentile(chroma, 90)], 0)          # the label's ink direction (red / teal)
        cosv = (dv @ ink) / (np.linalg.norm(dv, axis=-1) * np.linalg.norm(ink) + 1e-6)
        a = np.clip((chroma - 15.0) / 15.0, 0, 1) * np.clip((cosv - 0.75) / 0.15, 0, 1)   # that ink only
        o = im[by0:by1, bx0:bx1].astype(np.float32); b = filled[by0:by1, bx0:bx1].astype(np.float32)
        col = np.clip(b + (o - b) / np.maximum(a, 0.35)[..., None], 0, 255)
        groups.append((col, a, r, ((bx0 + bx1) // 2, (by0 + by1) // 2)))

    # ---- stretch ---------------------------------------------------------------------------------------------------
    ymap = ymap_table(H)
    outH = int(round(ymap[H]))
    inv = np.interp(np.arange(outH) + 0.5, ymap, np.arange(H + 1)) - 0.5   # output row centre -> source row
    mapx = np.tile(np.arange(W, dtype=np.float32), (outH, 1))
    mapy = np.repeat(inv.astype(np.float32)[:, None], W, 1)
    big = cv2.remap(filled, mapx, mapy, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    bigfield = cv2.remap(field, mapx, mapy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    Y = lambda y: float(np.interp(y + 0.5, np.arange(H + 1), ymap) - 0.5)   # source row -> output row

    # top band repainted as plain cream at the new size (no stretched speckle), feathered into its surroundings
    oy0, oy1 = int(round(Y(ty0))), int(round(Y(ty1)))
    cream_new = synth_cream(bigfield[oy0:oy1, tx0:tx1], hf, hf_ok, (oy1 - oy0, tx1 - tx0), rng)
    wmask = np.zeros((outH, W), np.float32)
    wmask[oy0:oy1, tx0:tx1] = 1.0
    sun = np.zeros((outH, W), np.float32)                               # keep the sun's top and the coral tips
    srcband = np.zeros((H, W), np.uint8)
    srcband[ty0:ty1, tx0:tx1] = ((dE[ty0:ty1, tx0:tx1] > 14) & (np.arange(ty0, ty1)[:, None] > 318)).astype(np.uint8)
    for cx, cy in KNOBS:                                                # (labels reach down to ~340: not the sun)
        cv2.rectangle(srcband, (cx - 135, 290), (cx + 135, ty1), 0, -1)
    sun = cv2.remap(cv2.dilate(srcband, np.ones((9, 9), np.uint8)).astype(np.float32), mapx, mapy, cv2.INTER_LINEAR)
    oys = int(round(Y(322)))                                          # the sun's top stays as painted
    wmask[oys:, 1092:1262] = 0.0
    wmask = cv2.GaussianBlur(wmask, (0, 0), 3) * (1 - np.clip(sun, 0, 1))
    region = big[oy0:oy1, tx0:tx1]
    wm = wmask[oy0:oy1, tx0:tx1, None]
    big[oy0:oy1, tx0:tx1] = region * (1 - wm) + cream_new * wm

    for col, a, (bx0, by0, bx1, by1), (ax, ay) in groups:
        dy = int(round(Y(ay) - ay))                                     # the group moves with its control
        sl = big[by0 + dy:by1 + dy, bx0:bx1]
        sl[:] = sl * (1 - a[..., None]) + col * a[..., None]

    # crop the flat top
    c0, c1 = int(round(Y(CROP[1]))), int(round(Y(CROP[3])))
    art = big[c0:c1, CROP[0]:CROP[2]]
    artW = CROP[2] - CROP[0]
    target = round(artW * (BODY_H - 2 * INSET) / (BODY_W - 2 * INSET))
    print("stretched height", art.shape[0], "target", target)
    art = cv2.resize(art, (artW, target), interpolation=cv2.INTER_AREA if art.shape[0] > target else cv2.INTER_CUBIC)
    # the mock-up's own rounded enclosure rim (and the white page) show in the corners: cut the print just outside the
    # printed frame line with rounded corners, so the enclosure's cream paint shows there (alpha, antialiased)
    th, tw = art.shape[:2]
    m4 = np.zeros((th * 4, tw * 4), np.uint8)
    x0m, y0m, x1m, y1m, rad = 2 * 4, 4 * 4, (tw - 4) * 4, (th - 4) * 4, 26 * 4
    cv2.rectangle(m4, (x0m + rad, y0m), (x1m - rad, y1m), 255, -1)
    cv2.rectangle(m4, (x0m, y0m + rad), (x1m, y1m - rad), 255, -1)
    for cx, cy in ((x0m + rad, y0m + rad), (x1m - rad, y0m + rad), (x0m + rad, y1m - rad), (x1m - rad, y1m - rad)):
        cv2.circle(m4, (cx, cy), rad, 255, -1)
    alpha = cv2.resize(m4, (tw, th), interpolation=cv2.INTER_AREA)
    rgba = np.dstack([cv2.cvtColor(np.clip(art, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB), alpha])
    Image.fromarray(rgba, "RGBA").save(out, optimize=True)
    print("art", (artW, target), "aspect W/H %.4f" % (artW / target))
    return Y, art.shape[0] / (c1 - c0), c0


def fractions(Y=None, ky=1.0, c0=0.0):
    """Body fractions for FaceLayout (x of W, y of H): the art is printed INSET mm inside the 186.8 x 149.8 mm body."""
    if Y is None:
        Y = lambda y: y
    artW = CROP[2] - CROP[0]
    fx = lambda x: INSET / BODY_W + (x - CROP[0]) / artW * (BODY_W - 2 * INSET) / BODY_W
    def fy(y):
        yo = (Y(y) - c0) * ky                                           # output art row
        artH = artW * (BODY_H - 2 * INSET) / (BODY_W - 2 * INSET)
        return INSET / BODY_H + yo / artH * (BODY_H - 2 * INSET) / BODY_H
    fd = lambda d: d / artW * (BODY_W - 2 * INSET) / BODY_W
    return fx, fy, fd


if __name__ == "__main__":
    Y, ky, c0 = build(sys.argv[1], sys.argv[2])
    fx, fy, fd = fractions(Y, ky, c0)
    print("knob d %.4fW" % fd(KNOB_D), "footswitch %.4fW" % fd(FOOT_D))
    for name, (x, y) in zip(["BOOST", "LEVEL", "LOW", "HIGH"], KNOBS):
        print("knob", name, (round(fx(x), 4), round(fy(y), 4)))
    print("toggle", (round(fx(TOGGLE[0]), 4), round(fy(TOGGLE[1]), 4)))
    for name, (x, y) in zip(["BOOST", "EQ"], LEDS):
        print("led", name, (round(fx(x), 4), round(fy(y), 4)))
    for name, (x, y) in zip(["BOOST", "EQ"], FOOTS):
        print("footswitch", name, (round(fx(x), 4), round(fy(y), 4)))
