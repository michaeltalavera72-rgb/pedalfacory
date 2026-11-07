"""Builds Assets/nightcourier_art.png from Michael's Night Courier artwork (Tools/Art/nightcourier_original.png).

The artwork already prints every label the model needs (Time / Repeats / Mix / Reverb, Mod / Tone, the
Delay / Reverb / Both toggle, BYPASS, the name), so nothing is re-lettered. The script:
  - paints out the six painted knobs, the toggle, the left LED and the BYPASS footswitch (the real controls are
    rendered exactly there), and the second footswitch, its LED and its PRESET label (Night Courier has one
    footswitch), with the exemplar inpainter from make_goldenhaze_art.py;
  - crops the flat top inside the enclosure's lit edge and scales it to the plugin's art width WITHOUT
    stretching (the original is squatter than our 226 x 372 body): the missing height is added as plain matte
    black above and below (same mean / grain as the adjacent rows, feathered), so knobs and dot rings stay round.
Run from C:\\Dev\\pedalfactory-master (numpy, opencv-python, pillow):
    python Tools/Art/make_nightcourier_art.py Tools/Art/nightcourier_original.png Assets/nightcourier_art.png
Source pixel coordinates below refer to the 1024 x 1536 original."""
import os, sys, numpy as np, cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_goldenhaze_art import exemplar_inpaint

CROP = (52, 66, 972, 1440)                       # flat top inside the lit edge / bottom bevel (source px)
BIG = [(175, 245), (395, 243), (630, 243), (855, 243)]     # TIME, REPEATS, MIX, REVERB (painted knob centres)
BIG_D = 150
SMALL = [(255, 505), (770, 505)]                 # MOD, TONE
SMALL_D = 132
TOGGLE = (513, 563)                              # Delay / Reverb / Both
LED = (182, 1163)
FOOT = (180, 1288)                               # BYPASS
GONE_LED, GONE_FOOT, GONE_LABEL = (845, 1163), (845, 1290), (778, 1378, 908, 1416)   # PRESET switch: removed
PLAIN = (612, 1228, 752, 1308)                   # plain matte paint: grain source for the removed switch

OW = 1200                                        # output width (px); height from the 226 x 372 body minus the 2.6 mm inset
W_MM, H_MM, M_MM = 91.0, 91.0 * 372 / 226, 2.6
OH = round(OW * (H_MM - 2 * M_MM) / (W_MM - 2 * M_MM))
S = OW / (CROP[2] - CROP[0])                     # uniform scale
PAD_TOP = (OH - round((CROP[3] - CROP[1]) * S)) // 2


def to_art(x, y):
    return (x - CROP[0]) * S, (y - CROP[1]) * S + PAD_TOP


def fractions():
    """Body fractions (x of W, y of H) for FaceLayout: the art is printed 2.6 mm inside the 91 x 149.8 mm body."""
    fx = lambda x: M_MM / W_MM + to_art(x, 0)[0] / OW * (W_MM - 2 * M_MM) / W_MM
    fy = lambda y: M_MM / H_MM + to_art(0, y)[1] / OH * (H_MM - 2 * M_MM) / H_MM
    fd = lambda d: d * S / OW * (W_MM - 2 * M_MM) / W_MM
    return fx, fy, fd


