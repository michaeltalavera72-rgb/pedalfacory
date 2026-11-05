"""
Pedal Factory app icon - photoreal Blender render (Windows exe / taskbar icon).

A candy-orange metal-flake stompbox (three cream knurled knobs, red LED, chrome footswitch, side jacks,
"PEDAL FACTORY" printed on the face) standing on an invisible floor, seen from the front at a three-quarter
angle, with two steel factory gears standing behind it. Lighting, materials and wear come from
pedal_render_common.py, so it matches the pedal renders.

Two renders, both cropped to the object, centred on a transparent square and written at 1024 x 1024:
  * big   - pedal + gears + label   -> Assets/Icon/PedalFactory_icon_big.png   (JUCE ICON_BIG: 256 px+ icons)
  * small - pedal only, closer to top-down, no label -> Assets/Icon/PedalFactory_icon_small.png
            (JUCE ICON_SMALL: the 16-48 px taskbar / title-bar sizes, where the gears would just be noise)
Also writes Assets/Icon/PedalFactory.ico (16-256 px; small render up to 48 px, big render above) and saves
Tools/Blender/icon.blend. CMakeLists.txt already points ICON_BIG / ICON_SMALL at the two PNGs, so re-run
CMake and rebuild after rendering.

Run from C:\\Dev\\pedalfactory-master:
    & "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" -b -P Tools\\Blender\\render_icon.py
Options after "--":
    --quick            32 samples at 1024 px (check framing in a minute or two)
    --hdri=NAME.exr    another bundled studio light
    --exposure=+0.3    stops added after auto exposure (brighter +, darker -)
    --only=big|small   render just one of the two
"""
import math, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Assets", "Icon")
TMP = os.path.join(HERE, "_frames_icon")
FONT = os.path.join(ROOT, "Assets", "AlfaSlabOne-Regular.ttf")

# ----------------------------------------------------------------------------- design (mm)
W, H, DEPTH, CORNER = 66.0, 112.0, 32.0, 4.0           # chunky 1590B-ish enclosure
FLOOR = -DEPTH                                          # enclosure face is z = 0
ORANGE = (0.62, 0.115, 0.012, 1)                        # albedo darker than the look (AgX lifts it)
KNOB_R, KNOB_HEIGHT, KNOB_Y = 8.4, 11.0, 34.0
KNOBS = ((-20.5, -50.0), (0.0, 5.0), (20.5, 55.0))     # (x, pointer angle deg, clockwise from 12 o'clock)
LED_XY, LED_R = (0.0, 14.0), 2.7
LED_GLOW_W = 60.0                                       # red point light that tints the paint around the LED
LABEL_RECT = (0.0, 2.0, 50.0, 6.0)                      # cx, cy, w, h (big icon only)
SW_XY, SW_D = (0.0, -30.0), 15.0
JACK_Y, JACK_Z = 28.0, -13.0
GEARS = (  # name, teeth, r_out, r_root, thickness, hub hole, x, y, spin deg
    ("GearBig", 10, 40.0, 33.0, 9.0, 10.0, 30.0, 76.0, 9.0),
    ("GearSmall", 7, 25.0, 19.5, 7.0, 6.5, -24.0, 72.0, 4.0),
)
VIEWS = {   # elevation above the floor, azimuth (negative = from the left), aim point, lens mm
    "big":   dict(elev=50.0, azim=-18.0, target=(2.0, 12.0, -10.0), lens=85.0, dist=520.0),
    "small": dict(elev=62.0, azim=-12.0, target=(0.0, 0.0, -14.0), lens=85.0, dist=440.0),
}
ICON_PX = 1024
MARGIN = 0.05                                           # transparent border around the cropped object
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICO_SMALL_MAX = 48                                      # sizes <= this come from the small render

# ----------------------------------------------------------------------------- image helpers (numpy only)
def _area_matrix(n_out, n_in):
    import numpy as np
    M = np.zeros((n_out, n_in), dtype=np.float32)
    s = n_in / n_out
    for i in range(n_out):
        a, b = i * s, (i + 1) * s
        for j in range(int(math.floor(a)), min(n_in, int(math.ceil(b)))):
            M[i, j] = max(0.0, min(b, j + 1) - max(a, j))
        M[i] /= M[i].sum()
    return M

