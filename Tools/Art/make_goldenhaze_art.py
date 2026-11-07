"""Builds Assets/goldenhaze_art.png from Michael's Golden Haze artwork (Tools/Art/goldenhaze_original.png).

The template paints three knobs (LEVEL / TONE / FUZZ), but the Acapulco Gold circuit has a single VOLUME knob. So:
  - the LEVEL and FUZZ knobs and all three labels are painted out with exemplar (patch-copy) inpainting, which
    continues the speckled black-and-gold paint and the swirls instead of smearing them;
  - the painted TONE knob, the footswitch and the LED are painted out too (the real controls go exactly there);
  - "VOLUME" is printed over the centre knob in the art's spaced sans caps (Barlow Medium, OFL);
  - the bottom line "FUZZ - OVERDRIVE - HIGHER GROUND" becomes "POWER AMP - DISTORTION - HIGHER GROUND".
Only numpy, opencv-python (core, no contrib) and pillow are needed. Run from C:\\Dev\\pedalfactory-master:
    python Tools/Art/make_goldenhaze_art.py Tools/Art/goldenhaze_original.png Tools/Art/fonts/Barlow-Medium.ttf Assets/goldenhaze_art.png
Source pixel coordinates below refer to the 1024 x 1536 original. Takes about a minute."""
import sys, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CROP = (70, 55, 954, 1441)                       # flat pedal top inside the bevelled rim (source px)
KNOBS = [(219, 254), (512, 256), (806, 254)]     # painted LEVEL / TONE / FUZZ knobs (centre of the skirt)
KNOB = KNOBS[1]                                  # the real VOLUME knob sits on the painted TONE knob
KNOB_D = 212                                     # painted knob skirt diameter
LED = (696, 1238)
FOOT = (510, 1234)
LABELS = [(160, 82, 286, 122), (460, 80, 566, 124), (756, 82, 858, 122)]           # LEVEL, TONE, FUZZ
TAG = (138, 1364, 892, 1397)                     # bottom line: words and the two rules
LABEL_Y, LABEL_CAP, LABEL_RGB = 103, 31, (219, 174, 91)
TAG_Y, TAG_CAP, TAG_RGB, RULE_RGB = 1380, 15, (192, 144, 60), (212, 162, 76)
TAG_WORDS = ("POWER AMP", "DISTORTION", "HIGHER GROUND")


