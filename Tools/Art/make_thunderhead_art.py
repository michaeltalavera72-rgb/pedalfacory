"""Builds Assets/thunderhead_art.png from Michael's Thunderhead artwork (Tools/Art/thunderhead_original.png):
crop the pedal top, paint out the painted knobs / TONE + LEVEL labels / LED / footswitch (the real controls go
exactly there, see FaceLayout.h 7-knob branch / render_thunderhead.py), then print the labels the VH4 model needs
in a slab serif matching the art's GAIN (Bitter, OFL): DEEP / VOLUME over the big knobs, BASS / MIDDLE and
TREBLE / PRESENCE under the four small knobs either side of the storm face, AMP / DIRECT at the output toggle.
Run from C:\\Dev\\pedalfactory-master (needs numpy, opencv-python, pillow):
    python Tools/Art/make_thunderhead_art.py Tools/Art/thunderhead_original.png "Tools/Art/fonts/Bitter[wght].ttf" Assets/thunderhead_art.png
Source pixel coordinates below refer to the 1024 x 1536 original."""
import sys, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CROP = (72, 60, 948, 1442)                      # flat pedal top inside the bevelled edge (source px)
# controls (source px) - FaceLayout.h numKnobs == 7 is derived from these (see fractions() below)
BIG = [(222, 262), (512, 262), (802, 262)]      # GAIN / DEEP / VOLUME, centred on the painted knobs' silhouettes
BIG_D = 213
SMALL = [(142, 486), (290, 486), (732, 486), (878, 486)]   # BASS / MIDDLE | TREBLE / PRESENCE
SMALL_D = 121
LED = (511, 1098)
FOOT = (508, 1254)
TOGGLE = (250, 1250)
LABEL_BIG_Y, LABEL_BIG_CAP = 120, 34            # painted GAIN: cap height 34 px, centred at y 120
LABEL_SMALL_Y, LABEL_SMALL_CAP = 570, 18


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
    for cx, cy in BIG:
        cv2.circle(mask, (cx, cy), 118, 255, -1)
        cv2.ellipse(mask, (cx + 2, cy + 8), (116, 118), 0, 0, 360, 255, -1)   # skirt + contact shadow
    cv2.rectangle(mask, (450, 96), (572, 143), 255, -1)       # TONE
    cv2.rectangle(mask, (731, 96), (870, 143), 255, -1)       # LEVEL
    cv2.circle(mask, LED, 33, 255, -1)
    cv2.circle(mask, FOOT, 101, 255, -1)
    cv2.ellipse(mask, (FOOT[0] + 4, FOOT[1] + 8), (100, 100), 0, 0, 360, 255, -1)
    filled = cv2.inpaint(im, mask, 9, cv2.INPAINT_TELEA)
    rng = np.random.default_rng(7)
    noise = rng.normal(0, 1, im.shape[:2]).astype(np.float32)
    noise = cv2.GaussianBlur(noise, (0, 0), 1.2) * 14.0
    m = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), 3)[..., None]
    filled = np.clip(filled.astype(np.float32) + noise[..., None] * m, 0, 255).astype(np.uint8)
    art = Image.fromarray(cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)).crop(CROP)

    W, H, M = 91.0, 91.0 * 372 / 226, 2.6
    ow = 1200; oh = round(ow * (H - 2 * M) / (W - 2 * M))
    art = art.resize((ow, oh), Image.LANCZOS).convert("RGBA")
    sx, sy = ow / (CROP[2] - CROP[0]), oh / (CROP[3] - CROP[1])

    def label(text, cx, cy, cap):
        """Engraved-silver slab caps like the art's GAIN: condensed, spaced, light top / darker bottom, worn."""
        font = ImageFont.truetype(font_path, 200); font.set_variation_by_axes([680])
        capH = font.getbbox("H")[3] - font.getbbox("H")[1]
        size = cap * sy / capH * 200
        font = ImageFont.truetype(font_path, int(round(size))); font.set_variation_by_axes([680])
        squeeze = 0.84
        sp = 0.08 * font.size
        tmp = Image.new("L", (int(font.size * len(text) * 1.2 + 40), int(font.size * 1.6)), 0)
        d = ImageDraw.Draw(tmp)
        x = 10
        for c in text:
            d.text((x, font.size * 0.8), c, font=font, fill=255, anchor="lm")
            x += d.textlength(c, font=font) + sp
        bb = tmp.getbbox(); tmp = tmp.crop(bb)
        tmp = tmp.resize((max(1, int(tmp.width * squeeze)), int(tmp.height * sy / sy * 1.0)), Image.LANCZOS)
        a = np.array(tmp).astype(np.float32) / 255
        h, w = a.shape
        grad = np.linspace(240, 178, h)[:, None] * np.ones((1, w))                 # light top, darker bottom
        grad -= rng.random((h, w)) * 34
        rgb = np.stack([grad * 0.98, grad * 0.99, grad * 1.02], -1)
        spec = rng.random((h, w)) < 0.09                                              # worn specks
        a = np.where(spec, a * 0.35, a)
        lay = Image.fromarray(np.dstack([np.clip(rgb, 0, 255), a * 255]).astype(np.uint8), "RGBA")
        px = int(round((cx - CROP[0]) * sx - w / 2)); py = int(round((cy - CROP[1]) * sy - h / 2))
        shadow = Image.new("RGBA", art.size, (0, 0, 0, 0))
        sh = Image.new("RGBA", lay.size, (0, 0, 0, 0)); sh.putalpha(Image.fromarray((np.array(tmp) * 0.9).astype(np.uint8)))
        shadow.alpha_composite(sh, (px + 3, py + 3))
        art.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(2.5)))
        art.alpha_composite(lay, (px, py))

    label("DEEP", BIG[1][0], LABEL_BIG_Y, LABEL_BIG_CAP)
    label("VOLUME", BIG[2][0], LABEL_BIG_Y, LABEL_BIG_CAP)
    for t, (cx, _) in zip(("BASS", "MIDDLE", "TREBLE", "PRESENCE"), SMALL):
        label(t, cx, LABEL_SMALL_Y, LABEL_SMALL_CAP)
    label("AMP", TOGGLE[0], TOGGLE[1] - 103, LABEL_SMALL_CAP)
    label("DIRECT", TOGGLE[0], TOGGLE[1] + 103, LABEL_SMALL_CAP)
    art.convert("RGB").save(out, optimize=True)
    print("art", art.size, "aspect", art.size[1] / art.size[0])


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        build(*sys.argv[1:4])
    fx, fy, fd = fractions()
    print("big knobs   d %.4fW at" % fd(BIG_D), [(round(fx(x), 4), round(fy(y), 4)) for x, y in BIG])
    print("small knobs d %.4fW at" % fd(SMALL_D), [(round(fx(x), 4), round(fy(y), 4)) for x, y in SMALL])
    print("LED", (round(fx(LED[0]), 4), round(fy(LED[1]), 4)), "footswitch", (round(fx(FOOT[0]), 4), round(fy(FOOT[1]), 4)),
          "toggle", (round(fx(TOGGLE[0]), 4), round(fy(TOGGLE[1]), 4)))