def resize(a, n):
    """Area-average resize of a straight-alpha RGBA array to n x n (premultiplied, so edges stay clean)."""
    import numpy as np
    pm = a.astype(np.float32).copy(); pm[..., :3] *= pm[..., 3:4]
    Mh, Mw = _area_matrix(n, a.shape[0]), _area_matrix(n, a.shape[1])
    out = np.stack([Mh @ pm[..., c] @ Mw.T for c in range(4)], axis=-1)
    al = out[..., 3:4]
    out[..., :3] = np.where(al > 1e-6, out[..., :3] / np.maximum(al, 1e-6), 0.0)
    return np.clip(out, 0.0, 1.0)

def crop_square(a, threshold=0.5, margin=MARGIN):
    """Crop to the solid object (soft floor shadow ignored for the bounds), centre it on a square canvas
    with a margin, and fade the alpha near the canvas border so a clipped shadow never shows a hard edge."""
    import numpy as np
    ys, xs = np.nonzero(a[..., 3] > threshold)
    if len(xs) == 0: return a
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    side = int(math.ceil(max(y1 - y0, x1 - x0) * (1.0 + 2.0 * margin)))
    cy, cx = (y0 + y1) / 2.0, (x0 + x1) / 2.0
    sy, sx = int(round(cy - side / 2.0)), int(round(cx - side / 2.0))
    out = np.zeros((side, side, 4), dtype=np.float32)
    h, w = a.shape[:2]
    ay0, ay1, ax0, ax1 = max(0, sy), min(h, sy + side), max(0, sx), min(w, sx + side)
    out[ay0 - sy:ay1 - sy, ax0 - sx:ax1 - sx] = a[ay0:ay1, ax0:ax1]
    t = np.linspace(0.0, 1.0, side)
    edge = np.clip(np.minimum(t, 1.0 - t) / (margin * 0.8), 0.0, 1.0)
    edge = edge * edge * (3 - 2 * edge)
    out[..., 3] *= edge[:, None] * edge[None, :]
    return out

def write_ico(pngs, path):
    """pngs: [(size, png_bytes)] -> a Windows .ico with PNG-compressed entries (Vista+)."""
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, data in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data; offset += len(data)
    with open(path, "wb") as f: f.write(head + entries + blobs)
    print(f"[icon] wrote {path}  ({', '.join(str(s) for s, _ in pngs)} px)")

# ----------------------------------------------------------------------------- geometry
def gear(name, teeth, r_out, r_root, thick, hole, mat, cutters):
    import bmesh
    p = 2 * math.pi / teeth
    pts = []
    for i in range(teeth):
        c = i * p
        for r, f in ((r_root, -0.5), (r_root, -0.31), (r_out, -0.17), (r_out, 0.0), (r_out, 0.17), (r_root, 0.31)):
            pts.append((r * math.cos(c + f * p), r * math.sin(c + f * p)))
    o = C.flat_shape(name, pts, mat, thickness=thick)
    # hub hole + lightening holes, one cutter mesh parented to the gear so it follows it around
    bm = bmesh.new()
    holes = [(0.0, 0.0, hole)]
    if r_root > 25:
        rr, hr = (hole + r_root) / 2.0, (r_root - hole) * 0.24
        holes += [(rr * math.cos(k * 2 * math.pi / 5), rr * math.sin(k * 2 * math.pi / 5), hr) for k in range(5)]
    for x, y, r in holes:
        ret = bmesh.ops.create_cone(bm, cap_ends=True, segments=64, radius1=r, radius2=r, depth=thick * 3)
        bmesh.ops.translate(bm, verts=ret["verts"], vec=(x, y, thick / 2))
    cut = C.mesh_obj(name + "Holes", bm, None)
    cutters.objects.link(cut)
    cut.parent = o
    b = o.modifiers.new("Holes", "BOOLEAN"); b.operation = "DIFFERENCE"; b.object = cut
    try: b.solver = "EXACT"
    except Exception: pass
    C.bevel(o, 0.7, 3, 40)
    return o