def exemplar_inpaint(img, hole, patch=11, search=170, seed=5, dweight=0.0, allowed=None):
    """Exemplar (Criminisi-style) inpainting: fill the hole patch by patch from its edge inwards, each time copying the
    best-matching fully known patch from nearby (cv2.matchTemplate). dweight > 0 fills strong incoming structure
    first (Criminisi's data term); 0 = plain onion-peel order, which gave the cleanest result on this art (fewer
    big gold blocks). patch 11 / seed 5 chosen by eye from several runs. Results can differ slightly between
    machines (float matching ties), so the committed Assets/goldenhaze_art.png is the reference."""
    rng = np.random.default_rng(seed)
    im = img.astype(np.float32).copy()
    H, W = hole.shape
    h = patch // 2
    known = ~hole.copy()
    conf = known.astype(np.float32)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    src_ok = cv2.erode(known.astype(np.uint8), np.ones((patch, patch), np.uint8),
                       borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    if allowed is not None:                       # optional: only copy patches lying fully inside "allowed"
        src_ok &= cv2.erode(allowed.astype(np.uint8), np.ones((patch, patch), np.uint8),
                            borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    src_ok[:h + 1] = src_ok[-h - 1:] = False
    src_ok[:, :h + 1] = src_ok[:, -h - 1:] = False
    k3 = np.ones((3, 3), np.uint8)
    while not known.all():
        front = ~known & cv2.dilate(known.astype(np.uint8), k3).astype(bool)
        ys, xs = np.nonzero(front)
        cs = cv2.boxFilter(conf, -1, (patch, patch), normalize=True)
        # data term: strength of the isophotes arriving at the front
        g = np.where(known, gray, 0)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        inner = cv2.erode(known.astype(np.uint8), k3).astype(bool)
        gx[~inner] = 0; gy[~inner] = 0
        gx = cv2.dilate(np.abs(gx), np.ones((5, 5), np.uint8)) * np.sign(cv2.GaussianBlur(gx, (5, 5), 0) + 1e-9)
        gy = cv2.dilate(np.abs(gy), np.ones((5, 5), np.uint8)) * np.sign(cv2.GaussianBlur(gy, (5, 5), 0) + 1e-9)
        m = cv2.GaussianBlur(known.astype(np.float32), (0, 0), 2)
        nx = cv2.Sobel(m, cv2.CV_32F, 1, 0, ksize=3); ny = cv2.Sobel(m, cv2.CV_32F, 0, 1, ksize=3)
        D = np.abs(-gy * nx + gx * ny) / (np.sqrt(nx * nx + ny * ny) + 1e-6) / 255.0
        P = cs[ys, xs] * (dweight * D[ys, xs] + 0.05) * (1 + 0.01 * rng.random(len(ys)))
        picked = []                                   # a few well-separated top-priority points per round
        for j in np.argsort(-P)[:40]:
            y, x = int(ys[j]), int(xs[j])
            if any(abs(y - a) < patch and abs(x - b) < patch for a, b in picked): continue
            picked.append((y, x))
            if len(picked) >= 6: break
        for y, x in picked:
            y0, y1, x0, x1 = max(y - h, 0), min(y + h + 1, H), max(x - h, 0), min(x + h + 1, W)
            tgt = im[y0:y1, x0:x1]; tk = known[y0:y1, x0:x1]
            sy0, sy1, sx0, sx1 = max(y - search, 0), min(y + search + 1, H), max(x - search, 0), min(x + search + 1, W)
            win = im[sy0:sy1, sx0:sx1]
            ssd = cv2.matchTemplate(win, tgt, cv2.TM_SQDIFF, mask=np.repeat(tk[..., None], 3, 2).astype(np.float32))
            cy0, cx0 = sy0 + (y - y0), sx0 + (x - x0)
            valid = np.zeros(ssd.shape, bool)
            vv = src_ok[cy0:cy0 + ssd.shape[0], cx0:cx0 + ssd.shape[1]]
            valid[:vv.shape[0], :vv.shape[1]] = vv
            ssd = np.where(valid, ssd, np.inf)
            flat = ssd.ravel()
            if not np.isfinite(flat).any(): continue
            best = np.argpartition(flat, 3)[:4]
            best = best[np.isfinite(flat[best])]
            b = best[np.argsort(flat[best])][min(len(best) - 1, int(rng.integers(0, 2)))]   # 1st or 2nd best
            by, bx = np.unravel_index(b, ssd.shape)
            src = win[by:by + tgt.shape[0], bx:bx + tgt.shape[1]]
            fill = ~tk
            tgt[fill] = src[fill]
            conf[y0:y1, x0:x1][fill] = cs[y, x]
            known[y0:y1, x0:x1] |= fill
    return np.clip(im, 0, 255).astype(np.uint8)


def fractions():
    """Body fractions (x of W, y of H) for FaceLayout: the art is printed 2.6 mm inside the 91 x 149.8 mm body."""
    W, H, M = 91.0, 91.0 * 372 / 226, 2.6
    fx = lambda x: M / W + (x - CROP[0]) / (CROP[2] - CROP[0]) * (W - 2 * M) / W
    fy = lambda y: M / H + (y - CROP[1]) / (CROP[3] - CROP[1]) * (H - 2 * M) / H
    fd = lambda d: d / (CROP[2] - CROP[0]) * (W - 2 * M) / W
    return fx, fy, fd


def build(src, font_path, out):
    im = cv2.cvtColor(np.array(Image.open(src).convert("RGB")), cv2.COLOR_RGB2BGR)
    mask = np.zeros(im.shape[:2], np.uint8)
    for cx, cy in KNOBS:
        cv2.circle(mask, (cx, cy), 124, 255, -1)                                  # skirt + dark halo
        cv2.ellipse(mask, (cx + 3, cy + 14), (124, 120), 0, 0, 360, 255, -1)     # contact shadow below
    for r in LABELS:
        cv2.rectangle(mask, r[:2], r[2:], 255, -1)
    cv2.circle(mask, FOOT, 106, 255, -1)
    cv2.ellipse(mask, (FOOT[0] + 4, FOOT[1] + 10), (104, 102), 0, 0, 360, 255, -1)
    cv2.circle(mask, LED, 46, 255, -1)
    cv2.rectangle(mask, TAG[:2], TAG[2:], 255, -1)
    filled = im.copy()
    for (x0, y0, x1, y1) in [(CROP[0], CROP[1], CROP[2], 620), (CROP[0], 1040, CROP[2], CROP[3])]:
        filled[y0:y1, x0:x1] = exemplar_inpaint(filled[y0:y1, x0:x1], mask[y0:y1, x0:x1] > 0)
    art = Image.fromarray(cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)).crop(CROP)

    W, H, M = 91.0, 91.0 * 372 / 226, 2.6
    ow = 1200; oh = round(ow * (H - 2 * M) / (W - 2 * M))
    art = art.resize((ow, oh), Image.LANCZOS).convert("RGBA")
    sx, sy = ow / (CROP[2] - CROP[0]), oh / (CROP[3] - CROP[1])
    rng = np.random.default_rng(3)

    def text_layer(text, cap, rgb, track):
        """Printed caps like the art's labels: spaced, flat ink with a little wear. Returns (RGBA image, width)."""
        font = ImageFont.truetype(font_path, 200)
        capH = font.getbbox("H")[3] - font.getbbox("H")[1]
        font = ImageFont.truetype(font_path, max(8, int(round(cap * sy / capH * 200))))
        sp = track * font.size
        tmp = Image.new("L", (int(font.size * len(text) * 1.3 + 40), int(font.size * 1.6)), 0)
        d = ImageDraw.Draw(tmp)
        x = 10
        for c in text:
            d.text((x, font.size * 0.8), c, font=font, fill=255, anchor="lm")
            x += d.textlength(c, font=font) + sp
        tmp = tmp.crop(tmp.getbbox())
        tmp = tmp.resize((max(1, round(tmp.width * sx / sy)), tmp.height), Image.LANCZOS)   # undo the art's stretch
        a = np.array(tmp).astype(np.float32) / 255
        wear = cv2.GaussianBlur(rng.random(a.shape).astype(np.float32), (0, 0), 0.8)
        a *= np.clip(0.55 + wear * 0.9, 0, 1)                                    # slightly worn print
        shade = 1.0 - 0.10 * rng.random(a.shape)
        rgbA = np.stack([np.full(a.shape, c, np.float32) * shade for c in rgb], -1)
        return Image.fromarray(np.dstack([np.clip(rgbA, 0, 255), a * 255]).astype(np.uint8), "RGBA")

    def put(layer, cx, cy):
        art.alpha_composite(layer, (int(round((cx - CROP[0]) * sx - layer.width / 2)),
                                    int(round((cy - CROP[1]) * sy - layer.height / 2))))

    put(text_layer("VOLUME", LABEL_CAP, LABEL_RGB, 0.16), KNOB[0], LABEL_Y)

    # bottom line: three phrases with a rule between each pair, spread over the original line's width
    words = [text_layer(w, TAG_CAP, TAG_RGB, 0.14) for w in TAG_WORDS]
    span = (TAG[2] - TAG[0] - 12) * sx
    gap = (span - sum(w.width for w in words)) / 2
    x = (TAG[0] + 6 - CROP[0]) * sx
    yc = (TAG_Y - CROP[1]) * sy
    d = ImageDraw.Draw(art)
    for i, w in enumerate(words):
        art.alpha_composite(w, (int(round(x)), int(round(yc - w.height / 2))))
        x += w.width
        if i < 2:
            pad = gap * 0.16
            d.rectangle([x + pad, yc - 0.65 * sy, x + gap - pad, yc + 0.65 * sy], fill=RULE_RGB + (235,))
            x += gap
    art.convert("RGB").save(out, optimize=True)
    print("art", art.size, "aspect", art.size[1] / art.size[0])


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        build(*sys.argv[1:4])
    fx, fy, fd = fractions()
    print("knob d %.4fW at" % fd(KNOB_D), (round(fx(KNOB[0]), 4), round(fy(KNOB[1]), 4)))
    print("LED", (round(fx(LED[0]), 4), round(fy(LED[1]), 4)), "footswitch", (round(fx(FOOT[0]), 4), round(fy(FOOT[1]), 4)))