def build(src, out):
    im = cv2.cvtColor(np.array(Image.open(src).convert("RGB")), cv2.COLOR_RGB2BGR)
    mask = np.zeros(im.shape[:2], np.uint8)
    for (cx, cy), r in [(c, 80) for c in BIG] + [(c, 70) for c in SMALL]:
        cv2.circle(mask, (cx, cy), r, 255, -1)
        cv2.ellipse(mask, (cx + 2, cy + 5), (r - 1, r - 2), 0, 0, 360, 255, -1)      # contact shadow
    cv2.circle(mask, TOGGLE, 46, 255, -1)
    cv2.ellipse(mask, (TOGGLE[0] + 2, TOGGLE[1] + 5), (45, 44), 0, 0, 360, 255, -1)
    cv2.circle(mask, LED, 34, 255, -1)
    cv2.circle(mask, FOOT, 84, 255, -1)
    cv2.ellipse(mask, (FOOT[0] + 3, FOOT[1] + 7), (83, 82), 0, 0, 360, 255, -1)
    # the removed PRESET switch, its LED (with its glow on the paint) and label: plain matte paint there
    gone = np.zeros(im.shape[:2], np.uint8)
    led_gone = np.zeros(im.shape[:2], np.uint8)
    cv2.circle(led_gone, GONE_LED, 50, 255, -1)          # sits on the landscape edge: patch-copied (below)
    cv2.circle(gone, GONE_FOOT, 100, 255, -1)
    cv2.ellipse(gone, (GONE_FOOT[0] + 4, GONE_FOOT[1] + 10), (100, 98), 0, 0, 360, 255, -1)
    cv2.rectangle(gone, GONE_LABEL[:2], GONE_LABEL[2:], 255, -1)
    # never copy printed lettering / dot rings / symbols into the holes: exclude cream ink (bright, unsaturated)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    ink = ((hsv[..., 2] > 120) & (hsv[..., 1] < 70)).astype(np.uint8)
    allowed = cv2.dilate(ink, np.ones((9, 9), np.uint8)) == 0
    filled = im.copy()
    # the removed LED and its glow sit where the moonlit water meets the black paint: continue that texture
    lx0, ly0, lx1, ly1 = 640, 1000, CROP[2], 1250
    filled[ly0:ly1, lx0:lx1] = exemplar_inpaint(filled[ly0:ly1, lx0:lx1], led_gone[ly0:ly1, lx0:lx1] > 0, seed=4,
                                                allowed=allowed[ly0:ly1, lx0:lx1] & (mask[ly0:ly1, lx0:lx1] == 0))
    for (x0, y0, x1, y1) in [(CROP[0], CROP[1], CROP[2], 660), (CROP[0], 1040, CROP[2], CROP[3])]:
        filled[y0:y1, x0:x1] = exemplar_inpaint(filled[y0:y1, x0:x1], mask[y0:y1, x0:x1] > 0, seed=2,
                                                allowed=allowed[y0:y1, x0:x1])

    # the removed switch: plain matte paint = smooth shading (Telea on a blurred copy) + the real paint grain,
    # tiled (mirrored) from a plain patch left of it (PLAIN). Patch-copy filling made dark blocks here.
    f32 = filled.astype(np.float32)
    low = cv2.GaussianBlur(f32, (0, 0), 5)
    gone_d = cv2.dilate(gone, np.ones((13, 13), np.uint8))
    low_f = cv2.inpaint(np.clip(low, 0, 255).astype(np.uint8), gone_d, 30, cv2.INPAINT_TELEA).astype(np.float32)
    px0, py0, px1, py1 = PLAIN
    tex = (f32 - low)[py0:py1, px0:px1]
    tex = np.concatenate([tex, tex[:, ::-1]], 1); tex = np.concatenate([tex, tex[::-1]], 0)
    ys, xs = np.nonzero(gone_d)
    grain = np.zeros_like(f32)
    grain[ys, xs] = tex[(ys - ys.min()) % tex.shape[0], (xs - xs.min()) % tex.shape[1]]
    soft = cv2.GaussianBlur((gone_d > 0).astype(np.float32), (0, 0), 4)[..., None]
    filled = np.clip(f32 * (1 - soft) + (low_f + grain) * soft, 0, 255).astype(np.uint8)
    art = cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)[CROP[1]:CROP[3], CROP[0]:CROP[2]]
    art = np.array(Image.fromarray(art).resize((OW, round((CROP[3] - CROP[1]) * S)), Image.LANCZOS)).astype(np.float32)

    # extend with matte black above and below: per-column mean of the nearest 24 rows + matching fine grain
    rng = np.random.default_rng(4)
    canvas = np.zeros((OH, OW, 3), np.float32)
    h = art.shape[0]
    canvas[PAD_TOP:PAD_TOP + h] = art
    for top in (True, False):
        band = art[24:48] if top else art[-48:-24]                 # a little inside: the very edge rows are shaded
        # robust stats (the band can hold printed symbols): per-column median, grain from the median absolute deviation
        med = np.median(band, axis=0, keepdims=True).astype(np.float32)
        med = np.minimum(med, np.median(med, axis=1, keepdims=True) + 6.0)                  # no streaks above symbols
        mean = cv2.GaussianBlur(med, (0, 0), sigmaX=40)[0]                                  # (OW, 3)
        hp = (band - cv2.GaussianBlur(band, (0, 0), 3)).mean(2)
        std = float(1.4826 * np.median(np.abs(hp - np.median(hp))))
        n = PAD_TOP if top else OH - PAD_TOP - h
        grain = cv2.GaussianBlur(rng.normal(0, 1, (n + 32, OW)).astype(np.float32), (0, 0), 0.8)
        grain *= std / (grain.std() + 1e-6)
        fill = mean[None, :, :] + grain[..., None]
        if top:
            canvas[:n] = fill[:n]
            # feather the seam: blend 24 rows of the art into the fill
            for k in range(32):
                a = (k + 1) / 33.0
                canvas[n + k] = a * art[k] + (1 - a) * fill[n + k]
        else:
            canvas[PAD_TOP + h:] = fill[:n]
            for k in range(32):
                a = (k + 1) / 33.0
                canvas[PAD_TOP + h - 1 - k] = a * art[h - 1 - k] + (1 - a) * fill[n + k]
    Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8)).save(out, optimize=True)
    print("art", (OW, OH), "aspect", OH / OW, "pad", PAD_TOP)


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        build(*sys.argv[1:3])
    fx, fy, fd = fractions()
    print("big knobs   d %.4fW at" % fd(BIG_D), [(round(fx(x), 4), round(fy(y), 4)) for x, y in BIG])
    print("small knobs d %.4fW at" % fd(SMALL_D), [(round(fx(x), 4), round(fy(y), 4)) for x, y in SMALL])
    print("toggle", (round(fx(TOGGLE[0]), 4), round(fy(TOGGLE[1]), 4)), "LED", (round(fx(LED[0]), 4), round(fy(LED[1]), 4)),
          "footswitch", (round(fx(FOOT[0]), 4), round(fy(FOOT[1]), 4)))