def jack(name, x, side, mats, coll):
    """Chrome 1/4" jack nut + washer on the enclosure side (side = -1 left, +1 right)."""
    nickel, satin = mats
    parts = []
    w = C.cylinder(name + "Washer", 6.2, 0.8, verts=64, mat=satin)
    n = C.cylinder(name + "Nut", 5.6, 2.6, z0=0.8, verts=6, mat=nickel); C.bevel(n, 0.5, 2)
    s = C.cylinder(name + "Sleeve", 4.4, 4.0, z0=0.8, verts=48, mat=nickel)
    h = C.cylinder(name + "Hole", 3.2, 0.6, z0=4.5, verts=48, mat=C.mat_simple(name + "Dark", (0.01, 0.01, 0.01, 1), 0.6))
    import bpy
    piv = bpy.data.objects.new(name + "Pivot", None); coll.objects.link(piv)
    piv.location = (x, JACK_Y, JACK_Z)
    piv.rotation_euler = (0.0, math.radians(90.0 * side), 0.0)
    for o in (w, n, s, h):
        o.parent = piv; coll.objects.link(o); parts.append(o)
    return parts

def build(scene):
    import bpy
    colls = {k: bpy.data.collections.new(k) for k in ("Pedal", "Label", "Gears", "Floor", "Cutters")}
    for c in colls.values(): scene.collection.children.link(c)
    colls["Cutters"].hide_render = True; colls["Cutters"].hide_viewport = True
    ped = colls["Pedal"]

    sx, sy = SW_XY
    body = C.enclosure("Enclosure", W, H, DEPTH, CORNER, None)
    paint = C.mat_metallic_paint("OrangeFlake", ORANGE, body, scuff_center=(sx, sy),
                                 metallic=0.45, coat=0.7, coat_rough=0.05)
    body.data.materials.append(paint)
    ped.objects.link(body)

    chrome = C.mat_metal("Chrome", (0.92, 0.92, 0.94, 1), 0.07, smudges=0.05)
    nickel = C.mat_metal("Nickel", (0.78, 0.77, 0.74, 1), 0.16, smudges=0.06)
    satin = C.mat_metal("SatinMetal", (0.45, 0.45, 0.47, 1), 0.34, smudges=0.1)
    cream = C.mat_plastic("KnobCream", (0.60, 0.54, 0.42, 1), rough=0.38, spec=0.4, smudges=0.06)
    cream_cap = C.mat_plastic("KnobCreamCap", (0.66, 0.60, 0.47, 1), rough=0.22, spec=0.5, coat=0.3, smudges=0.04)
    pointer = C.mat_simple("PointerBlack", (0.012, 0.012, 0.012, 1), rough=0.45)
    ink = C.mat_ink("InkCream", (0.62, 0.56, 0.43, 1), body, chip_amount=0.6)
    gear_steel = C.mat_metal("GearSteel", (0.30, 0.31, 0.33, 1), 0.30, smudges=0.08)

    # knobs
    for i, (kx, ang) in enumerate(KNOBS):
        piv = C.knurled_knob(f"Knob{i}", KNOB_R, KNOB_HEIGHT, (cream, cream_cap, pointer), ped)
        piv.location = (kx, KNOB_Y, 0.0)
        piv.rotation_euler = (0.0, 0.0, -math.radians(ang))

    # LED (lit) in a chrome bezel, plus a little red light so it glows on the paint
    lx, ly = LED_XY
    bez = C.cylinder("LedBezel", LED_R + 1.3, 1.3, mat=chrome); C.bevel(bez, 0.4, 3)
    bez.location = (lx, ly, 0.0); ped.objects.link(bez)
    led_mat = C.mat_led("LedOn", True)
    C.set_in(led_mat.node_tree.nodes.get("Principled BSDF"), "Emission Strength", 6.0)
    lens = C.dome("LedLens", LED_R, 0.6, led_mat, segs=48); lens.location = (lx, ly, 1.3); ped.objects.link(lens)
    glow = bpy.data.lights.new("LedGlow", "POINT"); glow.energy = LED_GLOW_W; glow.color = (1.0, 0.12, 0.05)
    try: glow.shadow_soft_size = 1.5
    except Exception: pass
    go = bpy.data.objects.new("LedGlow", glow); go.location = (lx, ly, 3.2); ped.objects.link(go)

    # footswitch
    washer = C.cylinder("SwWasher", SW_D * 0.56, 0.7, verts=96, mat=satin); C.bevel(washer, 0.2, 2)
    nut = C.cylinder("SwNut", SW_D * 0.5, 3.0, z0=0.7, verts=6, mat=nickel); C.bevel(nut, 0.9, 3)
    nut.rotation_euler = (0, 0, math.radians(30))
    plunger = C.cylinder("SwPlunger", SW_D * 0.32, 6.0, verts=96, mat=chrome); C.bevel(plunger, 0.8, 4); C.smooth(plunger)
    cap = C.dome("SwDome", SW_D * 0.30, 0.45, chrome); cap.location = (0, 0, 6.0)
    for o in (washer, nut, plunger, cap):
        o.location = (sx, sy, o.location.z); ped.objects.link(o)

    # input / output jacks on the sides
    jack("JackIn", W / 2, 1, (nickel, satin), ped)
    jack("JackOut", -W / 2, -1, (nickel, satin), ped)

    # printed name (big icon only)
    font = bpy.data.fonts.load(FONT) if os.path.exists(FONT) else None
    C.text_obj("Label", "PEDAL FACTORY", font, ink, LABEL_RECT, colls["Label"], spacing=1.05, z=0.0)

    # factory gears standing behind the pedal, teeth on the floor
    for name, teeth, r_out, r_root, thick, hole, gx, gy, spin in GEARS:
        g = gear(name, teeth, r_out, r_root, thick, hole, gear_steel, colls["Cutters"])
        g.location = (gx, gy, FLOOR + r_out)
        g.rotation_euler = (math.radians(90.0), math.radians(spin), math.radians(-10.0))
        colls["Gears"].objects.link(g)

    # invisible floor that only keeps the shadows (transparent PNG with a soft contact shadow)
    floor = C.box("Floor", 900.0, 900.0, 1.0, center=(0, 0, FLOOR - 0.5))
    floor.is_shadow_catcher = True
    colls["Floor"].objects.link(floor)
    return colls

