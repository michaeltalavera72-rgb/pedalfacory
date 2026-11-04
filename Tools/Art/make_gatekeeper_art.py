"""Builds Assets/gatekeeper_art.png from Michael's Gatekeeper artwork (Tools/Art/gatekeeper_original.png):
crop the pedal top, paint out the painted knobs / LED / footswitch (the rendered ones go exactly there, see
FaceLayout.h Gatekeeper branch / render_gatekeeper.py), print HARD / SOFT around the range toggle (Cinzel, OFL).
Run from C:\\Dev\\pedalfactory-master (needs numpy, opencv-python, pillow):
    python Tools/Art/make_gatekeeper_art.py Tools/Art/gatekeeper_original.png "Tools/Art/fonts/Cinzel[wght].ttf" Assets/gatekeeper_art.png
Source pixel coordinates below refer to the 1024 x 1536 original."""
import sys, numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter
src, font_path, out = sys.argv[1:4]
CROP = (88, 50, 936, 1430)                     # pedal top inside the worn rim (source px)
im = cv2.cvtColor(np.array(Image.open(src).convert("RGB")), cv2.COLOR_RGB2BGR)
x0, y0 = CROP[:2]
mask = np.zeros(im.shape[:2], np.uint8)
for (cx, cy, r) in [(223, 200, 104), (804, 200, 104), (512, 1057, 36), (511, 1191, 97)]:
    cv2.circle(mask, (cx, cy), r, 255, -1)
# knob shadows fall down-right a little
for cx in (223, 804): cv2.ellipse(mask, (cx + 4, 210), (106, 106), 0, 0, 360, 255, -1)
filled = cv2.inpaint(im, mask, 9, cv2.INPAINT_TELEA)
# put grain back into the painted-out discs (inpaint is smooth): borrow texture from a ring around each disc
rng = np.random.default_rng(3)
noise = rng.normal(0, 1, im.shape[:2]).astype(np.float32)
noise = cv2.GaussianBlur(noise, (0, 0), 1.2) * 16.0
m = cv2.GaussianBlur(mask.astype(np.float32) / 255, (0, 0), 3)[..., None]
filled = np.clip(filled.astype(np.float32) + noise[..., None] * m, 0, 255).astype(np.uint8)
art = Image.fromarray(cv2.cvtColor(filled, cv2.COLOR_BGR2RGB)).crop(CROP)

# target shape = the printed area on the pedal (body 91 x 149.8 mm minus 2.6 mm each side)
W, H, M = 91.0, 91.0 * 372 / 226, 2.6
ow = 1200; oh = round(ow * (H - 2 * M) / (W - 2 * M))
art = art.resize((ow, oh), Image.LANCZOS)

# HARD / SOFT around the toggle, in the artwork's engraved-silver caps style
sx, sy = ow / (CROP[2] - CROP[0]), oh / (CROP[3] - CROP[1])
font = ImageFont.truetype(font_path, int(30 * sx)); font.set_variation_by_axes([700])
def label(text, cx, cy):
    cx, cy = (cx - x0) * sx, (cy - y0) * sy
    lay = Image.new("RGBA", art.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    sp = 0.18 * font.size
    ws = [d.textlength(c, font=font) for c in text]; tw = sum(ws) + sp * (len(text) - 1)
    x = cx - tw / 2
    shadow = Image.new("RGBA", art.size, (0, 0, 0, 0)); ds = ImageDraw.Draw(shadow)
    for c, w in zip(text, ws):
        ds.text((x + 2, cy + 2), c, font=font, fill=(0, 0, 0, 230), anchor="lm")
        d.text((x, cy), c, font=font, fill=(206, 204, 200, 255), anchor="lm"); x += w + sp
    # worn print: knock random specks out of the letters
    a = np.array(lay); spec = rng.random(a.shape[:2]) < 0.10
    a[..., 3] = np.where(spec, (a[..., 3] * 0.35).astype(np.uint8), a[..., 3])
    a[..., :3] = np.clip(a[..., :3].astype(int) - (rng.random(a.shape[:2])[..., None] * 40).astype(int), 0, 255)
    lay = Image.fromarray(a)
    return shadow.filter(ImageFilter.GaussianBlur(2)), lay
art = art.convert("RGBA")
for t, cy in (("HARD", 1108), ("SOFT", 1274)):
    sh, lay = label(t, 270, cy)
    art.alpha_composite(sh); art.alpha_composite(lay)
art.convert("RGB").save(out, optimize=True)
print("art", art.size, "aspect", art.size[1] / art.size[0])