# ----------------------------------------------------------------------------- camera
def aim(cam, elev, azim, target, lens, dist):
    from mathutils import Vector
    e, a = math.radians(elev), math.radians(azim)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    t = Vector(target)
    cam.location = t + d * dist
    cam.rotation_euler = (t - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens

# ----------------------------------------------------------------------------- render
def arg(name, default=None):
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for a in args:
        if a.startswith(f"--{name}="): return a.split("=", 1)[1]
    return default

def main():
    import bpy
    os.makedirs(OUT, exist_ok=True); os.makedirs(TMP, exist_ok=True)
    scene = C.setup_scene(ST)
    C.world_hdri(scene, ST.hdri, rotation_deg=40.0)
    C.add_key_light(scene)
    C.add_softbox(scene, size=420.0, height=260.0)
    colls = build(scene)

    cd = bpy.data.cameras.new("IconCam"); cd.clip_start = 1.0; cd.clip_end = 5000.0
    cam = bpy.data.objects.new("IconCam", cd); scene.collection.objects.link(cam); scene.camera = cam
    res = 1024 if ST.quick else 2048
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.render.resolution_percentage = 100

    layers = {"big": ("Pedal", "Label", "Gears", "Floor"), "small": ("Pedal", "Floor")}
    all_c = [colls[k] for k in ("Pedal", "Label", "Gears", "Floor")]

    def setup(view):
        C.show_only([colls[k] for k in layers[view]], all_c)
        aim(cam, **VIEWS[view])

    def render_current(path): C.render_to(scene, path)

    setup("big")
    C.auto_exposure(scene, render_current, 0.50, os.path.join(TMP, "exposure_probe.png"))
    scene.view_settings.exposure += float(arg("exposure", "0"))

    only = arg("only")
    finals = {}
    for view in ("big", "small"):
        dst = os.path.join(OUT, f"PedalFactory_icon_{view}.png")
        if only and only != view:
            if os.path.exists(dst): finals[view] = C.load_rgba(dst)
            continue
        setup(view)
        raw = os.path.join(TMP, f"icon_{view}_raw.png")
        C.render_to(scene, raw)
        img = resize(crop_square(C.load_rgba(raw)), ICON_PX)
        C.save_rgba(img, dst)
        print(f"[icon] wrote {dst}")
        finals[view] = img

    if "big" in finals and "small" in finals:
        pngs = []
        for s in ICO_SIZES:
            src = finals["small"] if s <= ICO_SMALL_MAX else finals["big"]
            p = os.path.join(TMP, f"ico_{s}.png")
            C.save_rgba(resize(src, s), p)
            with open(p, "rb") as f: pngs.append((s, f.read()))
        write_ico(pngs, os.path.join(OUT, "PedalFactory.ico"))

    setup("big")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "icon.blend"))
    print("[icon] done - re-run CMake and rebuild to pick up the new icon")

if __name__ == "__main__":
    import importlib, pedal_render_common as C
    importlib.reload(C)
    ST = C.Settings(sys.argv)
    main()
